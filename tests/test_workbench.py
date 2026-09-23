"""工作台导航、结果快照、来源标记与当前参数导出。"""
from io import BytesIO
import hashlib

import pandas as pd
import pytest

from tests.test_batch_upload import ROOT, batch_app
from tests.test_chinese_exports import run_upload


def run_batch(monkeypatch):
    raw = (ROOT / "examples/reference_mesoporous.xlsx").read_bytes()
    files = [("A.xlsx", raw), ("B.xlsx", raw)]
    app, downloads = batch_app(monkeypatch, files)
    assert not app.exception
    return app, downloads, files


def test_options_update_results_and_display_toggle_is_independent(monkeypatch):
    app, downloads, _ = run_batch(monkeypatch)
    original = downloads["BET_batch_summary.csv"]
    next(c for c in app.checkbox if c.label == "显示 t-plot 微孔分析").uncheck().run()
    assert not app.exception
    assert downloads["BET_batch_summary.csv"] == original
    assert not any("待重新计算" in w.value for w in app.warning)
    next(c for c in app.checkbox if c.label.startswith("按 Rouquerol")).uncheck().run()
    assert downloads["BET_batch_summary.csv"] != original
    assert not any("待重新计算" in w.value for w in app.warning)
    assert not app.exception
    new = pd.read_csv(BytesIO(downloads["BET_batch_summary.csv"]))
    assert new["Rouquerol 状态"].eq("未启用").all()


def test_replacing_files_removes_previous_sample_details(monkeypatch):
    app, downloads, files = run_batch(monkeypatch)
    original = downloads["BET_batch_summary.csv"]
    files[:] = [("changed.csv", b"pressure,adsorbed\n0.1,1\n")]
    app.run()
    assert downloads["BET_batch_summary.csv"] != original
    assert not app.exception
    assert app.radio(key="analysis_mode").value == "样品分析"
    assert not app.tabs
    assert not any("当前分析文件：A" in h.value for h in app.subheader)
    assert not any("待重新计算" in w.value for w in app.warning)


def test_calculation_options_keep_current_file_and_comparison_selection(monkeypatch):
    raw = (ROOT / "examples/reference_mesoporous.xlsx").read_bytes()
    app, downloads = batch_app(monkeypatch, [(f"{name}.xlsx", raw) for name in "ABC"])
    detail = app.selectbox(key="batch_detail").options[2]
    app.selectbox(key="batch_detail").select(detail).run()
    next(c for c in app.checkbox if c.label.startswith("按 Rouquerol")).uncheck().run()
    assert app.selectbox(key="batch_detail").value == detail
    app.radio(key="analysis_mode").set_value("对比分析").run()
    samples = app.multiselect(key="comparison_samples").options[1:]
    app.multiselect(key="comparison_samples").set_value(samples).run()
    next(c for c in app.checkbox if c.label.startswith("按 Rouquerol")).check().run()
    assert not app.exception
    assert app.multiselect(key="comparison_samples").value == samples
    frame = pd.read_csv(BytesIO(downloads["BET_comparison_isotherm.csv"]))
    assert set(frame["文件"]) == {"B.xlsx", "C.xlsx"}
    app.radio(key="analysis_mode").set_value("样品分析").run()
    assert app.selectbox(key="batch_detail").value == detail


def test_batch_opens_original_analysis_and_comparison_has_its_own_area(monkeypatch):
    app, downloads, _ = run_batch(monkeypatch)
    assert app.radio(key="analysis_mode").options == ["样品分析", "对比分析"]
    assert app.radio(key="analysis_mode").value == "样品分析"
    assert len(app.tabs) == 7
    assert "A_BET_report.csv" in downloads
    assert len(app.sidebar.dataframe[0].value.columns) <= 10
    assert "提示" in app.sidebar.dataframe[0].value.columns
    assert not app.multiselect
    assert app.sidebar.selectbox(key="batch_detail")
    assert len(pd.read_csv(BytesIO(downloads["BET_batch_summary.csv"])).columns) > 20
    app.checkbox(key="batch_all_columns").check().run()
    assert len(app.sidebar.dataframe[0].value.columns) > 20
    app.radio(key="analysis_mode").set_value("对比分析").run()
    assert app.multiselect(key="comparison_samples")
    assert not app.tabs
    assert not app.exception


def test_batch_file_switch_uses_the_same_figures_as_single_file(monkeypatch):
    snapshots = []
    def capture(fig, **kwargs):
        fig.canvas.draw()
        snapshots.append(hashlib.sha256(fig.canvas.buffer_rgba()).hexdigest())
    monkeypatch.setattr("streamlit.pyplot", capture)
    raw = (ROOT / "examples/reference_mesoporous.xlsx").read_bytes()
    single = run_upload(monkeypatch, raw, "A.xlsx")
    assert not single.exception
    expected = snapshots[:]
    assert len(expected) == 6  # 包含 Rouquerol 灵敏度热图，不能静默丢图。
    snapshots.clear()
    app, downloads, _ = run_batch(monkeypatch)
    assert snapshots == expected
    choices = app.selectbox(key="batch_detail").options
    snapshots.clear()
    downloads.clear()
    app.selectbox(key="batch_detail").select(choices[2]).run()
    assert not app.exception
    assert "B_BET_report.csv" in downloads
    assert "A_BET_report.csv" not in downloads
    assert snapshots == expected
    app.radio(key="analysis_mode").set_value("对比分析").run()
    app.radio(key="analysis_mode").set_value("样品分析").run()
    assert app.selectbox(key="batch_detail").value == choices[2]


