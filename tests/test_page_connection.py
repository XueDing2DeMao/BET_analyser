"""样品详情和单图对比往返、文件集合变化与 t-plot 参数一致性。"""
from io import BytesIO

import numpy as np
import pandas as pd
import pytest

from tests.test_batch_upload import ROOT, batch_app
from tplot_analysis import TPlotAnalyser


def workbench(monkeypatch):
    raw = (ROOT / "examples/reference_mesoporous.xlsx").read_bytes()
    files = [(f"{name}.xlsx", raw) for name in "ABC"]
    app, downloads = batch_app(monkeypatch, files)
    return app, downloads, files


@pytest.mark.parametrize("kind,title,tab", [
    ("isotherm", "吸附–脱附等温线", "📊 总览"),
    ("bet", "BET 拟合", "BET"),
    ("bjh_psd", "BJH 孔径分布", "BJH"),
    ("bjh_cumulative", "BJH 累积孔容", "BJH"),
    ("tplot", "t-plot", "t-plot"),
])
def test_chart_links_open_matching_comparison_and_sample_tab(monkeypatch, kind, title, tab):
    app, downloads, _ = workbench(monkeypatch)
    app.button(key=f"compare_{kind}").click().run()
    assert not app.exception
    assert app.radio(key="analysis_mode").value == "对比分析"
    assert app.radio(key="comparison_kind").value == title
    selected = app.multiselect(key="comparison_samples").value
    target = app.selectbox(key="comparison_detail").options[1]
    app.selectbox(key="comparison_detail").select(target).run()
    app.button(key="comparison_open_detail").click().run()
    assert not app.exception
    assert app.selectbox(key="batch_detail").value == target
    scope = app.session_state["bet_batch"]["results"][1]["scope"]
    assert app.session_state[f"detail_tab_{scope}"] == tab
    app.radio(key="analysis_mode").set_value("对比分析").run()
    assert app.multiselect(key="comparison_samples").value == selected
    assert app.radio(key="comparison_kind").value == title
    assert f"BET_comparison_{kind}.png" in downloads


def test_file_add_remove_reorder_keeps_selected_identities_and_colors(monkeypatch):
    figures = []
    monkeypatch.setattr("streamlit.pyplot", lambda fig, **kw: figures.append(fig))
    app, downloads, files = workbench(monkeypatch)
    app.radio(key="analysis_mode").set_value("对比分析").run()
    options = app.multiselect(key="comparison_samples").options
    app.multiselect(key="comparison_samples").set_value(options[1:]).run()
    colors = [line.get_color() for line in figures[-1].axes[0].lines[::2]]
    files[:] = [files[2], files[1], ("D.xlsx", files[0][1])]
    app.run()
    assert not app.exception
    selected = app.multiselect(key="comparison_samples").value
    assert {label.split(" · ", 1)[1] for label in selected} == {"B.xlsx", "C.xlsx"}
    frame = pd.read_csv(BytesIO(downloads["BET_comparison_isotherm.csv"]))
    assert set(frame["文件"]) == {"B.xlsx", "C.xlsx"}
    plotted = {line.get_label().split(" · ")[1]: line.get_color()
               for line in figures[-1].axes[0].lines[::2]}
    assert plotted == {"B": colors[0], "C": colors[1]}
    files.pop(1)
    downloads.clear()
    app.run()
    assert len(app.multiselect(key="comparison_samples").value) == 1
    assert "BET_comparison_isotherm.png" not in downloads


