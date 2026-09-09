"""
xls_reader.py
~~~~~~~~~~~~~
Reads legacy .xls files directly via the xlrd API, completely bypassing
pandas ExcelFile / read_excel so that the pandas >= 2.0 xlrd-version guard is
never triggered. The xlrd API used here (open_workbook, sheet.nrows/ncols,
sheet.cell, XL_CELL_* constants) is stable for .xls files across xlrd 1.2.x
and 2.x; the runtime dependency therefore pins xlrd>=2.0.

Returns sheet data as {sheet_name: pd.DataFrame} with header=None,
matching the output of pd.read_excel(..., header=None).
"""

import re
import xlrd
import numpy as np
import pandas as pd


def _sheet_to_df(sheet) -> pd.DataFrame:
    """Convert an xlrd Sheet object to a pandas DataFrame (header=None)."""
    data = []
    for rx in range(sheet.nrows):
        row = []
        for cx in range(sheet.ncols):
            cell = sheet.cell(rx, cx)
            # xlrd cell types: 0=empty, 1=text, 2=number, 3=date, 4=bool, 5=error
            if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_ERROR):
                row.append(np.nan)
            elif cell.ctype == xlrd.XL_CELL_TEXT:
                row.append(cell.value)
            elif cell.ctype == xlrd.XL_CELL_NUMBER:
                row.append(cell.value)
            elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                row.append(bool(cell.value))
            else:
                row.append(cell.value)
        data.append(row)
    return pd.DataFrame(data)


def read_xls_sheets(filepath: str) -> tuple[list[str], dict]:
    """
    Open a .xls workbook and return:
      sheet_names : list[str]
      raw         : {sheet_name: pd.DataFrame}  (header=None)
    """
    wb = xlrd.open_workbook(filepath)
    try:
        sheet_names = wb.sheet_names()
        raw = {name: _sheet_to_df(wb.sheet_by_name(name)) for name in sheet_names}
    finally:
        wb.release_resources()
    return sheet_names, raw


ASAP_BLOCK_WIDTHS = {
    "summary report": 2,
    "isotherm linear plot": 4,
    "bet report": 3,
    "bjh adsorption pore distribution report": 6,
    "bjh adsorption dv/dd pore volume": 2,
}
NUMBER_PATTERN = r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
SMP_SIGNATURE = b"^vMIC##&&FS\x00"


def _text(value):
    return " ".join(str(value).strip().casefold().split())


def _asap_blocks(raw):
    found = {}
    for frame in raw.values():
        for (row, col), value in np.ndenumerate(frame.to_numpy()):
            name = _text(value)
            if name not in ASAP_BLOCK_WIDTHS:
                continue
            if name in found:
                raise ValueError(f"检测到多个 {name} 报告，请每次导出一个样品。")
            found[name] = (frame, row, col)
    blocks = {}
    for name, (frame, row, col) in found.items():
        ends = [r for f, r, c in found.values() if f is frame and c == col and r > row]
        end = min(ends, default=len(frame))
        blocks[name] = frame.iloc[row+1:end, col:col+ASAP_BLOCK_WIDTHS[name]].reset_index(drop=True)
    return blocks


def _check_asap_gas(raw):
    gases = set()
    for frame in raw.values():
        for (row, col), value in np.ndenumerate(frame.to_numpy()):
            if _text(value) == "analysis adsorptive:" and col+1 < frame.shape[1]:
                gases.add(_text(frame.iat[row, col+1]))
    if not gases:
        raise ValueError("ASAP 报告缺少吸附质信息（Analysis adsorptive），请导出包含测试条件的完整报告。")
    if not gases <= {"n2", "n₂", "nitrogen"}:
        raise ValueError("此分析模型仅支持 N₂（氮气）吸附数据，不能将其他吸附质按氮气换算。")


def _label_row(frame, label):
    matches = [i for i, value in enumerate(frame.iloc[:, 0]) if _text(value) == label.casefold()]
    if not matches:
        raise ValueError(f"ASAP 报告缺少字段：{label}。请重新导出完整的表格报告。")
    return matches[0]


