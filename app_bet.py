"""
BET Analyser — Streamlit Web Application
=========================================
Author  : Hoda Jafari | github.com/Hj1308
License : MIT
"""

import io
import hashlib
import inspect
import re
import warnings
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator
import streamlit as st
from pathlib import Path
from zh_cn import (
    zh, classification_description, rouquerol_report_zh, prepare_figure,
    matplotlib_rendering,
)

from bet_analysis import (
    read_bet_xls,
    classify_isotherm,
    classify_hysteresis,
    verify_bet,
    plot_all,
    setup_plot_style,
    validity_warnings,
    BJH_NARROW_MESOPORE_NM,
    C_ADS, C_DES, C_BET, C_BJH, C_CUM, N2_CAVITATION_NM,
)
from rouquerol import (
    select_bet_range,
    diagnose_instrument_range,
    rouquerol_transform,
    bet_sensitivity_heatmap,
)
from langmuir import (
    fit_langmuir_window,
    format_langmuir_report,
    langmuir_linear_y,
    MIN_LANGMUIR_POINTS,
)

# ════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title='BET 比表面积分析',
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ════════════════════════════════════════════════════════════════════════════
# CUSTOM CSS
# ════════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
    html, body, [data-testid="stApp"], [data-testid="stSidebar"] {
        font-family: "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
    }
    [data-testid="stApp"] :is(h1,h2,h3,h4,p,label,input,button,table),
    [data-baseweb="select"] {
        font-family: "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
    }
    [data-testid="stApp"] h1 { font-size: 1.65rem; }
    [data-testid="stApp"] h3 { font-size: 1.2rem; }
    [data-testid="stCaptionContainer"] { color: #505a65; }
    table, .metric-value { font-variant-numeric: tabular-nums; }
    .block-container { padding-top: 1.5rem; }
    .stAlert { border-radius: 8px; }
    .metric-box {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 12px 16px;
        text-align: center;
    }
    .metric-label { font-size: 0.78rem; color: #6c757d; margin-bottom: 2px; }
    .metric-value { font-size: 1.3rem; font-weight: 700; color: #212529; }
    .metric-unit  { font-size: 0.72rem; color: #6c757d; }
    .tag-valid   { background:#d4edda; color:#155724; border-radius:4px;
                   padding:2px 8px; font-size:0.8rem; font-weight:600; }
    .tag-warning { background:#fff3cd; color:#856404; border-radius:4px;
                   padding:2px 8px; font-size:0.8rem; font-weight:600; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# CSV TEMPLATE
# ════════════════════════════════════════════════════════════════════════════

def _make_csv_template() -> bytes:
    lines = [
        '# BET 分析 — 手动输入模板',
        '# 填写说明：',
        '#   1. 在各数据区填写数据；吸附量单位为 cm³(STP)/g。',
        '#   2. 保留方括号区名、英文字段名及单位，不要翻译它们。',
        '#   3. 以 # 开头的中文说明会被自动忽略。',
        '#   4. 以 UTF-8 CSV（逗号分隔）格式保存。',
        "",
        "[ISOTHERM]",
        '# 吸附支：建议至少 10 个数据点；pp0 为相对压力 p/p0。',
        '# 前两列为吸附支，后两列为脱附支；无脱附数据时保留列名、将后两列留空。',
        "pp0_ads,Va_ads_cm3g,pp0_des,Va_des_cm3g",
        "0.050,5.10,0.950,68.00",
        "0.100,7.20,0.900,62.00",
        "0.150,8.80,0.800,48.00",
        "0.200,10.50,0.700,36.00",
        "0.250,12.10,0.600,28.00",
        "0.300,14.00,0.500,22.00",
        "0.400,17.50,0.400,18.00",
        "0.500,21.00,0.300,14.00",
        "0.600,26.00,,",
        "0.700,32.00,,",
        "0.800,42.00,,",
        "0.900,58.00,,",
        "0.950,68.00,,",
        "",
        "[BET_POINTS]",
        '# BET 线性化数据：1/[Va(p0/p-1)] 对 p/p0。',
        '# 在 0.05 <= p/p0 <= 0.35 区间选择 5–10 个数据点。',
        "pp0,y_bet",
        "0.050,0.0095",
        "0.100,0.0132",
        "0.150,0.0168",
        "0.200,0.0205",
        "0.250,0.0241",
        "0.300,0.0278",
        "",
        "[SUMMARY]",
        '# 仪器报告参数：S_BET/S_BJH 为比表面积；Vm 为单层饱和吸附量；C 为 BET 常数。',
        "parameter,value",
        "S_BET,95.30",
        "Vm,21.90",
        "C,120.50",
        "Vp_total,0.380",
        "dp_avg,16.00",
        "S_BJH,88.00",
        "Vp_BJH,0.370",
        "rp_peak_BJH,4.00",
        "",
        "[BJH]",
        '# BJH 孔径分布（吸附支）；rp_peak_BJH 为峰值孔半径，不是孔直径。',
        '# rp_nm = 孔半径（nm）；dVp_drp = 按孔半径微分的孔容分布。',
        '# cum_Vp = 累积孔容；cum_Sap = 累积比表面积。',
        "rp_nm,dVp_drp,cum-Vp,cum-Sap",
        "1.50,0.0010,0.0010,0.50",
        "2.00,0.0050,0.0060,2.00",
        "2.50,0.0120,0.0180,4.50",
        "3.00,0.0200,0.0380,8.00",
        "4.00,0.0180,0.0560,11.00",
        "5.00,0.0100,0.0660,13.00",
        "7.00,0.0060,0.0720,14.00",
        "10.00,0.0040,0.0760,14.50",
    ]
    return "\n".join(lines).encode("utf-8-sig")


# ════════════════════════════════════════════════════════════════════════════
# CSV PARSER
# ════════════════════════════════════════════════════════════════════════════

def _parse_csv_template(file_bytes: bytes) -> dict:
    text = file_bytes.decode("utf-8-sig")
    lines = [l for l in text.splitlines() if not l.strip().startswith("#")]
    sections = {}; current = None; buf = []
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            if current and buf: sections[current] = "\n".join(buf)
            current = s[1:-1]; buf = []
        elif s:
            buf.append(s)
    if current and buf: sections[current] = "\n".join(buf)

    required = {"ISOTHERM", "BET_POINTS", "SUMMARY", "BJH"}
    missing = required - set(sections)
    if missing:
        raise ValueError(f"Missing sections in CSV template: {missing}.")

    def _read_section(key):
        return pd.read_csv(io.StringIO(sections[key]))

    df_iso = _read_section("ISOTHERM")
    ads_cols = [c for c in df_iso.columns if "ads" in c.lower()]
    des_cols = [c for c in df_iso.columns if "des" in c.lower()]
    ads = df_iso[ads_cols].dropna().values.astype(float)
    des = df_iso[des_cols].dropna().values.astype(float) if des_cols else np.array([])

    df_bet = _read_section("BET_POINTS")
    bet_pts = df_bet.values.astype(float)

    df_sum = _read_section("SUMMARY")
    df_sum.columns = ["parameter", "value"]
    s_dict = dict(zip(df_sum["parameter"].str.strip(),
                      pd.to_numeric(df_sum["value"], errors="coerce")))

    required_keys = ["S_BET", "Vm", "C", "Vp_total", "dp_avg",
                     "S_BJH", "Vp_BJH", "rp_peak_BJH"]
    missing_keys = [k for k in required_keys if k not in s_dict]
    if missing_keys:
        raise ValueError(f"Missing summary parameters: {missing_keys}.")

    summary = {
        "Vm": float(s_dict["Vm"]), "S_BET": float(s_dict["S_BET"]),
        "C": float(s_dict["C"]), "Vp_total": float(s_dict["Vp_total"]),
        "dp_avg": float(s_dict["dp_avg"]), "rp_peak_BJH": float(s_dict["rp_peak_BJH"]),
        "S_BJH": float(s_dict["S_BJH"]), "Vp_BJH": float(s_dict["Vp_BJH"]),
        "start_pt": 0, "end_pt": len(bet_pts) - 1,
    }

    df_bjh = _read_section("BJH")
    bjh = df_bjh.values.astype(float)
    return dict(ads=ads, des=des, bet_pts=bet_pts, bjh=bjh, summary=summary)


# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _read_uploaded_instrument(file_bytes: bytes, ext: str) -> dict:
    """使用系统临时目录读取上传文件，并在解析后自动清理。"""
    with TemporaryDirectory(prefix="bet-upload-") as tmp_dir:
        tmp = Path(tmp_dir) / f"upload{ext}"
        tmp.write_bytes(file_bytes)
        return read_bet_xls(str(tmp))


def _read_uploaded_data(file_bytes: bytes, filename: str) -> dict:
    """单文件和批量入口共用格式识别，支持两种 CSV。"""
    ext = Path(filename).suffix.lower()
    if ext not in {".xls", ".xlsx", ".csv", ".smp"}:
        raise ValueError("仅支持 SMP、XLS、XLSX 或 CSV 文件。")
    if ext == ".csv":
        first = next(
            (line.strip() for line in file_bytes.decode("utf-8-sig").splitlines()
             if line.strip() and not line.lstrip().startswith("#")), ""
        )
        if first.startswith("[") and "]" in first:
            return _parse_csv_template(file_bytes)
    return _read_uploaded_instrument(file_bytes, ext)


def _batch_optional_results(data, iso, row, notes, use_rq, use_tplot):
    """附加分析各自隔离失败，保留已得到的 BET 结果和诊断。"""
    p, n = data["ads"].T
    summary = data["summary"]
    best = None
    row["Rouquerol 状态"] = "未启用"
    if use_rq:
        try:
            best = select_bet_range(p, n)["best"]
            if best is None:
                raise ValueError("未找到可用的拟合区间")
            row.update({
                "Rouquerol 状态": "通过" if best.valid else "未通过",
                "Rouquerol 判据全部满足": zh(best.valid),
                "Rouquerol 比表面积 (m²/g)": best.S_BET,
                "Rouquerol 标准误差 (m²/g)": best.sigma_S_BET,
                "Rouquerol C": best.C, "Rouquerol R²": best.R2,
                "Rouquerol 相对压力下限": best.p_min,
                "Rouquerol 相对压力上限": best.p_max,
                "Rouquerol 点数": best.n_points,
            })
            if not best.valid:
                notes.append("Rouquerol 未通过全部判据；该面积仅供诊断。")
        except Exception as exc:
            row["Rouquerol 状态"] = "未能确定"
            notes.append(f"Rouquerol：{zh(exc)}")

    row["t-plot 状态"] = "未启用"
    if use_tplot:
        try:
            from tplot_analysis import TPlotAnalyser
            rq_valid = best is not None and best.valid
            area = best.S_BET if rq_valid else summary["S_BET"]
            tp = TPlotAnalyser(
                p, n, area, summary.get("Vp_total"),
                c_constant=summary.get("C"),
                total_pore_volume_reason=summary.get("Vp_total_reason"),
            ).full_tplot_report()
            row.update({
                "t-plot 状态": "完成" if tp["micropore_analysis_possible"] else "低压数据不足",
                "t-plot 模型": tp["model"],
                "t-plot BET 来源": "Rouquerol" if rq_valid else row["BET 区间来源"],
                "t-plot 参考曲线": tp["reference_curve"],
                "t-plot 膜厚下限 (Å)": tp["t_range"][0],
                "t-plot 膜厚上限 (Å)": tp["t_range"][1],
                "t-plot 点数": tp["n_points"],
                "t-plot 总比表面积 (m²/g)": tp["S_total_m2g"],
                "t-plot 外比表面积 (m²/g)": tp["S_ext_m2g"],
                "t-plot 微孔比表面积 (m²/g)": tp["S_micro_m2g"],
                "t-plot 微孔孔容 (cm³/g)": tp["V_micro_cm3g"],
                "介孔与大孔合计孔容 (cm³/g)": tp["V_meso_cm3g"],
                "t-plot 2t (nm)": tp["2t_nm"],
            })
            if not tp["micropore_analysis_possible"]:
                notes.append(zh(tp["micropore_analysis_reason"]))
            notes.extend(zh(note) for note in tp.get("warnings", []))
            if tp.get("low_confidence"):
                notes.append(zh(tp["low_confidence_reason"]))
            if tp["S_ext_m2g"] > area:
                notes.append("t-plot 外比表面积高于所用 BET 面积，需检查参考曲线和拟合区间。")
        except Exception as exc:
            row["t-plot 状态"] = "未能确定"
            notes.append(f"t-plot：{zh(exc)}")

    try:
        mask = np.isfinite(p) & np.isfinite(n) & (p > 0) & (p < 1) & (n > 0)
        pl, nl = p[mask], n[mask]
        if len(pl) < MIN_LANGMUIR_POINTS:
            raise ValueError("至少需要 3 个有效吸附点")
        lo, hi = _default_langmuir_range(pl)
        mask = (pl >= lo - 1e-9) & (pl <= hi + 1e-9)
        result = fit_langmuir_window(
            pl[mask], nl[mask], has_hysteresis=iso["has_hysteresis"],
            has_plateau=iso["has_plateau"], S_BET=summary["S_BET"],
        )
        row["Langmuir 状态"] = "通过" if result["model_applicable"] else "不适用"
        row["Langmuir 相对压力下限"] = result["p_min"]
        row["Langmuir 相对压力上限"] = result["p_max"]
        if result["model_applicable"]:
            row["Langmuir 比表面积 (m²/g)"] = result["S_Langmuir"]
            row["Langmuir 标准误差 (m²/g)"] = result["sigma_S_Langmuir"]
            row["Langmuir R²"] = result["R2"]
        else:
            notes.append("Langmuir 未通过模型适用性检查，不报告其面积。")
    except Exception as exc:
        row["Langmuir 状态"] = "未能确定"
        notes.append(f"Langmuir：{zh(exc)}")


def _default_langmuir_range(pressure):
    lo, hi = float(np.min(pressure)), float(np.max(pressure))
    if 0.30 <= lo or 0.05 >= hi:
        return lo, hi
    return max(0.05, lo), min(0.30, hi)


def _analyse_batch_file(filename, content, index, use_rq, use_tplot):
    """一份文件对应一个结果，读取失败也保留独立的汇总行。"""
    name = Path(filename.replace("\\", "/")).stem
    row = {"序号": index, "文件": filename, "样品": name, "状态": "失败"}
    item = {"row": row, "error": None}
    notes = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            data = _read_uploaded_data(content, filename)
            iso = classify_isotherm(data["ads"], data["des"])
            hyst = classify_hysteresis(data["ads"], data["des"])
            bet = verify_bet(data["bet_pts"], data["summary"])
            s = data["summary"]
            # 回归函数可能返回 NaN/Inf；此类文件不能进入成功列表或详情绘图。
            fit_values = [bet[key] for key in ("S_BET_calc", "Vm", "C", "R2", "slope", "intercept")]
            report_values = [s[key] for key in ("S_BET", "Vm", "C")]
            if not (np.isfinite(fit_values).all() and np.isfinite(report_values).all()
                    and np.isfinite(bet["x"]).all() and np.isfinite(bet["y"]).all()):
                raise ValueError("BET 数据或拟合结果包含非有限数值（NaN/Inf），请检查吸附量和拟合区间。")
            instrument = s.get("instrument_summary", True)
            peak = s.get("rp_peak_BJH")
            row.update({
                "状态": "完成",
                "数据来源": "仪器/模板报告" if instrument else "原始等温线计算",
                "BET 区间来源": s.get("window_method", "仪器/模板设定" if instrument else "默认压力范围"),
                "吸附点数": len(data["ads"]), "脱附点数": len(data["des"]),
                "BET 比表面积 (m²/g)": s["S_BET"],
                "BET 重算比表面积 (m²/g)": bet["S_BET_calc"],
                "BET 单层容量 (cm³(STP)/g)": s["Vm"],
                "BET C": s["C"], "BET C 是否为正": zh(s["C"] > 0),
                "BET 重算单层容量 (cm³(STP)/g)": bet["Vm"],
                "BET 重算 C": bet["C"], "BET 重算 R²": bet["R2"],
                "BET 重算 C 是否为正": zh(bet["C_valid"]),
                "BET 相对压力下限": float(np.min(bet["x"])),
                "BET 相对压力上限": float(np.max(bet["x"])),
                "BET 拟合点数": len(bet["x"]),
                "总孔容 (cm³/g)": s.get("Vp_total"),
                "平均孔径 (nm)": s.get("dp_avg"),
                "BJH 数据": "已提供" if len(data["bjh"]) else "未提供",
                "BJH 比表面积 (m²/g)": s.get("S_BJH"),
                "BJH 累积孔容 (cm³/g)": s.get("Vp_BJH"),
                "BJH 峰值孔直径 (nm)": None if peak is None else peak * 2,
                "等温线类型": zh(iso["type"]),
                "滞后环类型": zh(hyst["type"]) if len(data["des"]) else "未提供脱附支",
            })
            notes.extend(f"报告参数：{zh(note)}" for note in validity_warnings(s, iso))
            notes.extend(zh(note) for note in s.get("declined", {}).values())
            _batch_optional_results(data, iso, row, notes, use_rq, use_tplot)
            item.update(data=data, iso=iso, hyst=hyst, bet=bet)
        except Exception as exc:
            item["error"] = str(exc)
            row["状态"] = "失败"
            notes.append(zh(exc))
    notes.extend(f"重算/附加分析：{zh(w.message)}" for w in caught if issubclass(w.category, UserWarning))
    row["提示"] = "；".join(dict.fromkeys(notes))
    if item["error"] is None and notes:
        row["状态"] = "完成（有提示）"
    return item


def _batch_csv(frame):
    """保持数值列可计算；防止文件名被电子表格当作公式。"""
    def safe(value):
        if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
            return "'" + value
        return value
    return frame.apply(lambda column: column.map(safe)).to_csv(index=False).encode("utf-8-sig")


COMPARISON_KINDS = {
    "吸附–脱附等温线": ("isotherm", "相对压力 (p/p₀)", "吸附量 (cm³/g STP)", "📊 总览"),
    "BET 拟合": ("bet", "相对压力 (p/p₀)", "BET 变换 p/[V(p₀−p)] (g/cm³ STP)", "BET"),
    "BJH 孔径分布": ("bjh_psd", "孔径（直径） (nm)", "dV/dD (cm³/g/nm)", "BJH"),
    "BJH 累积孔容": ("bjh_cumulative", "孔径（直径） (nm)", "累积孔容 (cm³/g)", "BJH"),
    "t-plot": ("tplot", "统计膜厚 t (Å)", "吸附量 (cm³/g STP)", "t-plot"),
}


def _sample_label(item):
    return f"{item['row']['序号']:03d} · {item['row']['文件']}"


def _file_scope(identities, index):
    identity = identities[index - 1]
    return hashlib.sha256(repr((identity, identities[:index].count(identity))).encode()).hexdigest()[:16]


def _sample_rq(item):
    if "detail_rq" not in item:
        item["detail_rq"] = select_bet_range(*item["data"]["ads"].T)
    return item["detail_rq"]


def _sample_tplot(item, use_rq):
    """详情与对比共享同一组参数和计算结果；显示开关不改变计算参数。"""
    from tplot_analysis import TPlotAnalyser, LINE1_T_MIN, HJ_VALID_T_MAX
    settings = st.session_state.setdefault("detail_settings", {}).setdefault(item["scope"], {})
    window = tuple(settings.get("tplot_range", (LINE1_T_MIN, HJ_VALID_T_MAX)))
    rq_enabled = use_rq and settings.get("tplot_rq", True)
    signature = (window, rq_enabled)
    cached = item.get("current_tplot")
    if cached is not None and cached["signature"] == signature:
        return cached
    data, summary = item["data"], item["data"]["summary"]
    area = summary["S_BET"]
    source = "仪器/模板报告" if summary.get("instrument_summary", True) else "等温线计算值"
    notes = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        if rq_enabled:
            best = _sample_rq(item)["best"]
            if best is not None:
                area, source = best.S_BET, "Rouquerol"
                if not best.valid:
                    notes.append("Rouquerol 未通过全部判据，所用面积仅供诊断。")
        analyser = TPlotAnalyser(*data["ads"].T, area, summary.get("Vp_total"),
                                c_constant=summary.get("C"),
                                total_pore_volume_reason=summary.get("Vp_total_reason"))
        result = analyser.full_tplot_report(t_min=window[0], t_max=window[1])
    notes.extend(zh(w.message) for w in caught)
    notes.extend(zh(note) for note in result.get("warnings", []))
    if not result["micropore_analysis_possible"]:
        notes.append(zh(result["micropore_analysis_reason"]))
    if result.get("low_confidence"):
        notes.append(zh(result["low_confidence_reason"]))
    if result["S_ext_m2g"] > result["S_BET_m2g"]:
        notes.append("外比表面积高于所用 BET 面积，请检查参考曲线和拟合区间。")
    cached = dict(signature=signature, analyser=analyser, result=result, source=source,
                  requested_range=window, notes=list(dict.fromkeys(notes)))
    item["current_tplot"] = cached
    return cached


def _open_comparison(scope, title):
    state = st.session_state["bet_batch"]
    success = [item for item in state["results"] if item["error"] is None]
    settings = state.setdefault("comparison_settings", {})
    selected = list(settings.get("samples", [_sample_label(item) for item in success]))
    label = next(_sample_label(item) for item in success if item["scope"] == scope)
    if label not in selected:
        selected.append(label)
    settings.update(samples=selected, kind=title)
    st.session_state["comparison_samples"] = selected
    st.session_state["comparison_kind"] = title
    st.session_state["analysis_mode"] = "对比分析"
    st.session_state["detail_settings"][scope]["tab"] = COMPARISON_KINDS[title][3]


def _open_sample(scope, title):
    state = st.session_state["bet_batch"]
    item = next(item for item in state["results"] if item["scope"] == scope)
    state["detail"] = _sample_label(item)
    st.session_state["batch_detail"] = state["detail"]
    st.session_state["analysis_mode"] = "样品分析"
    tab = COMPARISON_KINDS[title][3]
    st.session_state.setdefault("detail_settings", {}).setdefault(scope, {})["tab"] = tab
    st.session_state[f"detail_tab_{scope}"] = tab
    if tab == "t-plot":
        st.session_state["show_tplot"] = True


def _compare_link(kind, label="对比此图 →"):
    title = next(title for title, spec in COMPARISON_KINDS.items() if spec[0] == kind)
    st.button(label, key=f"compare_{kind}", on_click=_open_comparison,
              args=(detail_scope, title))


def _remember_detail_tab(scope, key):
    st.session_state["detail_settings"][scope]["tab"] = st.session_state[key]


def _comparison_series(item, kind):
    """复用批量分析数值；绘图和 CSV 使用相同的曲线，避免单位或选区不一致。"""
    data = item["data"]
    if kind == "isotherm":
        return [(label, data[key][:, 0], data[key][:, 1], style, marker)
                for key, label, style, marker in (
                    ("ads", "吸附支", "-", "o"), ("des", "脱附支", "--", "s"))
                if len(data[key])]
    if kind == "bet":
        bet = item["bet"]
        x_fit = np.linspace(np.min(bet["x"]), np.max(bet["x"]), 100)
        return [
            ("BET 数据点", bet["x"], bet["y"], "None", "o"),
            ("BET 拟合线", x_fit, bet["slope"] * x_fit + bet["intercept"], "-", ""),
        ]
    if kind == "tplot":
        current = item["current_tplot"]
        tp, result = current["analyser"], current["result"]
        valid = np.isfinite(tp.t) & np.isfinite(tp.v)
        end = tp.t[valid].max() * 1.02
        curves = [("t-plot 数据点", tp.t[valid], tp.v[valid], "None", "o")]
        if result["micropore_analysis_possible"] and result["model"] == "single_line":
            x = np.linspace(0, end, 200)
            curves.append(("总比表面积拟合线", x, result["slope_1"] * x, "-", ""))
        else:
            start = result["t_range"][0]
            if result["micropore_analysis_possible"]:
                start = result["t_bend_A"] or tp.t[valid].min()
                x = np.linspace(0, start, 100)
                curves.append(("总比表面积拟合线", x, result["slope_1"] * x, "-", ""))
            x = np.linspace(start, end, 200)
            curves.append(("外比表面积拟合线", x,
                           result["slope_2"] * x + result["intercept_2"], "-", ""))
        return curves
    bjh = data["bjh"]
    if not len(bjh):
        return []
    # 内部存储孔半径和 dV/dr；显示孔直径和 dV/dD，与单样品页面保持一致。
    if kind == "bjh_psd":
        return [("BJH 孔径分布", bjh[:, 0] * 2, bjh[:, 1] / 2, "-", "")]
    cumulative = bjh[np.argsort(bjh[:, 0]), 2]
    direction = "从大孔径累积" if cumulative[-1] < cumulative[0] else "从小孔径累积"
    return [(f"BJH 累积孔容（{direction}）", bjh[:, 0] * 2, bjh[:, 2], "-", "")]


def _plot_sample_comparison(items, kind, title, xlabel, ylabel, branch_mode="吸附与脱附"):
    setup_plot_style()
    fig, ax = plt.subplots(figsize=(8, 4.8))
    frames = []
    colors = [C_ADS, C_DES, C_BET, C_BJH, C_CUM] + list(plt.get_cmap("tab10").colors[5:])
    try:
        for item in items:
            row = item["row"]
            # 按文件身份保持颜色，切换图表、筛选或重排文件时不漂移。
            color = colors[item.get("color_index", row["序号"] - 1) % len(colors)]
            name = f"{row['序号']:03d} · {row['样品']}"
            for branch, x, y, style, marker in _comparison_series(item, kind):
                if kind == "isotherm" and ((branch_mode == "仅吸附" and branch != "吸附支")
                                          or (branch_mode == "仅脱附" and branch != "脱附支")):
                    continue
                order = np.argsort(x)
                x, y = np.asarray(x)[order], np.asarray(y)[order]
                label = name if kind == "bjh_psd" else f"{name} · {branch}"
                ax.plot(x, y, color=color, ls=style, marker=marker,
                        ms=5, lw=1.5, label=label)
                frames.append(pd.DataFrame({
                    "序号": row["序号"], "文件": row["文件"], "样品": row["样品"],
                    "曲线": branch, xlabel: x, ylabel: y,
                }))
        ax.set(xlabel=xlabel, ylabel=ylabel, title=f"多样品对比 · {title}")
        if kind == "isotherm":
            ax.set_xlim(-0.01, 1.01)
            ax.set_ylim(bottom=0)
            ax.xaxis.set_minor_locator(AutoMinorLocator())
            ax.yaxis.set_minor_locator(AutoMinorLocator())
        prepare_figure(fig)
        legend = ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), fontsize=9)
        for text in legend.get_texts():
            text.set_parse_math(False)  # 文件名中的 $ 等字符按原文显示。
        with matplotlib_rendering():
            fig.tight_layout()
        return fig, pd.concat(frames, ignore_index=True)
    except Exception:
        plt.close(fig)
        raise


def _render_sample_comparison(success):
    st.subheader("对比分析")
    st.caption("选择已导入的文件，将同类曲线叠加到一张图中。使用与单文件分析相同的绘图风格。")
    if not success:
        st.info("至少需要 2 个分析成功的样品才能进行同图对比。")
        return
    options = {_sample_label(item): item for item in success}
    settings = st.session_state["bet_batch"].setdefault("comparison_settings", {})
    selected = st.multiselect("选择对比文件", list(options), default=settings.get("samples", list(options)),
                              key="comparison_samples")
    settings["samples"] = selected
    kinds = COMPARISON_KINDS
    title = st.radio("对比图类型", list(kinds), horizontal=True,
                     index=list(kinds).index(settings.get("kind", "吸附–脱附等温线")), key="comparison_kind")
    settings["kind"] = title
    kind, xlabel, ylabel, _ = kinds[title]
    st.caption("同一样品使用相同颜色；按原始数值叠加，不进行归一化或纵向平移。图例序号与批量汇总一致。")
    if kind == "isotherm":
        st.caption("实线圆点为吸附支，虚线方点为脱附支；未提供脱附数据的样品仅显示吸附支。")
    branches = ["吸附与脱附", "仅吸附", "仅脱附"]
    branch_mode = "吸附与脱附"
    if kind == "isotherm":
        branch_mode = st.radio("等温线分支", branches, horizontal=True,
                               index=branches.index(settings.get("branch", branches[0])), key="comparison_branch")
        settings["branch"] = branch_mode
    if kind == "bet":
        st.caption("圆点与实线分别表示 BET 变换值和拟合线；使用各样品原区间重算结果，选区可能不同。Rouquerol 结果请查看汇总表。")
    elif kind.startswith("bjh"):
        st.caption("仅使用输入报告中的 BJH 数据，按孔直径显示；缺失数据不会补零。")
    elif kind == "tplot":
        st.caption("沿用各样品详情中的 t-plot 膜厚区间和 BET 来源；未调整的样品使用默认参数。圆点为实验数据，实线为拟合线。")
    plot_area = st.container()
    detail_options = selected or list(options)
    saved_detail = settings.get("detail", detail_options[0])
    if st.session_state.get("comparison_detail") not in detail_options:
        st.session_state["comparison_detail"] = saved_detail if saved_detail in detail_options else detail_options[0]
    alignment = {"vertical_alignment": "bottom"} if "vertical_alignment" in inspect.signature(st.columns).parameters else {}
    detail_column, action_column = st.columns([3, 1], **alignment)
    detail = detail_column.selectbox("查看样品详情 / 调整参数", detail_options, key="comparison_detail")
    settings["detail"] = detail
    action_column.button("← 查看详情", key="comparison_open_detail", on_click=_open_sample,
                         args=(options[detail]["scope"], title))
    if len(selected) < 2:
        st.info("请至少选择 2 个样品进行对比。")
        return
    items = [options[label] for label in selected]
    parameters = []
    if kind == "tplot":
        valid_items = []
        for item in items:
            try:
                current = _sample_tplot(item, st.session_state["bet_batch"]["signature"][1])
                res = current["result"]
                parameters.append({
                    "序号": item["row"]["序号"], "文件": item["row"]["文件"],
                    "参考曲线": res["reference_curve"], "BET 来源": current["source"],
                    "BET 比表面积 (m²/g)": res["S_BET_m2g"],
                    "设置膜厚下限 (Å)": current["requested_range"][0],
                    "设置膜厚上限 (Å)": current["requested_range"][1],
                    "实际膜厚下限 (Å)": res["t_range"][0], "实际膜厚上限 (Å)": res["t_range"][1],
                    "模型": res["model"], "外比表面积 (m²/g)": res["S_ext_m2g"],
                    "状态": "完成" if res["micropore_analysis_possible"] else "低压数据不足，仅外比表面积拟合",
                })
                valid_items.append(item)
                if current["notes"]:
                    st.warning(f"{_sample_label(item)}：" + "；".join(current["notes"]))
            except Exception as exc:
                st.warning(f"{_sample_label(item)} 的 t-plot 无法计算，已从本图排除：{zh(exc)}")
        items = valid_items
    else:
        for item in items:
            row, bet = item["row"], item["bet"]
            entry = {"序号": row["序号"], "文件": row["文件"], "数据来源": row["数据来源"]}
            if kind == "bet":
                entry.update({"拟合区间来源": row["BET 区间来源"], "相对压力下限": min(bet["x"]),
                              "相对压力上限": max(bet["x"]), "点数": len(bet["x"]),
                              "重算 BET 比表面积 (m²/g)": bet["S_BET_calc"],
                              "C": bet["C"], "R²": bet["R2"]})
            parameters.append(entry)
    if parameters:
        with st.expander("查看各样品参数与来源"):
            st.dataframe(pd.DataFrame(parameters), hide_index=True, use_container_width=True)
            st.caption("参数来自单样品分析；可通过“查看详情”调整，返回本页后自动更新对应曲线。")
    if kind == "isotherm" and branch_mode == "仅脱附":
        missing = [item["row"]["文件"] for item in items if not len(item["data"]["des"])]
        if missing:
            st.warning("以下样品未提供脱附支，已排除：" + "；".join(missing))
        items = [item for item in items if len(item["data"]["des"])]
    if kind.startswith("bjh"):
        columns = 2 if kind == "bjh_psd" else 3
        def has_bjh(item):
            bjh = item["data"]["bjh"]
            return (bjh.ndim == 2 and len(bjh) > 0 and bjh.shape[1] >= columns
                    and np.isfinite(bjh[:, :columns]).all())
        missing = [label for label in selected if not has_bjh(options[label])]
        if missing:
            st.warning("以下样品未提供完整有效的 BJH 数据，已从本图排除：" + "；".join(missing))
        items = [item for item in items if has_bjh(item)]
    if len(items) < 2:
        st.info("当前图表至少需要 2 个具有相应数据的样品，请调整选择或导入完整报告。")
        return
    fig = None
    try:
        fig, frame = _plot_sample_comparison(items, kind, title, xlabel, ylabel, branch_mode)
        if kind == "tplot":
            frame = frame.merge(pd.DataFrame(parameters).drop(columns="文件"), on="序号", how="left")
            frame = frame[[c for c in frame if c not in (xlabel, ylabel)] + [xlabel, ylabel]]
        if kind == "bjh_cumulative":
            st.caption("图例和 CSV 标明累积方向，保留各报告原值。")
            if frame["曲线"].nunique() > 1:
                st.warning("所选报告的累积方向不同，同一孔径下的累积孔容含义不同，请选择相同方向的样品进行数值比较。")
        png = _fig_to_bytes(fig)
        with plot_area:
            _show_figure(fig)
            st.caption("预览与下载使用同一张图；文件选择和分支选择同时作用于图像及 CSV。")
            _render_comparison_data(frame, xlabel, ylabel)
            image_download, data_download = st.columns(2)
            with image_download:
                st.download_button(
                    label="下载对比图 PNG（300 dpi）", data=png,
                    file_name=f"BET_comparison_{kind}.png", mime="image/png",
                )
            with data_download:
                st.download_button(
                    label="下载对比曲线 CSV", data=_batch_csv(frame),
                    file_name=f"BET_comparison_{kind}.csv", mime="text/csv",
                )
    except Exception as exc:
        st.warning(f"对比图生成失败：{zh(exc)}。批量汇总和单样品详情仍可查看。")
    finally:
        if fig is not None:
            plt.close(fig)


def _render_comparison_data(frame, xlabel, ylabel):
    """展示重合提示和绘图所用原始数据。"""
    signatures = {}
    for (number, sample), group in frame.groupby(["序号", "样品"], sort=False):
        signature = group[["曲线", xlabel, ylabel]].to_csv(index=False)
        signatures.setdefault(signature, []).append(f"{number:03d} · {sample}")
    overlaps = [" / ".join(names) for names in signatures.values() if len(names) > 1]
    if overlaps:
        st.info("以下样品的当前曲线完全重合：" + "；".join(overlaps))
    with st.expander("查看当前对比数据"):
        st.dataframe(frame, hide_index=True, use_container_width=True)


def _make_batch_archive(results, progress):
    buffer = io.BytesIO()
    plot_errors = []
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("批量汇总.csv", _batch_csv(pd.DataFrame([r["row"] for r in results])))
        failed = [r["row"] for r in results if r["error"] is not None]
        if failed:
            archive.writestr("失败记录.csv", _batch_csv(pd.DataFrame(failed)))
        for index, item in enumerate(results, 1):
            row = item["row"]
            if item["error"] is None:
                # 序号避免同名覆盖；过滤路径符号和 Windows 非法文件名字符。
                safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", row["样品"]).strip(" .")[:80] or "样品"
                folder = f"{index:03d}_{safe_name}"
                report = pd.DataFrame(list(row.items()), columns=["参数", "数值"])
                archive.writestr(f"{folder}/分析报告.csv", _batch_csv(report))
                figures_before = set(plt.get_fignums())
                try:
                    with matplotlib_rendering():
                        plot_all(item["data"], item["iso"], item["hyst"],
                                 item["bet"], row["样品"], save=False)
                        archive.writestr(f"{folder}/BET分析四联图.png", _fig_to_bytes(plt.gcf()))
                except Exception as exc:
                    plot_errors.append({"文件": row["文件"], "图像生成失败原因": zh(exc)})
                finally:
                    with matplotlib_rendering():
                        for number in set(plt.get_fignums()) - figures_before:
                            plt.close(number)
            progress.progress(index / len(results), text=f"正在打包 {index}/{len(results)}")
        if plot_errors:
            archive.writestr("图像生成失败记录.csv", _batch_csv(pd.DataFrame(plot_errors)))
        archive.writestr(
            "下载说明.txt",
            "每个文件独立分析，同名文件用序号区分；失败文件保留在汇总和失败记录中。\n"
            "BET 字段保留输入报告参数；带“重算”的字段来自原区间回归。Rouquerol 为独立自动选区；四联图采用原区间。\n"
            "t-plot 使用默认 Harkins–Jura 曲线与默认膜厚区间；详细参数见报告。\n"
            "空白数值表示缺失或不予报告，不等于零。请结合状态、提示及方法适用性解读。\n"
            "标准误差仅为拟合传播误差。批量完成不代表各模型的适用性检查均通过。\n"
        )
    return buffer.getvalue(), plot_errors


def _render_batch(files, use_rq, use_tplot, analysis_mode):
    """上传或计算选项变化时自动分析；普通界面交互复用已有结果。"""
    payloads = [(file.name, file.getvalue()) for file in (files or [])]
    signature = (tuple((name, hashlib.sha256(raw).hexdigest()) for name, raw in payloads),
                 use_rq, use_tplot)
    state = st.session_state.get("bet_batch")
    toolbar = file_summary.columns(2)
    if state is None or state["signature"] != signature:
        same_files = state is not None and state["signature"][0] == signature[0]
        preserved = {key: state[key] for key in ("detail", "comparison_settings")
                     if state is not None and key in state}
        old_labels = {_sample_label(item): item.get("scope", _file_scope(state["signature"][0], index))
                      for index, item in enumerate(state["results"], 1)} if state else {}
        if not same_files:
            st.session_state.pop("batch_detail", None)
            st.session_state.pop("comparison_samples", None)
            st.session_state.pop("comparison_detail", None)
        progress = st.progress(0.0, text="准备分析…")
        results = []
        for index, (filename, content) in enumerate(payloads, 1):
            item = _analyse_batch_file(filename, content, index, use_rq, use_tplot)
            item["scope"] = _file_scope(signature[0], index)
            color_map = st.session_state.setdefault("sample_colors", {})
            item["color_index"] = color_map.setdefault(item["scope"], len(color_map))
            results.append(item)
            progress.progress(index / len(payloads), text=f"已处理 {index}/{len(payloads)}：{filename}")
        if not same_files:
            new_labels = {item["scope"]: _sample_label(item) for item in results if item["error"] is None}
            if "detail" in preserved:
                scope = old_labels.get(preserved["detail"])
                if scope in new_labels:
                    preserved["detail"] = new_labels[scope]
                else:
                    preserved.pop("detail")
            if "comparison_settings" in preserved:
                settings = dict(preserved["comparison_settings"])
                if "samples" in settings:
                    settings["samples"] = [new_labels[old_labels[label]] for label in settings["samples"]
                                           if old_labels.get(label) in new_labels]
                if "detail" in settings:
                    scope = old_labels.get(settings["detail"])
                    settings["detail"] = new_labels.get(scope)
                preserved["comparison_settings"] = settings
        state = {"signature": signature, "results": results, **preserved}
        st.session_state["bet_batch"] = state
        progress.empty()
    results = state["results"]
    success = [item for item in results if item["error"] is None]
    file_status.caption(f"当前结果：{len(results)} 个样品 · {len(success)} 个完成 · {len(results) - len(success)} 个失败。")
    frame = pd.DataFrame([item["row"] for item in results])
    with toolbar[0]:
        st.download_button(
            label="导出本次批量 CSV", data=_batch_csv(frame),
            file_name="BET_batch_summary.csv", mime="text/csv",
        )
    if toolbar[1].button("生成批量图表 ZIP", key="batch_zip", disabled=not success):
        progress = st.progress(0.0, text="正在生成图表…")
        state["archive"], state["plot_errors"] = _make_batch_archive(results, progress)
        progress.empty()
    if "archive" in state:
        if state["plot_errors"]:
            file_summary.warning(f"{len(state['plot_errors'])} 个图像生成失败，原因已写入 ZIP；数值报告仍已保留。")
        with file_summary:
            st.download_button(
                label="下载批量结果 ZIP", data=state["archive"],
                file_name="BET_batch_results.zip", mime="application/zip",
            )
    with file_summary.expander("批量汇总与诊断", expanded=not success):
        all_columns = st.checkbox("显示全部字段", key="batch_all_columns")
        compact = ["样品", "状态", "BET 比表面积 (m²/g)", "Rouquerol 比表面积 (m²/g)",
                   "Rouquerol 状态", "总孔容 (cm³/g)", "平均孔径 (nm)", "提示"]
        visible = frame if all_columns else frame[[col for col in compact if col in frame]]
        st.dataframe(visible, use_container_width=True, hide_index=True, column_config={
            "BET 比表面积 (m²/g)": st.column_config.NumberColumn("原报告/输入 BET (m²/g)", format="%.3f"),
            "Rouquerol 比表面积 (m²/g)": st.column_config.NumberColumn(format="%.3f"),
            "总孔容 (cm³/g)": st.column_config.NumberColumn(format="%.4f"),
            "平均孔径 (nm)": st.column_config.NumberColumn(format="%.2f"),
            "提示": st.column_config.TextColumn(width="large"),
        })
        st.caption("CSV 始终包含全部字段。原报告值与自动选区结果分别保留；请结合方法状态判断适用性。")
        for item in results:
            row = item["row"]
            if row["提示"]:
                st.write(f"{row['序号']:03d} · {row['文件']} · {row['状态']}")
                st.write(row["提示"])
    if analysis_mode == "对比分析":
        _render_sample_comparison(success)
        return None
    if not success:
        if len(results) == 1:
            st.error(f"**文件读取失败：** {zh(results[0]['error'])}")
        return None
    options = ["请选择样品"] + [
        f"{item['row']['序号']:03d} · {item['row']['文件']}" for item in success
    ]
    with sample_picker:
        st.subheader("选择分析文件")
        saved_detail = state.get("detail", options[1])
        detail = st.selectbox("查看单个样品详细分析", options,
                              index=options.index(saved_detail), key="batch_detail")
        state["detail"] = detail
        st.caption("选择文件后，下方沿用单文件的全部分析图表。可输入文件名搜索。")
    if detail != options[0]:
        selected = success[options.index(detail) - 1]
        st.subheader(f"当前分析文件：{selected['row']['文件']}")
        st.caption("通过左侧文件选择器切换分析内容；样品参数分别保存，批量汇总保留本次批量计算的参数。")
        return selected
    else:
        st.info("请从左侧选择要查看的样品。")
    return None


def _fig_to_bytes(fig) -> bytes:
    buf = io.BytesIO()
    with matplotlib_rendering():
        fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    buf.seek(0)
    return buf.read()


def _show_figure(fig) -> None:
    """交给 Streamlit 渲染时持有与排版相同的进程级绘图锁。"""
    with matplotlib_rendering():
        st.pyplot(fig, use_container_width=True)


def _fmt(v, spec: str) -> str:
    """Format a value, or an em-dash when it is absent (None)."""
    return "—" if v is None else f"{v:{spec}}"


def _bet_source_table(summary, bet, rq):
    """报告值、原区间回归、自动选区分别呈现，不默认为推荐报告值。"""
    origin = "仪器/模板报告" if summary.get("instrument_summary", True) else "等温线计算值"
    window = f"{min(bet['x']):.4f}–{max(bet['x']):.4f}"
    def status(c):
        return "不适用：C ≤ 2" if c <= 2 else "C > 2；仍需检查选区与等温线"
    rows = [
        [origin, summary["S_BET"], summary["C"], window, status(summary["C"])],
        ["原区间重算", bet["S_BET_calc"], bet["C"], window, status(bet["C"])],
    ]
    best = rq["best"] if rq else None
    rows.append(["Rouquerol 自动选区", best.S_BET if best else None,
                 best.C if best else None,
                 f"{best.p_min:.4f}–{best.p_max:.4f}" if best else "—",
                 ("判据通过" if best.valid else "未通过全部判据；仅供诊断") if best else "未启用或无可用区间"])
    return pd.DataFrame(rows, columns=["结果来源", "比表面积 (m²/g)", "C", "相对压力区间", "适用状态"])


def _plot_isotherm(ads, des, iso_cls, hyst_cls) -> plt.Figure:
    """Draw the N₂ adsorption–desorption isotherm as a standalone figure."""
    setup_plot_style()
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.plot(ads[:, 0], ads[:, 1], "o-", color=C_ADS,
            ms=5, lw=1.5, label='吸附支')

    if len(des) > 0:
        sort_d = np.argsort(des[:, 0])[::-1]
        ax.plot(des[sort_d, 0], des[sort_d, 1], "s--", color=C_DES,
                ms=5, lw=1.5, label='脱附支')
        pp0_fill = np.concatenate([ads[:, 0], des[sort_d, 0][::-1]])
        Va_fill  = np.concatenate([ads[:, 1], des[sort_d, 1][::-1]])
        ax.fill(pp0_fill, Va_fill, alpha=0.10, color=C_ADS)

    ax.set_xlabel(r"相对压力 ($p/p_0$)", fontsize=11)
    ax.set_ylabel(r"吸附量 (cm$^3$ g$^{-1}$ STP)", fontsize=11)
    ax.set_xlim(-0.01, 1.01)
    ax.set_ylim(bottom=0)
    ax.xaxis.set_minor_locator(AutoMinorLocator())
    ax.yaxis.set_minor_locator(AutoMinorLocator())
    ax.legend(loc="upper left", fontsize=9)

    hl = hyst_cls["type"]
    ann = zh(iso_cls["type"]) + (f" / {hl}" if hl != "None" else "")
    ax.text(0.97, 0.05, ann, transform=ax.transAxes,
            va="bottom", ha="right", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="0.7", lw=0.7))

    ax.set_title("N₂ 吸附–脱附等温线 (77 K)", fontsize=11)
    prepare_figure(fig)
    with matplotlib_rendering():
        fig.tight_layout()
    return fig


def _plot_rouquerol_transform(p_rel, n, best_window) -> plt.Figure:
    """Plot n(1−p/p0) vs p/p0: full range plus a zoom on the selected BET window.

    The full-range panel keeps the Rouquerol-transform maximum (which sets the
    upper BET bound); a second, zoomed panel is confined to the selected window
    so the four consistency criteria can actually be inspected. A second panel
    was chosen over an inset so the zoomed region is large enough to read and
    the two views do not overlap.
    """
    setup_plot_style()
    fig, (ax, ax_zoom) = plt.subplots(1, 2, figsize=(10, 3.8))
    t = rouquerol_transform(p_rel, n)

    for a in (ax, ax_zoom):
        a.plot(p_rel, t, "o-", color=C_ADS, ms=4, lw=1.4, label="n(1−p/p₀)")
        if best_window is not None:
            a.axvspan(best_window.p_min, best_window.p_max,
                      alpha=0.18, color=C_BET, label="所选 BET 区间")
            a.axvline(best_window.p_min, ls="--", lw=0.9, color=C_BET)
            a.axvline(best_window.p_max, ls="--", lw=0.9, color=C_BET)
        a.set_xlabel(r"$p/p_0$")
        a.set_ylabel(r"$n(1-p/p_0)$  (cm³ g⁻¹)")

    ax.legend(fontsize=8)
    ax.set_title("Rouquerol 变换（全区间）", fontsize=10)

    if best_window is not None:
        margin = 0.1 * (best_window.p_max - best_window.p_min)
        # Relative pressure cannot be negative: keep the 10% margin but never
        # let the lower bound drop below zero.
        ax_zoom.set_xlim(max(best_window.p_min - margin, 0.0),
                         best_window.p_max + margin)
        in_win = (p_rel >= best_window.p_min) & (p_rel <= best_window.p_max)
        if in_win.any():
            y_win = t[in_win]
            y_margin = 0.1 * (y_win.max() - y_win.min())
            ax_zoom.set_ylim(y_win.min() - y_margin, y_win.max() + y_margin)
        ax_zoom.legend(fontsize=8)
        ax_zoom.set_title("所选 BET 区间（局部放大）", fontsize=10)
    else:
        ax_zoom.set_title("所选 BET 区间", fontsize=10)

    prepare_figure(fig)
    with matplotlib_rendering():
        fig.tight_layout()
    return fig



def _plot_bet_heatmap(heatmap_result, best_window) -> plt.Figure:
    """Plot S_BET sensitivity heatmap (BEaTmap-style)."""
    setup_plot_style()
    s_bet = heatmap_result["s_bet"]
    valid = heatmap_result["valid"]
    p = heatmap_result["p_sorted"]
    N = heatmap_result["n_points"]

    s_masked = np.ma.masked_where(~valid | ~np.isfinite(s_bet), s_bet)

    fig, ax = plt.subplots(figsize=(7, 5.5))
    cmap = plt.cm.RdYlGn_r.copy()
    cmap.set_bad(color="#e0e0e0")

    im = ax.imshow(s_masked, aspect="auto", cmap=cmap,
                   origin="lower", interpolation="nearest")

    if best_window is not None:
        start_idx = int(np.argmin(np.abs(p - best_window.p_min)))
        end_idx = int(np.argmin(np.abs(p - best_window.p_max)))

        rect = plt.Rectangle(
            (end_idx - 0.5, start_idx - 0.5),
            1.0,
            1.0,
            linewidth=2.2,
            edgecolor="blue",
            facecolor="none",
            linestyle="--",
        )
        ax.add_patch(rect)

    tick_step = max(1, N // 8)
    tick_pos = np.arange(0, N, tick_step)
    tick_labels = [f"{p[i]:.2f}" for i in tick_pos]
    ax.set_xticks(tick_pos)
    ax.set_xticklabels(tick_labels, fontsize=8, rotation=45)
    ax.set_yticks(tick_pos)
    ax.set_yticklabels(tick_labels, fontsize=8)

    ax.set_xlabel("终点相对压力 p/p₀")
    ax.set_ylabel("起点相对压力 p/p₀")
    plt.colorbar(im, ax=ax, label="S_BET (m² g⁻¹)")
    ax.set_title("BET 比表面积对选区的敏感性热图", fontsize=10)
    prepare_figure(fig)
    with matplotlib_rendering():
        fig.tight_layout()
    return fig


def _plot_langmuir_linear(p_all, n_all, result) -> plt.Figure:
    """Draw the Langmuir linear plot: (p/p0)/n vs p/p0 with fitted line."""
    setup_plot_style()
    fig, ax = plt.subplots(figsize=(5, 3.8))

    y_all = langmuir_linear_y(p_all, n_all)
    valid_all = np.isfinite(y_all)
    ax.scatter(p_all[valid_all], y_all[valid_all],
               color="0.75", s=22, zorder=2, label='全部数据点')

    x = result["x"]
    y = result["y"]
    ax.scatter(x, y, color=C_BJH, s=32, zorder=4, label='拟合数据点')

    x_fit = np.linspace(x.min(), x.max(), 200)
    ax.plot(x_fit, result["slope"] * x_fit + result["intercept"],
            "-", color=C_BJH, lw=1.6)

    ax.set_xlabel(r"$p/p_0$")
    ax.set_ylabel(r"$(p/p_0)/n$  (g cm$^{-3}$)")
    ax.legend(fontsize=8)
    ax.text(0.05, 0.94, f"R² = {result['R2']:.5f}",
            transform=ax.transAxes, va="top", fontsize=9)
    ax.text(0.05, 0.85,
            f"S = {result['S_Langmuir']:.2f} ± {result['sigma_S_Langmuir']:.2f} m² g⁻¹",
            transform=ax.transAxes, va="top", fontsize=9)
    ax.set_title("Langmuir 线性图", fontsize=10)
    prepare_figure(fig)
    with matplotlib_rendering():
        fig.tight_layout()
    return fig


def _match_instrument_window_by_pressure(p_ads, n_ads, bet_pts,
                                         start_pt, end_pt):
    """
    Evaluate the instrument's BET point range on the adsorption branch.

    start_pt/end_pt are row indices into the instrument's BET sheet, which
    is usually a subset of the adsorption points — so they cannot be used
    as indices into p_ads directly. Instead we take the instrument's p/p₀
    window and select the adsorption-branch points that fall inside it,
    then run the Rouquerol consistency check on that window.
    """
    inst_p = bet_pts[start_pt:end_pt + 1, 0]
    p_lo, p_hi = float(np.min(inst_p)), float(np.max(inst_p))
    mask = (p_ads >= p_lo - 1e-9) & (p_ads <= p_hi + 1e-9)
    idx = np.where(mask)[0]
    if len(idx) < 4:
        return None
    return diagnose_instrument_range(p_ads, n_ads, int(idx[0]), int(idx[-1]))


# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════════════

def _native_smp_info(parsed):
    st.success(f"已直接读取 SMP：{len(parsed['ads'])} 个吸附点、{len(parsed['des'])} 个脱附点。")
    st.caption(
        f"{parsed['version']} · 样品质量 {parsed['mass']:.4f} g · N₂。"
        "直接读取目前仅经一个 ASAP 2460 样品核对，其他版本和校正配置可能需要 XLS。"
    )
    with st.expander("SMP 测量信息"):
        c = parsed['conditions']
        st.write({"样品": parsed['name'], "仪器序列号": parsed['serial'],
                  "分析温度 (K)": c['bath'], "环境自由空间 (cm³)": c['warm'],
                  "分析自由空间 (cm³)": c['cold'], "非理想气体校正因子 (mmHg⁻¹)": c['alpha']})
    return st.checkbox("改用仪器导出的 XLS/XLSX 报告", key="smp_prefer_export")


def _smp_export_upload(source):
    """已验证的 SMP 直接分析；未支持的布局保留配套报告入口。"""
    from xls_reader import validate_smp
    from smp_reader import inspect_smp
    try:
        validate_smp(source.getvalue())
    except ValueError as exc:
        st.error(str(exc))
        return None
    try:
        parsed = inspect_smp(source.getvalue())
    except ValueError as exc:
        st.info(f"已识别 Micromeritics SMP 原始文件，但暂不能直接分析此文件。{exc}")
    else:
        if not _native_smp_info(parsed):
            return source
        st.info("已切换为仪器 XLS/XLSX 报告导入。")
    with st.expander("如何从 SMP 导出报告"):
        st.markdown(
            "在 ASAP / MicroActive 软件中打开 SMP，使用 **Reports → Start Report**，"
            "选择汇总报告、等温线线性图及 BET 报告；需要孔径分布时，同时选择 "
            "BJH 吸附支分布表和 dV/dD 曲线。将报告保存为 **Spreadsheet (*.XLS)**。"
        )
    exported = st.file_uploader(
        "上传该样品导出的 XLS/XLSX", type=["xls", "xlsx"], key="smp_export",
    )
    if exported is not None:
        st.caption(f"分析数据来源：{exported.name}；SMP 文件仅作格式识别，未参与数值计算。")
    return exported


with st.sidebar:
    st.title('🔬 BET 比表面积分析')
    st.caption("BET/BJH 与 t-plot 分析 · 支持论文级图表")
    sample_picker = st.container()
    st.divider()

    st.subheader('📁 数据输入')
    st.caption("支持一次上传一个或多个文件，上传后自动分析。自动识别 SMP、XLS、XLSX 和 CSV。")
    with st.expander("需要手动整理数据？下载 CSV 模板"):
        st.info("📥 下载模板、填写数据后，在此上传。")
        st.download_button(
            label="⬇ 下载 CSV 模板",
            data=_make_csv_template(),
            file_name="BET_template.csv",
            mime="text/csv",
        )

    with st.expander("添加或更新数据文件", expanded=True):
        uploaded_files = st.file_uploader(
            '上传数据文件',
            type=["xls", "xlsx", "csv", "smp"],
            accept_multiple_files=True,
            key="data_files",
            help="支持已验证的 ASAP 2460 v3.01 SMP、单表 XLS/XLSX 和原有格式；未知 SMP 配置可改用仪器报告。",
        ) or []
    batch_mode = len(uploaded_files) > 1
    uploaded = uploaded_files[0] if len(uploaded_files) == 1 else None
    if uploaded is not None and Path(uploaded.name).suffix.lower() == ".smp":
        uploaded = _smp_export_upload(uploaded)
        uploaded_files = [uploaded] if uploaded is not None else []
    if not uploaded_files:
        for key in ("bet_batch", "batch_detail", "comparison_samples", "comparison_detail", "sample_colors", "detail_png", "detail_rq"):
            st.session_state.pop(key, None)
    file_status = st.container()
    file_summary = st.expander("文件汇总与下载", expanded=False)

    st.divider()
    if batch_mode:
        sample_name = ""
        st.caption("批量样品名称取自文件名。未支持的 SMP 请换用仪器导出的 XLS/XLSX。")
    else:
        default_sample = Path(uploaded.name).stem if uploaded is not None else '样品'
        sample_name = st.text_input('样品名称', value=default_sample)

    st.divider()
    st.subheader('⚙️ 分析选项')
    show_tplot    = st.checkbox("显示 t-plot 微孔分析", value=True, key="show_tplot")
    calculate_tplot = st.checkbox("批量计算 t-plot", value=True, key="batch_calculate_tplot") if batch_mode else True
    show_features = st.checkbox("显示滞后环特征表", value=True)
    use_rouquerol = st.checkbox(
        "按 Rouquerol 判据自动选择 BET 线性区间",
        value=True,
        help="依据 Rouquerol 一致性判据（IUPAC 2015）自动选择 BET 线性拟合区间。",
    )

    with st.expander("专业术语与单位"):
        st.markdown(
            "- **比表面积**：单位质量样品的表面积，通常以 m²/g 表示。\n"
            "- **吸附量**：本软件使用标准状况下的气体体积，单位 cm³(STP)/g；STP 指标准温度和压力条件。\n"
            "- **孔容**：单位质量样品的孔体积，单位 cm³/g；与气体吸附量不同。\n"
            "- **孔径分布（PSD）**：图中横轴按孔直径表示；仪器 BJH 原始 rp 字段表示孔半径。\n"
            "- **滞后环**：吸附支与脱附支不重合形成的环。分类得分占比不是统计置信度。\n"
            "- **Rouquerol 判据**：用于检查 BET 线性拟合区间的一致性。\n"
            "- **t-plot（吸附膜厚度法）**：利用吸附量与统计膜厚的关系分析外比表面积和微孔。\n"
            "- **不确定度**：表征估计值的不确定程度，不等同于测量误差。\n"
            "- **Å（埃）**：1 Å = 0.1 nm。"
        )

    st.divider()
    st.markdown(
        "**DOI:** [10.5281/zenodo.22116897](https://doi.org/10.5281/zenodo.22116897)  \n"
        "MIT 许可证 · [GitHub](https://github.com/Hj1308/BET_analyser)"
    )


# ════════════════════════════════════════════════════════════════════════════
# MAIN PAGE
# ════════════════════════════════════════════════════════════════════════════

st.title('🔬 BET / BJH 比表面积与孔结构分析')
st.caption("气体物理吸附分析 · 依据 IUPAC 2015 建议")
analysis_mode = st.radio("分析功能", ["样品分析", "对比分析"], horizontal=True, key="analysis_mode")

detail_scope = None
selection = None
if uploaded_files:
    selection = _render_batch(uploaded_files, use_rouquerol, calculate_tplot, analysis_mode)
    if selection is None:
        st.stop()
    if batch_mode:
        sample_name = selection["row"]["样品"]
    detail_scope = selection.get("scope")
    if detail_scope is None:  # 兼容页面更新前会话里保留的结果。
        sample_index = selection["row"]["序号"]
        identities = st.session_state["bet_batch"]["signature"][0]
        detail_scope = _file_scope(identities, sample_index)
        selection["scope"] = detail_scope
elif analysis_mode == "对比分析":
    st.subheader("对比分析")
    st.info("请在左侧上传多个文件，自动分析后即可选择文件进行同图叠加。")
    st.stop()

if not uploaded_files:
    st.info("👈 从左侧上传数据文件，开始分析。")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### 📁 仪器数据")
        st.markdown("支持直接读取已验证的 **ASAP 2460 v3.01 SMP 原始数据**、单工作表 XLS/XLSX 报告及原有多工作表格式。")
    with c2:
        st.markdown("### 📋 手动录入 CSV")
        st.markdown("没有仪器 XLS 文件时，可从左侧下载 **CSV 模板**，按说明填写数据。")
    with c3:
        st.markdown("### 📊 分析内容")
        st.markdown(
            "- IUPAC 等温线与滞后环分类\n"
            "- BET 线性回归、决定系数 R² 与常数 C 检查\n"
            "- 依据 Rouquerol 判据自动选择 BET 区间\n"
            "- BJH 微分孔径分布\n"
            "- 累积孔容与累积比表面积\n"
            "- t-plot 微孔分析\n"
            "- 下载 300 dpi 图像与 CSV 报告"
        )
    st.stop()


data = selection["data"]

# ── Run analysis ─────────────────────────────────────────────────────────────────────
with st.spinner("正在分析…"):
    iso_cls  = classify_isotherm(data["ads"], data["des"])
    hyst_cls = classify_hysteresis(data["ads"], data["des"])
    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        bet_res = verify_bet(data["bet_pts"], data["summary"])

for w in caught_warnings:
    st.warning(f"⚠ {zh(w.message)}")

s = data["summary"]

# ── Rouquerol auto range ────────────────────────────────────────────────────────────
p_ads = data["ads"][:, 0]
n_ads = data["ads"][:, 1]
rouquerol_result = None
instrument_window = None

if use_rouquerol:
    with st.spinner("正在按 Rouquerol 判据选择区间…"):
        rouquerol_result = _sample_rq(selection)
        if s.get("window_derived"):
            # No instrument window exists for a plain isotherm; the derived
            # default window is not an instrument value, so the instrument-vs-
            # Rouquerol comparison is declined.
            instrument_window = None
        else:
            try:
                instrument_window = _match_instrument_window_by_pressure(
                    p_ads, n_ads, data["bet_pts"], s["start_pt"], s["end_pt"]
                )
            except Exception:
                instrument_window = None
    heatmap_result = None
    if rouquerol_result is not None:
        try:
            if "heatmap" not in selection:
                selection["heatmap"] = bet_sensitivity_heatmap(p_ads, n_ads)
            heatmap_result = selection["heatmap"]
        except Exception:
            heatmap_result = None


# ════════════════════════════════════════════════════════════════════════════
# RESULTS TABS
# ════════════════════════════════════════════════════════════════════════════

langmuir_result = None
tplot_result = None
tplot_error = None
detail_downloads = st.container()
bet_sources = _bet_source_table(s, bet_res, rouquerol_result)
detail_settings = st.session_state.setdefault("detail_settings", {}).setdefault(detail_scope, {})

tab_labels = ['📊 总览', 'BET', 'Langmuir', 'Rouquerol', 'BJH', 't-plot', '导出说明']
tab_options = {}
if "on_change" in inspect.signature(st.tabs).parameters:
    tab_key = f"detail_tab_{detail_scope}"
    if tab_key not in st.session_state:
        st.session_state[tab_key] = detail_settings.get("tab", tab_labels[0])
    tab_options = dict(key=tab_key, on_change=_remember_detail_tab, args=(detail_scope, tab_key))
elif detail_settings.get("tab"):
    st.caption(f"请点击下方“{detail_settings['tab']}”页签查看对应分析。")
tab_overview, tab_bet, tab_langmuir, tab_rouquerol, tab_bjh, tab_tplot, tab_download = st.tabs(tab_labels, **tab_options)


# ── TAB 1: OVERVIEW ─────────────────────────────────────────────────────────────────
with tab_overview:
    st.subheader(f"分析结果 — {sample_name}")
    st.markdown("**BET 结果来源与适用状态**")
    st.dataframe(bet_sources, hide_index=True, use_container_width=True, column_config={
        "比表面积 (m²/g)": st.column_config.NumberColumn(format="%.3f"),
        "C": st.column_config.NumberColumn(format="%.2f"),
        "适用状态": st.column_config.TextColumn(width="large"),
    })
    st.caption("各来源分别保留；判据通过不等于完整的测量质量验证。请确认来源和适用性后再报告结果。")

    # ─ KPI metrics row
    cols = st.columns(4)
    kpi = [
        (_fmt(s.get("Vp_total"), ".4f"), "cm³ g⁻¹", "总孔容"),
        (_fmt(s.get("dp_avg"), ".1f"),   "nm",       "平均孔径（直径）"),
        (str(len(data["ads"])), "点", "吸附数据"),
        (str(len(data["des"])), "点", "脱附数据"),
    ]
    for col, (val, unit, label) in zip(cols, kpi):
        with col:
            st.markdown(
                f'<div class="metric-box"><div class="metric-label">{label}</div>'
                f'<div class="metric-value">{val}</div>'
                f'<div class="metric-unit">{unit}</div></div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # ─ Isotherm plot + classification side by side
    col_plot, col_cls = st.columns([2, 1])

    with col_plot:
        st.markdown("**N₂ 吸附–脱附等温线**")
        _compare_link("isotherm")
        fig_iso = _plot_isotherm(data["ads"], data["des"], iso_cls, hyst_cls)
        _show_figure(fig_iso)
        plt.close(fig_iso)

    with col_cls:
        st.markdown("**等温线分类**")
        st.success(f"**{zh(iso_cls['type'])}**  \n{classification_description(iso_cls)}")
        if len(data.get("des", [])) == 0:
            st.info("未判定 IV/V 型：未提供脱附支数据"
                    "（输入仅包含吸附支）。")

        st.markdown("**滞后环分类**")
        if hyst_cls["type"] != "None":
            share = hyst_cls["score_share"]
            fn = st.success if share == "high" else st.warning if share == "moderate" else st.error
            fn(
                f"**{hyst_cls['type']}**  \n"
                f"{classification_description(hyst_cls, hysteresis=True)}  \n"
                f"得分占比：{zh(share)}（占总得分的 {hyst_cls['score_share_pct']:.0f}%，不是概率或统计置信度）"
            )
        elif len(data.get("des", [])) == 0:
            st.info("未判定滞后环：未提供脱附支数据。")
        else:
            st.info("未检测到滞后环。")

        no_condensation_types = ("Type I(a)", "Type I(b)", "Type II", "Type III",
                                 "Type VI")
        if iso_cls["type"] in no_condensation_types and hyst_cls["type"] != "None":
            st.info(
                f"{hyst_cls['type']} 滞后环与"
                f"{zh(iso_cls['type'])} 等温线可以同时出现；H3 "
                "型滞后环按定义可伴随 II 型吸附支"
                "(Thommes et al. 2015 §4.3.2)."
            )

    st.divider()

    # ─ Summary table
    st.markdown("**参数汇总**")
    df_out = pd.DataFrame([
        ["BET 比表面积",      _fmt(s.get("S_BET"), ".3f"),         "m² g⁻¹"],
        ["单层饱和吸附量 Vm",    _fmt(s.get("Vm"), ".4f"),            "cm³(STP) g⁻¹"],
        ["BET 常数 C",         _fmt(s.get("C"), ".2f"),             "—"],
        ["总孔容",      _fmt(s.get("Vp_total"), ".4f"),      "cm³ g⁻¹"],
        ["平均孔径（直径）",  _fmt(s.get("dp_avg"), ".3f"),        "nm"],
        ["BJH 比表面积",       _fmt(s.get("S_BJH"), ".3f"),         "m² g⁻¹"],
        ["BJH 峰值孔径（直径）", _fmt(None if s.get("rp_peak_BJH") is None else s["rp_peak_BJH"] * 2, ".2f"), "nm"],
    ], columns=['参数', '数值', '单位'])
    st.dataframe(df_out, use_container_width=True, hide_index=True)

    # ─ Declined / derived notes (plain-isotherm input) ──────────────
    if s.get("window_derived"):
        method = "Rouquerol 一致性判据" if s.get("window_method") == "Rouquerol" else "默认压力范围（0.05 ≤ p/p₀ ≤ 0.35，点数不足时扩大范围）"
        st.caption(f"BET 拟合区间由{method}确定，并非读取的仪器设定区间。")
    declined = []
    for label, reason in (s.get("declined") or {}).items():
        declined.append(f"{zh(label)}（{zh(reason)}）")
    if s.get("Vp_total_reason"):
        declined.append(f"总孔容（Gurvich 规则）— {zh(s['Vp_total_reason'])}")
    if declined:
        st.info("**数据不足，不予报告：** " + "; ".join(declined))

    tag = (
        '<span class="tag-valid">✓ BET 常数 C 为正</span>'
        if bet_res["C_valid"] else
        '<span class="tag-warning">⚠ BET 常数 C 为负，请检查相对压力区间</span>'
    )
    st.markdown(tag, unsafe_allow_html=True)

    for note in validity_warnings(s, iso_cls):
        st.warning(zh(note))

    # ── Rouquerol summary on overview ─────────────────────────────────────────────
    if use_rouquerol and rouquerol_result is not None:
        best = rouquerol_result["best"]
        if best is not None:
            st.divider()
            st.markdown("**Rouquerol BET 拟合区间**")
            if best.valid:
                st.success(
                    f"✓ **通过** — 自动选择的区间：p/p₀ = "
                    f"{best.p_min:.4f} – {best.p_max:.4f}（{best.n_points} 个数据点）  \n"
                    f"S_BET = {best.S_BET:.2f} ± {best.sigma_S_BET:.2f} m² g⁻¹ | C = {best.C:.1f} ± {best.sigma_C:.1f} | R² = {best.R2:.6f}"
                )
            else:
                st.warning(
                    f"⚠ **未找到满足全部一致性判据的区间** — 以下显示最佳折中结果。  \n"
                    f"p/p₀ = {best.p_min:.4f} – {best.p_max:.4f}（{best.n_points} 个数据点）  \n"
                    f"S_BET = {best.S_BET:.2f} ± {best.sigma_S_BET:.2f} m² g⁻¹ | C = {best.C:.1f} ± {best.sigma_C:.1f} | R² = {best.R2:.6f}"
                )

            # Compare with instrument range (matched by p/p₀, not sheet indices)
            if instrument_window is not None:
                diff_pct = abs(best.S_BET - instrument_window.S_BET) / instrument_window.S_BET * 100
                if diff_pct > 5:
                    st.warning(
                        f"⚠ 仪器区间的 S_BET = {instrument_window.S_BET:.3f} m² g⁻¹ "
                        f"与 Rouquerol 区间结果相差 {diff_pct:.1f}%。"
                        f"可考虑报告 Rouquerol 区间的结果。"
                    )
                else:
                    st.info(
                        f"仪器区间的 S_BET = {instrument_window.S_BET:.3f} m² g⁻¹ "
                        f"与 Rouquerol 结果的差异为 {diff_pct:.1f}%。"
                    )


# ── TAB 2: BET PLOT ─────────────────────────────────────────────────────────────────
with tab_bet:
    st.subheader("BET 线性图与回归分析")

    col_stats, col_fig = st.columns([1, 2])
    with col_stats:
        st.markdown("**回归参数**")
        st.table(pd.DataFrame({
            '参数': ['斜率', '截距', "R²", '单层饱和吸附量 Vm（计算值）', 'BET 常数 C（计算值）'],
            '数值': [
                f"{bet_res['slope']:.6f}",
                f"{bet_res['intercept']:.6f}",
                f"{bet_res['R2']:.6f}",
                f"{bet_res['Vm']:.4f}",
                f"{bet_res['C']:.2f}",
            ],
        }))
        st.markdown(
            f"所用数据点索引：**{s['start_pt']}** → **{s['end_pt']}** "
            f"（{s['end_pt'] - s['start_pt'] + 1} 个数据点）"
            + (" *（区间由数据确定，并非仪器设定值）*"
               if s.get("window_derived") else "")
        )
    with col_fig:
        _compare_link("bet")
        setup_plot_style()
        fig_bet, ax = plt.subplots(figsize=(5, 3.8))
        ax.scatter(bet_res["all_pts"][:, 0], bet_res["all_pts"][:, 1],
                   color="0.75", s=22, zorder=2, label='未参与拟合')
        ax.scatter(bet_res["x"], bet_res["y"],
                   color=C_BET, s=32, zorder=4, label='拟合数据点')
        x_fit = np.linspace(bet_res["x"].min(), bet_res["x"].max(), 200)
        ax.plot(x_fit, bet_res["slope"] * x_fit + bet_res["intercept"],
                "-", color=C_BET, lw=1.6)
        # Limit the axes to the fitted window (plus a 10% margin) so the
        # regression is inspectable on microporous isotherms, where the unused
        # points at high p/p0 would otherwise compress the fitted region to a
        # flat strip. The margin is derived from the fitted points, not a fixed
        # constant.
        x_lo = float(bet_res["x"].min())
        x_hi = float(bet_res["x"].max())
        x_margin = 0.1 * (x_hi - x_lo)
        # Relative pressure cannot be negative: keep the 10% margin but never
        # let the lower bound drop below zero.
        ax.set_xlim(max(x_lo - x_margin, 0.0), x_hi + x_margin)
        y_lo = float(bet_res["y"].min())
        y_hi = float(bet_res["y"].max())
        y_margin = 0.1 * (y_hi - y_lo)
        ax.set_ylim(y_lo - y_margin, y_hi + y_margin)
        ax.set_xlabel(r"$p/p_0$")
        ax.set_ylabel(r"$1/[V_a(p_0/p-1)]$ (g cm$^{-3}$)")
        ax.legend(fontsize=8)
        ax.text(0.05, 0.94, f"R² = {bet_res['R2']:.5f}",
                transform=ax.transAxes, va="top", fontsize=9)
        prepare_figure(fig_bet)
        with matplotlib_rendering():
            fig_bet.tight_layout()
        _show_figure(fig_bet)
        plt.close(fig_bet)


# ── TAB 3: LANGMUIR ─────────────────────────────────────────────────────────────────
with tab_langmuir:
    st.subheader("Langmuir（朗缪尔）比表面积")

    st.warning(
        "**Langmuir 模型解读：**\n\n"
        "Langmuir 模型假定在均一吸附位点上发生单层吸附。"
        "此处的 S_Langmuir 是补充表征参数，"
        "不能直接替代 S_BET。对于"
        "非均一表面、介孔或多层吸附体系，应谨慎解释结果。"
    )

    lang_valid = (
        np.isfinite(p_ads)
        & np.isfinite(n_ads)
        & (p_ads > 0)
        & (p_ads < 1)
        & (n_ads > 0)
    )
    p_lang = p_ads[lang_valid]
    n_lang = n_ads[lang_valid]

    if len(p_lang) < MIN_LANGMUIR_POINTS:
        st.error(
            "Langmuir 分析至少需要 3 个符合物理条件的吸附数据点，"
            "且满足 0 < p/p₀ < 1、吸附量为正。"
        )
    else:
        p_lo_data = float(np.min(p_lang))
        p_hi_data = float(np.max(p_lang))

        # Conservative default (0.05–0.30), clamped to the available range so the
        # slider never crashes when the data does not cover the classic window.
        default_lo, default_hi = _default_langmuir_range(p_lang)

        step = max(round((p_hi_data - p_lo_data) / 200, 4), 0.001)
        lang_lo, lang_hi = st.slider(
            "Langmuir 拟合区间（p/p₀）",
            min_value=p_lo_data,
            max_value=p_hi_data,
            value=detail_settings.get("langmuir_range", (default_lo, default_hi)),
            step=step,
            format="%.3f",
            key=f"langmuir_range_{detail_scope}" if detail_scope else None,
        )
        detail_settings["langmuir_range"] = (lang_lo, lang_hi)

        mask = (p_lang >= lang_lo - 1e-9) & (p_lang <= lang_hi + 1e-9)
        p_sel = p_lang[mask]
        n_sel = n_lang[mask]
        order = np.argsort(p_sel)
        p_sel = p_sel[order]
        n_sel = n_sel[order]

        if len(p_sel) < MIN_LANGMUIR_POINTS:
            st.warning(
                "所选相对压力区间内至少需要 3 个实测数据点，才能进行 Langmuir 拟合。"
            )
        else:
            try:
                result = fit_langmuir_window(
                    p_sel, n_sel,
                    has_hysteresis=iso_cls["has_hysteresis"],
                    has_plateau=iso_cls["has_plateau"],
                    S_BET=s["S_BET"],
                )
            except ValueError as e:
                st.error(f"Langmuir 拟合失败：{zh(e)}")
                result = None

            if result is not None:
                applicable = result.get("model_applicable", result.get("physical_fit", False))
                status = '通过' if applicable else '未通过'

                if applicable:
                    langmuir_result = result
                else:
                    st.warning(
                        "Langmuir 回归已完成，但该模型不适用于"
                        "此等温线（存在滞后环、缺少平台、"
                        "S_Langmuir 相对 S_BET 偏高或 R² 偏低），或者参数不符合物理条件。"
                        "该结果不会写入下载的 CSV 报告。"
                    )

                col_l1, col_l2 = st.columns([1, 2])
                with col_l1:
                    st.markdown("**Langmuir 拟合结果**")
                    st.table(pd.DataFrame({
                        '参数': [
                            '相对压力下限 p/p₀', '相对压力上限 p/p₀', '数据点数',
                            "Langmuir 比表面积 S_Langmuir", "单层饱和吸附量 nₘ", "吸附平衡常数 K", "决定系数 R²",
                            '模型适用性', '拟合状态',
                        ],
                        '数值': [
                            f"{result['p_min']:.4f}",
                            f"{result['p_max']:.4f}",
                            f"{result['n_points']}",
                            f"{result['S_Langmuir']:.2f} ± {result['sigma_S_Langmuir']:.2f} m² g⁻¹",
                            f"{result['n_m']:.2f} ± {result['sigma_n_m']:.2f} cm³(STP) g⁻¹",
                            f"{result['K']:.2f} ± {result['sigma_K']:.2f} (p/p0)⁻¹",
                            f"{result['R2']:.6f}",
                            "✓" if applicable else "✗",
                            status,
                        ],
                    }))

                with col_l2:
                    fig_lang = _plot_langmuir_linear(p_lang, n_lang, result)
                    _show_figure(fig_lang)
                    plt.close(fig_lang)

                st.divider()
                st.markdown("**与 BET 结果比较**")
                sbet_label = "S_BET" if not s.get("instrument_summary", True) else "仪器 S_BET"
                comp_rows = [
                    [sbet_label, _fmt(s.get("S_BET"), ".2f"), "—"],
                ]
                if use_rouquerol and rouquerol_result is not None and rouquerol_result["best"] is not None:
                    rb = rouquerol_result["best"]
                    comp_rows.append(
                        ["Rouquerol S_BET", f"{rb.S_BET:.2f}", f"{rb.sigma_S_BET:.2f}"]
                    )
                else:
                    comp_rows.append(["Rouquerol S_BET", "—", "—"])
                comp_rows.append(
                    ["S_Langmuir", f"{result['S_Langmuir']:.2f}", f"{result['sigma_S_Langmuir']:.2f}"]
                )
                comp_df = pd.DataFrame(
                    comp_rows,
                    columns=['方法', "比表面积（m² g⁻¹）", "不确定度（m² g⁻¹）"],
                )
                st.dataframe(comp_df, use_container_width=True, hide_index=True)
                st.caption(
                    "BET 与 Langmuir 比表面积基于不同的吸附模型假设；"
                    "结果是否一致，需要结合"
                    "等温线类型、孔结构和拟合质量判断。"
                    "若 S_Langmuir 比 S_BET 高出 20% 以上，或“模型适用性”为 ✗，表明"
                    "Langmuir 模型不适合描述此等温线。"
                )

                with st.expander("Langmuir 模型与方程"):
                    st.latex(r"n = n_m \frac{K(p/p_0)}{1 + K(p/p_0)}")
                    st.latex(r"\frac{p/p_0}{n} = \frac{1}{K n_m} + \frac{p/p_0}{n_m}")
                    st.latex(r"S_{\mathrm{Langmuir}} = n_m \times 4.353")


# ── TAB 4: ROUQUEROL ────────────────────────────────────────────────────────────────
with tab_rouquerol:
    st.subheader("Rouquerol BET 区间选择")

    if not use_rouquerol:
        st.info("请在左侧启用“按 Rouquerol 判据自动选择 BET 线性区间”。")
    elif rouquerol_result is None:
        st.warning("未能完成 Rouquerol 分析。")
    else:
        best = rouquerol_result["best"]
        if best is None:
            st.error("未找到可用的 BET 拟合区间。")
        else:
            col_r1, col_r2 = st.columns([1, 2])
            with col_r1:
                st.markdown("**所选区间**")
                st.table(pd.DataFrame({
                    '参数': ['相对压力下限 p/p₀', '相对压力上限 p/p₀', '数据点数', "BET 比表面积 S_BET", "单层饱和吸附量 Vm", "BET 常数 C", "决定系数 R²"],
                    '数值': [
                        f"{best.p_min:.4f}",
                        f"{best.p_max:.4f}",
                        f"{best.n_points}",
                        f"{best.S_BET:.2f} ± {best.sigma_S_BET:.2f} m² g⁻¹",
                        f"{best.Vm:.4f} cm³(STP) g⁻¹",
                        f"{best.C:.2f} ± {best.sigma_C:.2f}",
                        f"{best.R2:.6f}",
                    ],
                }))
                st.markdown(f"**已扫描候选区间数：** {rouquerol_result['n_candidates']}")
                st.markdown(f"**满足判据的区间数：** {rouquerol_result['n_valid']}")

            with col_r2:
                fig_rt = _plot_rouquerol_transform(p_ads, n_ads, best)
                _show_figure(fig_rt)
                plt.close(fig_rt)

            st.divider()
            st.markdown("**Rouquerol 一致性判据**")
            crit_df = pd.DataFrame({
                '判据': [
                    "C1：BET 常数 C > 0",
                    "C2：n(1−p/p₀) 随相对压力递增",
                    "C3：单层吸附量对应压力 p(nₘ) 位于所选区间内",
                    "C4：理论单层压力 1/(√C+1) 与实验值 p(nₘ) 一致",
                ],
                '状态': [
                    "✓" if best.c1_C_positive else "✗",
                    "✓" if best.c2_n1mp_increasing else "✗",
                    "✓" if best.c3_nm_in_range else "✗",
                    "✓" if best.c4_pm_consistency else "✗",
                ],
                '说明': [
                    f"C = {best.C:.2f}",
                    "检查所选区间内 n(1−p/p₀) 的单调性",
                    f"实验单层压力 pₘ = {best.pm_exp:.4f}",
                    f"理论单层压力 pₘ = {best.pm_theory:.4f}；允许偏差 ±20%",
                ],
            })
            st.dataframe(crit_df, use_container_width=True, hide_index=True)

            if heatmap_result is not None:
                st.divider()
                st.markdown("**BET 比表面积对选区的敏感性热图**")
                st.caption(
                    "每个单元格对应一个相对压力区间的 S_BET"
                    "（起点 × 终点）。彩色：满足 Rouquerol 判据；"
                    "灰色：未满足判据；蓝色虚线：所选区间。"
                )
                fig_hm = _plot_bet_heatmap(heatmap_result, best)
                _show_figure(fig_hm)
                plt.close(fig_hm)
                if heatmap_result["valid"].sum() <= 1:
                    st.info(
                        "仅找到一个满足 Rouquerol 判据的区间。"
                        "热图显示拟合区间唯一，无法利用多个有效区间"
                        "评估选区敏感性。"
                    )


            if instrument_window is not None:
                st.divider()
                st.markdown("**仪器区间与 Rouquerol 区间比较** （按相对压力匹配）")
                comp_df = pd.DataFrame({
                    '来源': ['仪器结果', "Rouquerol"],
                    '相对压力区间 p/p₀': [
                        f"{instrument_window.p_min:.4f} – {instrument_window.p_max:.4f}",
                        f"{best.p_min:.4f} – {best.p_max:.4f}",
                    ],
                    "S_BET (m² g⁻¹)": [
                        f"{instrument_window.S_BET:.2f} ± {instrument_window.sigma_S_BET:.2f}",
                        f"{best.S_BET:.2f} ± {best.sigma_S_BET:.2f}",
                    ],
                    "C": [
                        f"{instrument_window.C:.2f} ± {instrument_window.sigma_C:.2f}",
                        f"{best.C:.2f} ± {best.sigma_C:.2f}",
                    ],
                    "R²": [
                        f"{instrument_window.R2:.6f}",
                        f"{best.R2:.6f}",
                    ],
                    '是否满足判据': [
                        "✓" if instrument_window.valid else "✗",
                        "✓" if best.valid else "✗",
                    ],
                })
                st.dataframe(comp_df, use_container_width=True, hide_index=True)

            st.divider()
            st.markdown("**完整报告**")
            st.code(rouquerol_report_zh(rouquerol_result, sample_name), language=None)


# ── TAB 5: BJH / PSD ─────────────────────────────────────────────────────────────────
with tab_bjh:
    st.subheader("BJH 孔径分布")

    bjh = data["bjh"]

    if s.get("rp_peak_BJH") is not None:
        peak_diam = s["rp_peak_BJH"] * 2.0
        if peak_diam < BJH_NARROW_MESOPORE_NM:
            st.warning(
                f"⚠ BJH 峰值孔径（直径）为 {peak_diam:.1f} nm，小于 10 nm。"
                "基于 Kelvin 方程的 BJH 方法可能低估窄介孔"
                "孔径约 20%–30% (Thommes et al. 2015 §7.2, §9)."
            )

    if len(bjh) == 0:
        st.info("无法给出 BJH 孔径分布：输入未提供 BJH 表"
                "（仅含等温线数据）。")
    elif bjh.ndim != 2 or bjh.shape[1] < 4 or not np.isfinite(bjh[:, :4]).all():
        st.warning("BJH 表缺少完整有效的孔径分布、累积孔容或累积比表面积数据，无法生成完整双图。"
                   "请补充仪器报告；其他分析仍可使用，对比区可选择已有数据对应的图表。")
    else:
        # Instrument headers verified as radius ("rp/nm") and per-radius
        # differential ("dVp/drp"), so rp*2 = diameter and dV/dd = dV/dr / 2.
        rp   = bjh[:, 0] * 2           # radius (nm) -> diameter (nm)
        dVdd = bjh[:, 1] / 2.0         # dVp/drp -> dVp/ddp
        cum_Vp = bjh[:, 2]; cum_Sap = bjh[:, 3]

        link_psd, link_cumulative = st.columns(2)
        with link_psd:
            _compare_link("bjh_psd", "对比孔径分布 →")
        with link_cumulative:
            _compare_link("bjh_cumulative", "对比累积孔容 →")

        setup_plot_style()
        fig_bjh, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4))

        ax1.plot(rp, dVdd, "-", color=C_BJH, lw=1.5)
        ax1.fill_between(rp, dVdd, alpha=0.15, color=C_BJH)
        pk = np.argmax(dVdd)
        ax1.axvline(rp[pk], ls="--", lw=0.9, color=C_BJH, alpha=0.7)
        ax1.text(rp[pk]+0.3, dVdd[pk]*0.9, f"{rp[pk]:.1f} nm", fontsize=8, color=C_BJH)
        ax1.axvline(N2_CAVITATION_NM, ls=":", lw=0.8, color="0.6")
        ax1.set_xlabel("孔径（直径） (nm)")
        ax1.set_ylabel(r"d$V_p$/d$d_p$ (cm³ g⁻¹ nm⁻¹)")
        ax1.set_xlim(left=0); ax1.set_ylim(bottom=0)
        ax1.set_title("微分孔径分布")

        ax2r = ax2.twinx()
        ax2.plot(rp, cum_Vp,  "-",  color=C_CUM, lw=1.5, label='累积孔容 Vp')
        ax2r.plot(rp, cum_Sap, "--", color=C_BJH, lw=1.5, label='累积比表面积 Sap')
        ax2.set_xlabel("孔径（直径） (nm)")
        ax2.set_ylabel("累积孔容 (cm³ g⁻¹)", color=C_CUM)
        ax2r.set_ylabel("累积比表面积 (m² g⁻¹)", color=C_BJH)
        ax2.tick_params(axis="y", colors=C_CUM)
        ax2r.tick_params(axis="y", colors=C_BJH)
        ax2.set_xlim(left=0); ax2.set_ylim(bottom=0)
        ax2.set_title("累积孔容")
        l1, b1 = ax2.get_legend_handles_labels(); l2, b2 = ax2r.get_legend_handles_labels()
        ax2.legend(l1+l2, b1+b2, fontsize=8, loc="lower right")
        prepare_figure(fig_bjh)
        with matplotlib_rendering():
            fig_bjh.tight_layout()
        _show_figure(fig_bjh)
        plt.close(fig_bjh)

    if show_features and hyst_cls["type"] != "None":
        st.divider()
        st.markdown("**滞后环特征评分**")
        sc = hyst_cls["scores"]
        st.dataframe(
            pd.DataFrame([[k, v, "█"*v+"░"*(8-v)]
                          for k, v in sorted(sc.items(), key=lambda x: -x[1])],
                         columns=['类型', '得分', '得分条']),
            hide_index=True, use_container_width=False
        )
        st.markdown("**特征分析**")
        st.dataframe(
            pd.DataFrame([[zh(k), ("✓" if v is True else "✗" if v is False else zh(v))]
                          for k, v in hyst_cls["features"].items()],
                         columns=['特征', '数值']),
            hide_index=True, use_container_width=False
        )


# ── TAB 6: T-PLOT ──────────────────────────────────────────────────────────────────
with tab_tplot:
    if not show_tplot:
        st.info("请在左侧启用 t-plot 微孔分析。")
    else:
        st.subheader("t-plot（吸附膜厚度法）微孔分析")
        _compare_link("tplot")
        try:
            from tplot_analysis import LINE1_T_MIN, HJ_VALID_T_MAX

            # ── S_BET source for the decomposition ────────────────────────────
            if (use_rouquerol and rouquerol_result is not None
                    and rouquerol_result["best"] is not None):
                use_rq_sbet = st.checkbox(
                    "t-plot 分析采用 Rouquerol 的 S_BET",
                    value=detail_settings.get("tplot_rq", True),
                    key=f"tplot_rq_{detail_scope}" if detail_scope else None,
                    help=("BET 比表面积的选取会影响与外比表面积的比较。"
                          "采用满足 Rouquerol 判据的 S_BET，"
                          "可统一各项报告中 BET 比表面积的来源。"),
                )
                detail_settings["tplot_rq"] = use_rq_sbet

            # ── Adjustable fit window ─────────────────────────────────────────
            t_lo, t_hi = st.slider(
                "t-plot 拟合膜厚区间（Å）",
                min_value=LINE1_T_MIN, max_value=8.0,
                value=detail_settings.get("tplot_range", (LINE1_T_MIN, HJ_VALID_T_MAX)), step=0.1,
                key=f"tplot_range_{detail_scope}" if detail_scope else None,
                help=("双线段 t-plot 拟合区间。默认从第一线段的最低膜厚"
                      "（微孔填充区，p/p₀ ≈ 0.005）延伸至"
                      "第二线段的最高膜厚；第二线段限制在"
                      "Harkins–Jura 参考曲线的有效范围 3.5–6.5 Å 内。"),
            )

            detail_settings["tplot_range"] = (t_lo, t_hi)
            current_tplot = _sample_tplot(selection, use_rouquerol)
            tp, res = current_tplot["analyser"], current_tplot["result"]
            sbet_source = current_tplot["source"]
            tplot_result = {"result": res, "source": current_tplot["source"], "requested_range": (t_lo, t_hi)}

            # ── Sufficiency gate ─────────────────────────────────────────────
            if not res["micropore_analysis_possible"]:
                st.warning(
                    f"⚠ 无法进行微孔定量分析：{zh(res['micropore_analysis_reason'])}"
                )

            # ── Consistency warnings ──────────────────────────────────────────
            if res["n_points"] < 5:
                st.warning(
                    f"⚠ t-plot 在"
                    f"{res['t_range'][0]}–{res['t_range'][1]} Å 区间内仅使用 **{res['n_points']} 个数据点**；"
                    "少于约 5 个点时，R² 的参考意义有限。请扩大拟合区间，"
                    "或在 p/p₀ ≈ 0.08–0.30 区间补充测量。"
                )
            if res["S_ext_m2g"] > res["S_BET_m2g"]:
                over_pct = ((res["S_ext_m2g"] - res["S_BET_m2g"])
                            / res["S_BET_m2g"] * 100)
                st.warning(
                    f"⚠ 外比表面积 S_ext（{res['S_ext_m2g']:.2f} m² g⁻¹）高于 S_BET "
                    f"（{res['S_BET_m2g']:.2f} m² g⁻¹），超出 {over_pct:.1f}%。"
                    "需结合 BET 与 t-plot 的不确定度判断；"
                    "不应把该差异视为精确的微孔比表面积"
                    "分解结果。"
                )

            col_t1, col_t2 = st.columns([1, 2])
            with col_t1:
                st.markdown("**t-plot 分析结果**")

                def _fmt(v, spec):
                    return "—" if v is None else f"{v:{spec}}"

                st.table(pd.DataFrame({
                    '参数': ["BET 比表面积 S_BET", "总比表面积 S_total", "外比表面积 S_ext", "微孔比表面积 S_micro",
                                  "微孔孔容 V_micro", "介孔 + 大孔孔容 V_meso+macro", "2t（平均孔径估计值）"],
                    '数值': [
                        _fmt(res["S_BET_m2g"], ".2f"),
                        _fmt(res["S_total_m2g"], ".2f"),
                        _fmt(res["S_ext_m2g"], ".2f"),
                        _fmt(res["S_micro_m2g"], ".2f"),
                        _fmt(res["V_micro_cm3g"], ".4f"),
                        _fmt(res["V_meso_cm3g"], ".4f"),
                        _fmt(res["2t_nm"], ".3f"),
                    ],
                    '单位': ["m² g⁻¹", "m² g⁻¹", "m² g⁻¹", "m² g⁻¹",
                             "cm³ g⁻¹", "cm³ g⁻¹", "nm"],
                }))
                st.caption(
                    f"S_BET 来源：**{sbet_source}** · "
                    f"拟合区间：{res['t_range'][0]}–{res['t_range'][1]} Å "
                    f"（{res['n_points']} 个点）· 参考曲线：{zh(res['reference_curve'])}"
                )
                if res.get("warnings"):
                    st.warning("⚠ " + "；".join(zh(note) for note in res["warnings"]))
                if res.get("low_confidence"):
                    st.info(f"结果可信度较低：{zh(res['low_confidence_reason'])}")
            with col_t2:
                buf = io.BytesIO()
                tp.plot_tplot(save_path=buf, sample_name=sample_name,
                              t_min=t_lo, t_max=t_hi)
                buf.seek(0)
                st.image(buf, use_container_width=True)
        except ImportError:
            tplot_error = "t-plot 模块不可用"
            st.warning("未找到 tplot_analysis.py，t-plot 模块不可用。")
        except Exception as e:
            tplot_error = zh(e)
            st.error(f"t-plot 分析失败：{zh(e)}")


# ── TAB 7: DOWNLOAD ─────────────────────────────────────────────────────────────────
with tab_download:
    st.subheader("导出范围")
    st.write("上方“导出当前样品 CSV”包含本页当前参数、各 BET 来源及已运行的附加分析。批量 CSV 保留批次参数，两者独立。")
    st.write("四联图按需生成，包含等温线、原区间 BET、BJH 分布和累积孔容；不包含 Rouquerol 替换选区或 t-plot 图。")
    report_rows = [
        ['样品',              sample_name],
        ['BET 比表面积 S_BET (m²/g)',        s.get("S_BET")],
        ['单层饱和吸附量 Vm (cm³(STP)/g)',     s.get("Vm")],
        ['BET 常数 C',          s.get("C")],
        ['BET 常数 C 是否为正',             zh(bet_res["C_valid"])],
        ['决定系数 R²',                  bet_res['R2']],
        ['总孔容 Vp_total (cm³/g)',    s.get("Vp_total")],
        ['平均孔径（直径）dp_avg (nm)',         s.get("dp_avg")],
        ['BJH 比表面积 S_BJH (m²/g)',        s.get("S_BJH")],
        ['BJH 峰值孔径（直径）(nm)',  None if s.get("rp_peak_BJH") is None else s["rp_peak_BJH"] * 2],
        ['等温线类型',       zh(iso_cls["type"])],
        ['滞后环类型',     zh(hyst_cls["type"])],
        ['滞后环分类得分占比等级（非概率）', zh(hyst_cls.get("score_share", "—"))],
    ]
    if s.get('source_format') == 'SMP':
        report_rows.extend([
            ['数据来源', '直接读取 ASAP 2460 v3.01 SMP 原始等温线；本项目计算结果'],
            ['BET 区间来源', s.get('window_method', '默认压力范围')],
            ['仪器 BJH 报告', '未从 SMP 解码，需配套 XLS/XLSX'],
        ])
    if use_rouquerol and rouquerol_result is not None and rouquerol_result["best"] is not None:
        best = rouquerol_result["best"]
        report_rows.extend([
            ['Rouquerol 相对压力下限',  best.p_min],
            ['Rouquerol 相对压力上限',  best.p_max],
            ["Rouquerol S_BET",     f"{best.S_BET:.3f} ± {best.sigma_S_BET:.3f}"],
            ["Rouquerol C",         f"{best.C:.2f} ± {best.sigma_C:.2f}"],
            ['Rouquerol 决定系数 R²',        best.R2],
            ['Rouquerol 判据是否全部满足',     zh(best.valid)],
        ])
    if langmuir_result is not None:
        report_rows.extend([
            ['Langmuir 相对压力下限',  langmuir_result['p_min']],
            ['Langmuir 相对压力上限',  langmuir_result['p_max']],
            ['Langmuir 比表面积 (m²/g)',  langmuir_result['S_Langmuir']],
            ['Langmuir 比表面积不确定度 (m²/g)', langmuir_result['sigma_S_Langmuir']],
            ['Langmuir 单层饱和吸附量 n_m (cm³(STP)/g)', langmuir_result['n_m']],
            ['Langmuir 吸附平衡常数 K ((p/p0)^-1)', langmuir_result['K']],
            ['Langmuir 决定系数 R²',        langmuir_result['R2']],
            ['Langmuir 参数物理合理性', zh(langmuir_result["physical_fit"])],
        ])
    for _, source_row in bet_sources.iterrows():
        prefix = source_row["结果来源"]
        report_rows.extend([[f"{prefix} · {field}", source_row[field]] for field in bet_sources.columns[1:]])
    if tplot_result is not None:
        result = tplot_result["result"]
        report_rows.extend([
            ["t-plot 状态", "完成" if result["micropore_analysis_possible"] else "低压数据不足"],
            ["t-plot BET 来源", tplot_result["source"]],
            ["t-plot 设置膜厚下限 (Å)", tplot_result["requested_range"][0]],
            ["t-plot 设置膜厚上限 (Å)", tplot_result["requested_range"][1]],
            ["t-plot 实际膜厚下限 (Å)", result["t_range"][0]],
            ["t-plot 实际膜厚上限 (Å)", result["t_range"][1]],
            ["t-plot 参考曲线", result["reference_curve"]],
            ["t-plot 模型", result["model"]], ["t-plot 点数", result["n_points"]],
            ["t-plot BET 比表面积 (m²/g)", result["S_BET_m2g"]],
            ["t-plot 总比表面积 (m²/g)", result["S_total_m2g"]],
            ["t-plot 外比表面积 (m²/g)", result["S_ext_m2g"]],
            ["t-plot 微孔比表面积 (m²/g)", result["S_micro_m2g"]],
            ["t-plot 微孔孔容 (cm³/g)", result["V_micro_cm3g"]],
            ["t-plot 介孔与大孔孔容 (cm³/g)", result["V_meso_cm3g"]],
            ["t-plot 2t (nm)", result["2t_nm"]],
            ["t-plot 提示", "；".join(zh(v) for v in result.get("warnings", []))],
            ["t-plot 低可信度原因", zh(result.get("low_confidence_reason") or "无")],
            ["t-plot 微孔分析限制", zh(result.get("micropore_analysis_reason") or "无")],
        ])
    else:
        report_rows.append(["t-plot 状态", tplot_error or "未启用当前详情分析"])

    with detail_downloads:
        export_columns = st.columns(2)
        with export_columns[0]:
            st.download_button(
                label="导出当前样品 CSV", data=_batch_csv(pd.DataFrame(report_rows, columns=['参数','数值'])),
                file_name=f"{sample_name.replace(' ', '_')}_BET_report.csv", mime="text/csv",
            )
        with export_columns[1]:
            image_key = (detail_scope, sample_name)
            if st.button("生成四联图 PNG（300 dpi）", key="detail_png_generate"):
                before = set(plt.get_fignums())
                try:
                    with st.spinner("正在生成图像…"):
                        with matplotlib_rendering():
                            plot_all(data, iso_cls, hyst_cls, bet_res, sample_name, save=False)
                            st.session_state["detail_png"] = {
                                "key": image_key, "bytes": _fig_to_bytes(plt.gcf()),
                            }
                except Exception as exc:
                    st.warning(f"图像生成失败：{zh(exc)}。CSV 仍可下载。")
                finally:
                    with matplotlib_rendering():
                        for number in set(plt.get_fignums()) - before:
                            plt.close(number)
            saved = st.session_state.get("detail_png")
            if saved and saved["key"] == image_key:
                st.download_button(label="下载四联图 PNG", data=saved["bytes"],
                                   file_name=f"{sample_name.replace(' ', '_')}_BET_analysis.png", mime="image/png")

    st.divider()
    st.markdown("• **📚 引用本工具**")
    citation = (
        "Jafari, H. (2026). BET_analyser: Publication-Quality BET/BJH + T-Plot "
        "Analysis Tool (v3.0.0). Zenodo. DOI: 10.5281/zenodo.22116897"
    )
    st.code(citation, language=None)
