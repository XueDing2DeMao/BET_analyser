"""批量导入、失败隔离、结果快照和完整下载流程。"""
from io import BytesIO, StringIO
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from tests.asap_fixture import save_asap_workbook
from tests.smp_fixture import make_smp


ROOT = Path(__file__).resolve().parents[1]


def batch_app(monkeypatch, files):
    downloads = {}

    def upload(*args, **kwargs):
        if not kwargs.get("accept_multiple_files"):
            return None
        values = []
        for name, content in files:
            value = BytesIO(content)
            value.name = name
            values.append(value)
        return values

    monkeypatch.setattr("streamlit.file_uploader", upload)
    monkeypatch.setattr(
        "streamlit.download_button",
        lambda **kw: downloads.update({kw["file_name"]: kw["data"]}),
    )
    app = AppTest.from_file(str(ROOT / "app_bet.py"), default_timeout=90).run()
    return app, downloads


def start(app):
    assert [] == [e.message for e in app.exception]
    assert not any(c.key == "batch_mode" for c in app.checkbox)
    assert not any(b.key == "batch_start" for b in app.button)
    return pd.DataFrame([item["row"] for item in app.session_state["bet_batch"]["results"]])


def test_mixed_batch_keeps_valid_samples_when_one_file_fails(monkeypatch, tmp_path):
    path = tmp_path / "asap.xlsx"
    save_asap_workbook(path)
    smp, _ = make_smp()
    files = [
        ("仪器.XLSX", path.read_bytes()),
        ("原始.SMP", smp),
        ("HKUST.csv", (ROOT / "examples/betsi_HKUST-1.csv").read_bytes()),
        ("损坏.csv", b"pressure,adsorbed\n0.1,1\n"),
    ]
    app, downloads = batch_app(monkeypatch, files)
    assert "BET_batch_summary.csv" in downloads
    rows = start(app)
    assert [f[0] for f in files] == rows["文件"].tolist()
    assert rows["状态"].iloc[:3].str.startswith("完成").all()
    assert "失败" == rows["状态"].iloc[3]
    assert "至少需要 5 个数据点" in rows["提示"].iloc[3]
    assert 1556 == pytest.approx(rows["Rouquerol 比表面积 (m²/g)"].iloc[2], rel=.011)
    assert "是" == rows["Rouquerol 判据全部满足"].iloc[2]
    assert pd.isna(rows["BJH 比表面积 (m²/g)"].iloc[1])
    assert "未提供" == rows["BJH 数据"].iloc[1]
    assert b"\xef\xbb\xbf" == downloads["BET_batch_summary.csv"][:3]
    exported = pd.read_csv(StringIO(downloads["BET_batch_summary.csv"].decode("utf-8-sig")))
    assert rows["文件"].tolist() == exported["文件"].tolist()
    assert rows["状态"].tolist() == exported["状态"].tolist()
    assert "t-plot 微孔孔容 (cm³/g)" in exported.columns
    assert "Langmuir 状态" in exported.columns


def test_upload_analyzes_automatically_and_clearing_removes_results(monkeypatch):
    original = (ROOT / "examples/betsi_HKUST-1.csv").read_bytes()
    files = [("sample.csv", original)]
    app, downloads = batch_app(monkeypatch, files)
    rows = start(app)
    calls = []
    monkeypatch.setattr("rouquerol.select_bet_range", lambda *a, **kw: calls.append(1))
    app.run()
    assert not calls
    assert rows[app.sidebar.dataframe[0].value.columns].equals(app.sidebar.dataframe[0].value)
    files[0] = ("sample.csv", b"pressure,adsorbed\n0.1,1\n")
    downloads.clear()
    app.run()
    assert "失败" == start(app)["状态"].iloc[0]
    assert len(app.tabs) == 0
    assert "BET_batch_summary.csv" in downloads
    assert not any("待重新计算" in item.value for item in app.warning)
    downloads.clear()
    files.clear()
    app.run()
    assert len(app.dataframe) == 0
    assert "bet_batch" not in app.session_state
    assert "BET_batch_summary.csv" not in downloads