def test_current_tplot_parameters_and_sources_are_exported(monkeypatch):
    downloads = {}
    monkeypatch.setattr("streamlit.download_button", lambda **kw: downloads.update({kw["file_name"]: kw["data"]}))
    raw = (ROOT / "examples/reference_mesoporous.xlsx").read_bytes()
    app = run_upload(monkeypatch, raw, "当前样品.xlsx")
    next(s for s in app.slider if s.label.startswith("t-plot")).set_value((3.5, 5.5)).run()
    next(c for c in app.checkbox if c.label == "t-plot 分析采用 Rouquerol 的 S_BET").uncheck().run()
    assert not app.exception
    report = pd.read_csv(BytesIO(downloads["当前样品_BET_report.csv"])).set_index("参数")["数值"]
    assert float(report["t-plot 设置膜厚下限 (Å)"]) == pytest.approx(3.5)
    assert float(report["t-plot 设置膜厚上限 (Å)"]) == pytest.approx(5.5)
    assert report["t-plot BET 来源"] == "仪器/模板报告"
    assert "t-plot 微孔孔容 (cm³/g)" in report
    source = next(df.value for df in app.dataframe if "结果来源" in df.value.columns)
    assert set(source["结果来源"]) == {"仪器/模板报告", "原区间重算", "Rouquerol 自动选区"}
    assert "适用状态" in source


def test_publication_figure_is_generated_only_on_request(monkeypatch):
    import bet_analysis
    original = bet_analysis.plot_all
    calls = []

    def plot(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(bet_analysis, "plot_all", plot)
    downloads = {}
    monkeypatch.setattr("streamlit.download_button", lambda **kw: downloads.update({kw["file_name"]: kw["data"]}))
    raw = (ROOT / "examples/reference_mesoporous.xlsx").read_bytes()
    app = run_upload(monkeypatch, raw, "图表.xlsx")
    assert not calls
    app.button(key="detail_png_generate").click().run()
    assert not app.exception
    assert len(calls) == 1
    assert downloads["图表_BET_analysis.png"].startswith(b"\x89PNG")
    app.run()
    assert len(calls) == 1


def test_navigation_keeps_sample_parameters_and_comparison_branch(monkeypatch):
    app, downloads, _ = run_batch(monkeypatch)
    choices = app.selectbox(key="batch_detail").options
    app.selectbox(key="batch_detail").select(choices[1]).run()
    next(s for s in app.slider if s.label.startswith("t-plot")).set_value((3.5, 5.5)).run()
    next(c for c in app.checkbox if c.label == "t-plot 分析采用 Rouquerol 的 S_BET").uncheck().run()
    report = downloads["A_BET_report.csv"]
    app.radio(key="analysis_mode").set_value("对比分析").run()
    app.radio(key="analysis_mode").set_value("样品分析").run()
    assert downloads["A_BET_report.csv"] == report
    next(c for c in app.checkbox if c.label == "显示 t-plot 微孔分析").uncheck().run()
    assert not app.exception
    next(c for c in app.checkbox if c.label == "显示 t-plot 微孔分析").check().run()
    assert downloads["A_BET_report.csv"] == report
    app.selectbox(key="batch_detail").select(choices[2]).run()
    assert next(s for s in app.slider if s.label.startswith("t-plot")).value != (3.5, 5.5)
    app.selectbox(key="batch_detail").select(choices[1]).run()
    assert downloads["A_BET_report.csv"] == report
    app.radio(key="analysis_mode").set_value("对比分析").run()
    app.radio(key="comparison_branch").set_value("仅脱附").run()
    app.radio(key="analysis_mode").set_value("样品分析").run()
    app.radio(key="analysis_mode").set_value("对比分析").run()
    assert app.radio(key="comparison_branch").value == "仅脱附"
    assert not app.exception


def test_negative_report_values_remain_numbers(monkeypatch):
    from streamlit.testing.v1 import AppTest
    downloads = {}
    monkeypatch.setattr("streamlit.download_button", lambda **kw: downloads.update({kw["file_name"]: kw["data"]}))
    AppTest.from_file(str(ROOT / "app_bet.py")).run()
    raw = downloads["BET_template.csv"].replace(b"120.5", b"-90.1")
    app = run_upload(monkeypatch, raw, "=negative.csv")
    assert not app.exception
    report = pd.read_csv(BytesIO(downloads["=negative_BET_report.csv"])).set_index("参数")["数值"]
    assert float(report["BET 常数 C"]) == pytest.approx(-90.1)
    assert report["样品"].startswith("'=negative")
    source = next(df.value for df in app.dataframe if "结果来源" in df.value.columns)
    assert source.iloc[0]["适用状态"] == "不适用：C ≤ 2"