def test_tplot_comparison_uses_saved_detail_parameters_and_exact_fit(monkeypatch):
    app, downloads, _ = workbench(monkeypatch)
    app.selectbox(key="batch_detail").select(app.selectbox(key="batch_detail").options[2]).run()
    next(s for s in app.slider if s.label.startswith("t-plot")).set_value((3.5, 5.5)).run()
    next(c for c in app.checkbox if c.label == "t-plot 分析采用 Rouquerol 的 S_BET").uncheck().run()
    app.button(key="compare_tplot").click().run()
    assert not app.exception
    parameters = next(df.value for df in app.dataframe
                      if "参考曲线" in df.value.columns and "曲线" not in df.value.columns)
    b = parameters.set_index("文件").loc["B.xlsx"]
    assert b["设置膜厚下限 (Å)"] == pytest.approx(3.5)
    assert b["设置膜厚上限 (Å)"] == pytest.approx(5.5)
    assert b["BET 来源"] == "仪器/模板报告"
    data = app.session_state["bet_batch"]["results"][1]["data"]
    tp = TPlotAnalyser(*data["ads"].T, data["summary"]["S_BET"],
                      data["summary"]["Vp_total"], c_constant=data["summary"]["C"])
    res = tp.full_tplot_report(t_min=3.5, t_max=5.5)
    assert b["BET 比表面积 (m²/g)"] == pytest.approx(res["S_BET_m2g"])
    frame = pd.read_csv(BytesIO(downloads["BET_comparison_tplot.csv"]))
    points = frame[(frame["文件"] == "B.xlsx") & (frame["曲线"] == "t-plot 数据点")]
    order = np.argsort(tp.t)
    np.testing.assert_allclose(points["统计膜厚 t (Å)"], tp.t[order])
    np.testing.assert_allclose(points["吸附量 (cm³/g STP)"], tp.v[order])
    single_line = res["model"] == "single_line"
    fit_label = "总比表面积拟合线" if single_line else "外比表面积拟合线"
    fit = frame[(frame["文件"] == "B.xlsx") & (frame["曲线"] == fit_label)]
    assert len(fit) > 0
    assert b["模型"] == res["model"]
    np.testing.assert_allclose(fit["吸附量 (cm³/g STP)"],
                               (res["slope_1"] if single_line else res["slope_2"]) * fit["统计膜厚 t (Å)"]
                               + (0 if single_line else res["intercept_2"]))
    a = parameters.set_index("文件").loc["A.xlsx"]
    assert a["设置膜厚下限 (Å)"] == pytest.approx(2.4)
    assert a["设置膜厚上限 (Å)"] == pytest.approx(6.5)
    # 已经绘制过对比图后，再从详情修改参数，不能继续使用旧缓存。
    app.selectbox(key="comparison_detail").select("002 · B.xlsx").run()
    app.button(key="comparison_open_detail").click().run()
    next(s for s in app.slider if s.label.startswith("t-plot")).set_value((3.5, 6.0)).run()
    app.radio(key="analysis_mode").set_value("对比分析").run()
    assert not app.exception
    updated = pd.read_csv(BytesIO(downloads["BET_comparison_tplot.csv"]))
    assert updated.loc[updated["文件"] == "B.xlsx", "设置膜厚上限 (Å)"].eq(6.0).all()
    assert updated.loc[updated["文件"] == "A.xlsx", "设置膜厚上限 (Å)"].eq(6.5).all()


def test_failed_tplot_does_not_hide_other_curves_or_detail_link(monkeypatch):
    raw = (ROOT / "examples/reference_mesoporous.xlsx").read_bytes()
    high = b"pressure,quantity (cm3/g STP)\n0.6,10\n0.7,14\n0.8,21\n0.9,42\n0.99,430\n"
    app, downloads = batch_app(monkeypatch, [("high.csv", high), ("A.xlsx", raw), ("B.xlsx", raw)])
    app.radio(key="analysis_mode").set_value("对比分析").run()
    app.radio(key="comparison_kind").set_value("t-plot").run()
    assert not app.exception
    assert any("high.csv" in w.value for w in app.warning)
    frame = pd.read_csv(BytesIO(downloads["BET_comparison_tplot.csv"]))
    assert set(frame["文件"]) == {"A.xlsx", "B.xlsx"}
    assert app.button(key="comparison_open_detail")


def test_reordering_same_named_files_keeps_detail_target_identity(monkeypatch):
    raw = (ROOT / "examples/reference_mesoporous.xlsx").read_bytes()
    # 名称相同、内容签名不同；第二份仍是有效 Excel（末尾留白）。
    files = [("same.xlsx", raw), ("same.xlsx", raw + b"\n")]
    app, _ = batch_app(monkeypatch, files)
    app.radio(key="analysis_mode").set_value("对比分析").run()
    target_scope = app.session_state["bet_batch"]["results"][1]["scope"]
    app.selectbox(key="comparison_detail").select("002 · same.xlsx").run()
    files.reverse()
    app.run()
    assert not app.exception
    assert app.selectbox(key="comparison_detail").value == "001 · same.xlsx"
    app.button(key="comparison_open_detail").click().run()
    assert not app.exception
    assert app.selectbox(key="batch_detail").value == "001 · same.xlsx"
    assert app.session_state["bet_batch"]["results"][0]["scope"] == target_scope