def test_analysis_options_apply_automatically(monkeypatch):
    files = [("reference.xlsx", (ROOT / "examples/reference_mesoporous.xlsx").read_bytes())]
    app, downloads = batch_app(monkeypatch, files)
    start(app)
    option = next(c for c in app.checkbox if c.label.startswith("按 Rouquerol"))
    downloads.clear()
    option.uncheck().run()
    assert len(app.tabs) == 7
    assert "BET_batch_summary.csv" in downloads
    assert not any("待重新计算" in item.value for item in app.warning)
    rows = start(app)
    assert "未启用" == rows["Rouquerol 状态"].iloc[0]
    assert "Rouquerol 比表面积 (m²/g)" not in rows or pd.isna(rows["Rouquerol 比表面积 (m²/g)"].iloc[0])


def test_batch_zip_preserves_duplicate_names_and_detail_view(monkeypatch):
    data = (ROOT / "examples/reference_mesoporous.xlsx").read_bytes()
    files = [("../同名.XLSX", data), ("../同名.XLSX", data), ("bad.csv", b"bad")]
    app, downloads = batch_app(monkeypatch, files)
    start(app)
    app.button(key="batch_zip").click().run()
    assert [] == [e.message for e in app.exception]
    with ZipFile(BytesIO(downloads["BET_batch_results.zip"])) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert all(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts for name in names)
        assert 2 == sum(name.endswith(".png") for name in names)
        reports = [name for name in names if name.endswith("/分析报告.csv")]
        assert 2 == len(reports)
        assert reports[0].split("/")[0] != reports[1].split("/")[0]
        assert "批量汇总.csv" in names
        assert "失败记录.csv" in names
        for name in names:
            if name.endswith(".png"):
                assert b"\x89PNG\r\n\x1a\n" == archive.read(name)[:8]
        report = pd.read_csv(BytesIO(archive.read(reports[0])))
        assert "BET 比表面积 (m²/g)" in report["参数"].values
        area = float(report.loc[report["参数"] == "BET 比表面积 (m²/g)", "数值"].iloc[0])
        assert 177.279 == pytest.approx(area, abs=.001)
    selection = app.selectbox(key="batch_detail")
    selection.select(selection.options[1]).run()
    assert [] == [e.message for e in app.exception]
    assert 7 == len(app.tabs)


def test_batch_accepts_sectioned_csv_template(monkeypatch):
    files = []
    app, downloads = batch_app(monkeypatch, files)
    files.append(("模板.csv", downloads["BET_template.csv"]))
    app.run()
    rows = start(app)
    assert rows["状态"].iloc[0].startswith("完成")
    assert 95.3 == rows["BET 比表面积 (m²/g)"].iloc[0]
    assert 21.9 == rows["BET 单层容量 (cm³(STP)/g)"].iloc[0]
    assert 120.5 == rows["BET C"].iloc[0]
    assert 12.667 == pytest.approx(rows["BET 重算单层容量 (cm³(STP)/g)"].iloc[0], abs=.001)
    assert "报告参数：" in rows["提示"].iloc[0]


def test_all_failed_batch_still_exports_diagnostics(monkeypatch):
    files = [("bad.csv", b"bad"), ("unknown.smp", b"not smp")]
    app, downloads = batch_app(monkeypatch, files)
    rows = start(app)
    assert ["失败", "失败"] == rows["状态"].tolist()
    assert rows["提示"].str.len().gt(0).all()
    assert app.button(key="batch_zip").disabled
    assert "BET_batch_summary.csv" in downloads
    assert 0 == len(app.tabs)


