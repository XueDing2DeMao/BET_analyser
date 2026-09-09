"""基于公开合成样品构建 ASAP 报告，不保存用户测量数据。"""
from pathlib import Path
import numpy as np
import pandas as pd
from bet_analysis import read_bet_xls


def make_asap_frame(*, row_offset=0, col_offset=0):
    source = read_bet_xls(str(Path(__file__).parents[1] / "examples/reference_mesoporous.xlsx"))
    frame = pd.DataFrame(np.nan, index=range(len(source["ads"]) + 22 + row_offset), columns=range(22 + col_offset), dtype=object)

    def cell(row, col, value):
        frame.iat[row + row_offset, col + col_offset] = value

    summary = source["summary"]
    cell(1, 20, "Analysis adsorptive:")
    cell(1, 21, "N2")
    cell(0, 0, "Summary Report")
    for row, label, value in [
        (2, "BET Surface Area:", f"{summary['S_BET']} m²/g"),
        (4, "Single point adsorption total pore volume of pores", ""),
        (5, "less than 200 nm diameter at P/Po = 0.99:", f"{summary['Vp_total']} cm³/g"),
        (7, "Adsorption average pore diameter (4V/A by BET):", f"{summary['dp_avg']} nm"),
    ]:
        cell(row, 0, label)
        cell(row, 1, value)
    cell(0, 3, "Isotherm Linear Plot")
    for col, branch in [(3, "Adsorption"), (5, "Desorption")]:
        cell(2, col, "Synthetic : " + branch)
        cell(3, col, "Relative Pressure (P/Po)")
        cell(3, col+1, "Quantity Adsorbed (cm³/g STP)")
        for row, pair in enumerate(source["ads" if col == 3 else "des"], 4):
            cell(row, col, pair[0])
            cell(row, col+1, pair[1])
    cell(0, 8, "BET Report")
    for row, label, value in [(2, "BET surface area:", f"{summary['S_BET']} ± 0.1 m²/g"),
                               (3, "C:", str(summary["C"])),
                               (4, "Qm:", f"{summary['Vm']} cm³/g STP")]:
        cell(row, 8, label)
        cell(row, 9, value)
    for col, title in enumerate(["Relative Pressure (P/Po)", "Quantity Adsorbed (cm³/g STP)", "1/[Q(Po/P - 1)]"], 8):
        cell(6, col, title)
    selected = source["bet_pts"][summary["start_pt"]:summary["end_pt"]+1]
    for row, (p, y) in enumerate(selected, 7):
        for col, value in enumerate([p, p/(y*(1-p)), y], 8):
            cell(row, col, value)
    _write_bjh(cell, source["bjh"])
    return frame, source, selected


def _write_bjh(cell, bjh):
    cell(0, 12, "BJH Adsorption Pore Distribution Report")
    headers = ["Pore Diameter Range (nm)", "Average Diameter (nm)", "Incremental Pore Volume (cm³/g)",
               "Cumulative Pore Volume (cm³/g)", "Incremental Pore Area (m²/g)", "Cumulative Pore Area (m²/g)"]
    for col, title in enumerate(headers, 12):
        cell(3, col, title)
    cell(0, 19, "BJH Adsorption dV/dD Pore Volume")
    cell(3, 19, "Pore Diameter (nm)")
    cell(3, 20, "dV/dD Pore Volume (cm³/g·nm)")
    for row, (radius, derivative, volume, area) in enumerate(bjh, 4):
        for col, value in [(12, "range"), (13, 2*radius), (14, .01), (15, volume), (16, 1.),
                           (17, area), (19, 2*radius), (20, derivative/2)]:
            cell(row, col, value)


def save_asap_workbook(path, **kwargs):
    from openpyxl import Workbook
    frame, source, selected = make_asap_frame(**kwargs)
    book = Workbook()
    book.active.title = "ASAP 导出报告"
    for row in frame.itertuples(index=False, name=None):
        book.active.append([None if pd.isna(value) else value for value in row])
    book.save(path)
    return source, selected