def _check_unit(value, expected):
    # 接受仪器常见的 Unicode/ASCII 上标写法，但不猜测单位。
    actual = _text(value).replace("³", "3").replace("²", "2").replace("^", "")
    if expected.casefold() not in actual:
        raise ValueError(f"ASAP 单位不匹配：{value}；需要 {expected}（吸附量应为 cm³/g STP）。")


def _numeric_table(frame, *, start, columns):
    rows = []
    for values in frame.iloc[start:, list(columns)].itertuples(index=False, name=None):
        if all(pd.isna(value) or str(value).strip() == "" for value in values):
            continue
        try:
            numeric = np.asarray(values, dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError("ASAP 数据表中包含非数值，请检查导出内容。") from exc
        if not np.isfinite(numeric).all():
            raise ValueError("ASAP 数据行含缺失或非数值，未执行分析。")
        rows.append(numeric)
    return np.asarray(rows, dtype=float).reshape(-1, len(columns))


def _asap_isotherm(block):
    header = _label_row(block, "Relative Pressure (P/Po)")
    if not any(_text(value).endswith("adsorption") for value in block.iloc[:header, 0]):
        raise ValueError("ASAP 吸附支 Adsorption 标记缺失或不一致。")
    _check_unit(block.iat[header, 1], "cm3/g stp")
    ads = _numeric_table(block, start=header+1, columns=(0, 1))
    des = np.empty((0, 2))
    if block.shape[1] >= 4 and _text(block.iat[header, 2]) == "relative pressure (p/po)":
        if not any(_text(value).endswith("desorption") for value in block.iloc[:header, 2]):
            raise ValueError("ASAP 脱附支 Desorption 标记缺失或不一致。")
        _check_unit(block.iat[header, 3], "cm3/g stp")
        des = _numeric_table(block, start=header+1, columns=(2, 3))
    if len(ads) < 5:
        raise ValueError("ASAP 吸附支至少需要 5 个数据点。")
    for data in (ads, des):
        if len(data) and (np.any(data[:, 0] <= 0) or np.any(data[:, 0] > 1) or np.any(data[:, 1] <= 0)):
            raise ValueError("ASAP 等温线需要 0 < p/p₀ ≤ 1，且吸附量必须为正。")
    if np.any(np.diff(ads[:, 0]) <= 0) or np.any(np.diff(des[:, 0]) >= 0):
        raise ValueError("ASAP 吸附支/脱附支压力顺序异常，请检查分支是否正确。")
    return ads, des


def _asap_value(block, label, *, unit=None, required=True, continuation=False):
    try:
        row = _label_row(block, label)
    except ValueError:
        if required:
            raise
        return None
    candidates = range(row, min(row+3, len(block))) if continuation else [row]
    for index in candidates:
        value = str(block.iat[index, 1]).strip()
        match = re.match(NUMBER_PATTERN, value)
        if not match:
            continue
        if unit:
            _check_unit(value, unit)
        number = float(match.group())
        if not np.isfinite(number):
            break
        return number
    raise ValueError(f"ASAP 字段 {label} 缺失或非数值。")


def _asap_bet(block, ads):
    header = _label_row(block, "Relative Pressure (P/Po)")
    _check_unit(block.iat[header, 1], "cm3/g stp")
    _check_unit(block.iat[header, 2], "1/[q(po/p - 1)]")
    points = _numeric_table(block, start=header+1, columns=(0, 1, 2))
    if len(points) < 2 or np.any(points[:, 0] >= 1) or np.any(points <= 0):
        raise ValueError("ASAP BET 表至少需要两个有效数据点，且 p/p₀ < 1。")
    indices = np.abs(ads[:, 0, None] - points[:, 0]).argmin(axis=0)
    if not np.allclose(ads[indices], points[:, :2], rtol=2e-6, atol=1e-9):
        raise ValueError("ASAP BET 表与吸附支数据不一致，无法确认拟合区间。")
    if not np.all(np.diff(indices) == 1):
        raise ValueError("ASAP BET 选点不是连续区间，暂不支持此导出设置。")
    theoretical_y = points[:, 0] / (points[:, 1] * (1-points[:, 0]))
    if not np.allclose(theoretical_y, points[:, 2], rtol=2e-5, atol=1e-10):
        raise ValueError("ASAP BET 线性化数据与吸附量不一致，请重新导出报告。")
    return points[:, [0, 2]]


def _asap_bjh(blocks):
    table = blocks.get("bjh adsorption pore distribution report")
    curve = blocks.get("bjh adsorption dv/dd pore volume")
    if table is None or curve is None:
        return np.empty((0, 4))
    header = _label_row(table, "Pore Diameter Range (nm)")
    for col, label in [(1, "average diameter (nm)"), (3, "cumulative pore volume (cm3/g)"),
                       (5, "cumulative pore area (m2/g)")]:
        _check_unit(table.iat[header, col], label)
    data = _numeric_table(table, start=header+1, columns=(1, 3, 5))
    header = _label_row(curve, "Pore Diameter (nm)")
    _check_unit(curve.iat[header, 1], "dv/dd pore volume (cm3/g·nm)")
    psd = _numeric_table(curve, start=header+1, columns=(0, 1))
    if len(data) != len(psd) or not np.allclose(data[:, 0], psd[:, 0]):
        raise ValueError("ASAP BJH 两张表的孔径网格不一致，请重新导出完整报告。")
    if len(psd) == 0 or np.any(psd[:, 0] <= 0) or np.any(psd[:, 1] < 0) or np.any(data[:, 1:] < 0):
        raise ValueError("ASAP BJH 表为空或含无效孔径、孔容数据。")
    # 原报告按直径微分；项目数据结构按半径微分。
    return np.column_stack([psd[:, 0]/2, psd[:, 1]*2, data[:, 1:]])


def read_asap_report(raw):
    """按标题读取 ASAP 导出报告；未识别到此格式时返回 None。"""
    blocks = _asap_blocks(raw)
    if not blocks:
        return None
    required = {"summary report", "isotherm linear plot", "bet report"}
    if missing := required - blocks.keys():
        raise ValueError(f"ASAP 导出报告缺少 {', '.join(sorted(missing))}；请导出汇总、等温线线性图数据和 BET 报告。")
    _check_asap_gas(raw)
    ads, des = _asap_isotherm(blocks["isotherm linear plot"])
    bet = blocks["bet report"]
    bet_pts = _asap_bet(bet, ads)
    bjh = _asap_bjh(blocks)
    summary_block = blocks["summary report"]
    summary = {
        "S_BET": _asap_value(bet, "BET surface area:", unit="m2/g"),
        "Vm": _asap_value(bet, "Qm:", unit="cm3/g stp"),
        "C": _asap_value(bet, "C:"),
        "Vp_total": _asap_value(summary_block, "Single point adsorption total pore volume of pores", unit="cm3/g", required=False, continuation=True),
        "dp_avg": _asap_value(summary_block, "Adsorption average pore diameter (4V/A by BET):", unit="nm", required=False),
        "S_BJH": float(bjh[:, 3].max()) if len(bjh) else None,
        "Vp_BJH": float(bjh[:, 2].max()) if len(bjh) else None,
        "rp_peak_BJH": float(bjh[np.argmax(bjh[:, 1]), 0]) if len(bjh) else None,
        "start_pt": 0, "end_pt": len(bet_pts)-1,
    }
    if summary["S_BET"] <= 0 or summary["Vm"] <= 0:
        raise ValueError("ASAP 报告中的 BET 比表面积和单层饱和吸附量必须为正。")
    return dict(ads=ads, des=des, bet_pts=bet_pts, bjh=bjh, summary=summary)


def validate_smp(data):
    """仅识别 Micromeritics 原始容器，不猜测二进制测量字段。"""
    if not data.startswith(SMP_SIGNATURE):
        raise ValueError("无法识别此 SMP 文件：不是受识别的 Micromeritics 原始文件，请上传仪器导出的 XLS/XLSX。")