def test_optional_analysis_failure_preserves_bet_and_csv_text(monkeypatch):
    # 仅高压点的数据仍可回归 BET，但不足以完成默认 t-plot。
    raw = b"pressure,quantity (cm3/g STP)\n0.6,10\n0.7,14\n0.8,21\n0.9,42\n0.99,430\n"
    app, downloads = batch_app(monkeypatch, [("=sample.csv", raw)])
    rows = start(app)
    assert rows["状态"].iloc[0].startswith("完成")
    assert "未能确定" == rows["t-plot 状态"].iloc[0]
    assert "t-plot" in rows["提示"].iloc[0]
    assert pd.notna(rows["BET 比表面积 (m²/g)"].iloc[0])
    exported = pd.read_csv(BytesIO(downloads["BET_batch_summary.csv"]))
    assert "'=sample.csv" == exported["文件"].iloc[0]
    assert "=sample.csv" == rows["文件"].iloc[0]


def test_plot_failure_does_not_drop_reports_or_other_images(monkeypatch):
    import bet_analysis
    import matplotlib.pyplot as plt
    original = bet_analysis.plot_all
    calls = []

    def plot(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            plt.figure()
            raise RuntimeError("模拟单个图像失败")
        return original(*args, **kwargs)

    monkeypatch.setattr(bet_analysis, "plot_all", plot)
    raw = (ROOT / "examples/reference_mesoporous.xlsx").read_bytes()
    app, downloads = batch_app(monkeypatch, [("one.xlsx", raw), ("two.xlsx", raw)])
    start(app)
    before = plt.get_fignums()
    app.button(key="batch_zip").click().run()
    assert [] == [e.message for e in app.exception]
    assert before == plt.get_fignums()
    with ZipFile(BytesIO(downloads["BET_batch_results.zip"])) as archive:
        assert 2 == sum(name.endswith("/分析报告.csv") for name in archive.namelist())
        assert 1 == sum(name.endswith(".png") for name in archive.namelist())
        assert "图像生成失败记录.csv" in archive.namelist()
    assert any("1 个图像生成失败" in warning.value for warning in app.warning)


def test_nonfinite_bet_is_failed_and_excluded_from_detail(monkeypatch):
    raw = b"pressure,adsorbed\n0.05,0\n0.10,0\n0.15,0\n0.20,0\n0.30,0\n"
    good = (ROOT / "examples/reference_mesoporous.xlsx").read_bytes()
    app, downloads = batch_app(monkeypatch, [("zero.csv", raw), ("good.xlsx", good)])
    rows = start(app)
    assert "失败" == rows["状态"].iloc[0]
    assert "BET" in rows["提示"].iloc[0]
    assert rows["状态"].iloc[1].startswith("完成")
    assert not any("zero.csv" in option for option in app.selectbox(key="batch_detail").options)


def test_detail_settings_do_not_leak_between_samples(monkeypatch):
    raw = (ROOT / "examples/reference_mesoporous.xlsx").read_bytes()
    app, _ = batch_app(monkeypatch, [("A.xlsx", raw), ("B.xlsx", raw)])
    start(app)
    select = app.selectbox(key="batch_detail")
    select.select(select.options[1]).run()
    next(s for s in app.slider if s.label.startswith("Langmuir")).set_value((.1, .4)).run()
    next(s for s in app.slider if s.label.startswith("t-plot")).set_value((3.5, 5.5)).run()
    next(c for c in app.checkbox if c.label == "t-plot 分析采用 Rouquerol 的 S_BET").uncheck().run()
    select = app.selectbox(key="batch_detail")
    select.select(select.options[2]).run()
    assert [] == [e.message for e in app.exception]
    assert (.05, .3) == next(s.value for s in app.slider if s.label.startswith("Langmuir"))
    assert (2.4, 6.5) == next(s.value for s in app.slider if s.label.startswith("t-plot"))
    assert next(c.value for c in app.checkbox if c.label == "t-plot 分析采用 Rouquerol 的 S_BET")
