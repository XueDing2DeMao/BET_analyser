"""独立对比功能区的文件筛选、原有绘图风格、曲线数值与导出。"""
from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from bet_analysis import read_bet_xls, verify_bet
from tests.test_batch_upload import ROOT, batch_app, start as start_batch
from tests.asap_fixture import make_asap_frame


def start(app):
    app.radio(key="analysis_mode").set_value("对比分析").run()
    rows = start_batch(app)
    assert not app.exception
    return rows


@pytest.fixture
def comparison(monkeypatch):
    raw = (ROOT / "examples/reference_mesoporous.xlsx").read_bytes()
    files = [("样品甲.xlsx", raw), ("样品乙.xlsx", raw), ("损坏.csv", b"bad")]
    figures = []
    monkeypatch.setattr("streamlit.pyplot", lambda fig, **kw: figures.append(fig))
    app, downloads = batch_app(monkeypatch, files)
    start(app)
    return app, downloads, figures, files


def comparison_csv(downloads, kind="isotherm"):
    return pd.read_csv(BytesIO(downloads[f"BET_comparison_{kind}.csv"]))


def test_isotherms_overlay_successful_samples_and_export_exact_points(comparison):
    app, downloads, figures, _ = comparison
    assert len(app.multiselect) == 1
    assert len(app.multiselect[0].value) == 2
    assert all("损坏" not in option for option in app.multiselect[0].options)
    lines = figures[-1].axes[0].lines
    assert len(lines) == 4
    assert lines[0].get_color() == lines[1].get_color()
    assert lines[2].get_color() == lines[3].get_color()
    assert lines[0].get_color() != lines[2].get_color()
    assert lines[0].get_linestyle() != lines[1].get_linestyle()
    data = read_bet_xls(str(ROOT / "examples/reference_mesoporous.xlsx"))
    frame = comparison_csv(downloads)
    assert set(frame["文件"]) == {"样品甲.xlsx", "样品乙.xlsx"}
    for number in (1, 2):
        for branch, key in (("吸附支", "ads"), ("脱附支", "des")):
            points = frame[(frame["序号"] == number) & (frame["曲线"] == branch)]
            expected = data[key][np.argsort(data[key][:, 0])]
            np.testing.assert_allclose(points.iloc[:, -2:].to_numpy(), expected)
    assert downloads["BET_comparison_isotherm.png"].startswith(b"\x89PNG\r\n\x1a\n")
    assert not plt.fignum_exists(figures[-1].number)


def test_selection_changes_curves_keeps_colors_and_can_be_cleared(comparison):
    app, downloads, figures, files = comparison
    files.insert(2, ("样品丙.xlsx", files[0][1]))
    app.run()
    start(app)
    original_color = figures[-1].axes[0].lines[2].get_color()
    choices = app.multiselect(key="comparison_samples")
    choices.set_value(choices.options[1:]).run()
    assert not app.exception
    assert set(comparison_csv(downloads)["序号"]) == {2, 3}
    assert figures[-1].axes[0].lines[0].get_color() == original_color
    for values in ([], [choices.options[0]]):
        downloads.clear()
        count = len(figures)
        app.multiselect(key="comparison_samples").set_value(values).run()
        assert not app.exception
        assert len(figures) == count
        assert "BET_comparison_isotherm.png" not in downloads
        assert any("至少选择 2 个" in info.value for info in app.info)


@pytest.mark.parametrize("label,kind,column,scale", [
    ("BJH 孔径分布", "bjh_psd", 1, 0.5),
    ("BJH 累积孔容", "bjh_cumulative", 2, 1.0),
])
def test_bjh_compares_diameter_and_preserves_units(comparison, label, kind, column, scale):
    app, downloads, figures, _ = comparison
    app.radio(key="comparison_kind").set_value(label).run()
    assert not app.exception
    bjh = read_bet_xls(str(ROOT / "examples/reference_mesoporous.xlsx"))["bjh"]
    order = np.argsort(bjh[:, 0])
    frame = comparison_csv(downloads, kind)
    assert len(figures[-1].axes[0].lines) == 2
    for number in (1, 2):
        points = frame[frame["序号"] == number]
        np.testing.assert_allclose(points.iloc[:, -2], bjh[order, 0] * 2)
        np.testing.assert_allclose(points.iloc[:, -1], bjh[order, column] * scale)


def test_bet_uses_each_original_fit_window_and_regression(comparison):
    app, downloads, figures, _ = comparison
    app.radio(key="comparison_kind").set_value("BET 拟合").run()
    assert not app.exception
    data = read_bet_xls(str(ROOT / "examples/reference_mesoporous.xlsx"))
    bet = verify_bet(data["bet_pts"], data["summary"])
    frame = comparison_csv(downloads, "bet")
    points = frame[(frame["序号"] == 1) & (frame["曲线"] == "BET 数据点")]
    np.testing.assert_allclose(points.iloc[:, -2], bet["x"])
    np.testing.assert_allclose(points.iloc[:, -1], bet["y"])
    fit = frame[(frame["序号"] == 1) & (frame["曲线"] == "BET 拟合线")]
    assert fit.iloc[:, -2].min() == pytest.approx(min(bet["x"]))
    assert fit.iloc[:, -2].max() == pytest.approx(max(bet["x"]))
    np.testing.assert_allclose(fit.iloc[:, -1], bet["slope"] * fit.iloc[:, -2] + bet["intercept"])
    assert len(figures[-1].axes[0].lines) == 4
    assert any("原区间" in caption.value for caption in app.caption)


def test_missing_bjh_is_named_and_never_plotted_as_zero(monkeypatch):
    raw = (ROOT / "examples/betsi_HKUST-1.csv").read_bytes()
    reference = (ROOT / "examples/reference_mesoporous.xlsx").read_bytes()
    app, downloads = batch_app(monkeypatch, [("无孔径.csv", raw), ("有孔径.xlsx", reference)])
    start(app)
    downloads.clear()
    app.radio(key="comparison_kind").set_value("BJH 孔径分布").run()
    assert not app.exception
    assert any("无孔径" in warning.value and "BJH" in warning.value for warning in app.warning)
    assert "BET_comparison_bjh_psd.png" not in downloads
    assert any("至少需要 2 个" in info.value for info in app.info)


def test_new_files_do_not_expand_selection_and_duplicate_names_are_distinct(comparison):
    app, downloads, figures, files = comparison
    choices = app.multiselect(key="comparison_samples")
    choices.set_value([]).run()
    files[:] = [("同名.xlsx", files[0][1]), ("同名.xlsx", files[0][1])]
    downloads.clear()
    app.run()
    assert app.multiselect(key="comparison_samples").value == []
    assert "BET_comparison_isotherm.png" not in downloads
    app.multiselect(key="comparison_samples").set_value(app.multiselect(key="comparison_samples").options).run()
    assert not app.exception
    assert len(set(app.multiselect[0].value)) == 2
    frame = comparison_csv(downloads)
    assert set(frame["序号"]) == {1, 2}
    labels = [line.get_label() for line in figures[-1].axes[0].lines]
    assert len(set(labels)) == 4


def test_original_plot_style_and_branch_filter_share_export_data(comparison):
    app, downloads, figures, _ = comparison
    assert not app.get("vega_lite_chart")
    axis = figures[-1].axes[0]
    assert not any(line.get_visible() for line in axis.get_xgridlines())
    assert axis.lines[0].get_linewidth() == pytest.approx(1.5)
    assert axis.lines[0].get_markersize() == pytest.approx(5)
    preview = BytesIO()
    figures[-1].savefig(preview, format="png", dpi=300, bbox_inches="tight")
    assert downloads["BET_comparison_isotherm.png"] == preview.getvalue()
    app.radio(key="comparison_branch").set_value("仅吸附").run()
    assert not app.exception
    assert set(comparison_csv(downloads)["曲线"]) == {"吸附支"}
    assert len(figures[-1].axes[0].lines) == 2
    assert any("完全重合" in info.value for info in app.info)


def test_cumulative_direction_is_visible_in_mixed_reports(monkeypatch):
    files = []
    for reverse in (False, True):
        frame, source, _ = make_asap_frame()
        if reverse:
            values = source["bjh"][:, 2]
            frame.iloc[4:4 + len(values), 15] = values.max() - values
        buffer = BytesIO()
        frame.to_excel(buffer, index=False, header=False)
        files.append((f"方向{reverse}.xlsx", buffer.getvalue()))
    figures = []
    monkeypatch.setattr("streamlit.pyplot", lambda fig, **kw: figures.append(fig))
    app, downloads = batch_app(monkeypatch, files)
    start(app)
    app.radio(key="comparison_kind").set_value("BJH 累积孔容").run()
    assert not app.exception
    labels = [line.get_label() for line in figures[-1].axes[0].lines]
    assert "从小孔径累积" in labels[0]
    assert "从大孔径累积" in labels[1]
    exported = comparison_csv(downloads, "bjh_cumulative")
    assert any("从大孔径累积" in value for value in exported["曲线"])
    assert any("累积方向" in warning.value for warning in app.warning)


def test_sample_names_are_literal_text_and_plot_errors_do_not_hide_details(monkeypatch):
    raw = (ROOT / "examples/reference_mesoporous.xlsx").read_bytes()
    app, downloads = batch_app(monkeypatch, [("$^$.xlsx", raw), ("正常.xlsx", raw)])
    start(app)
    assert "BET_comparison_isotherm.png" in downloads
    assert "样品分析" in app.radio(key="analysis_mode").options

    def fail_save(*args, **kwargs):
        raise RuntimeError("模拟对比图导出失败")

    before = plt.get_fignums()
    monkeypatch.setattr("matplotlib.figure.Figure.savefig", fail_save)
    downloads.clear()
    app.run()
    assert not app.exception
    assert before == plt.get_fignums()
    assert "样品分析" in app.radio(key="analysis_mode").options
    assert any("模拟对比图导出失败" in warning.value for warning in app.warning)
    assert "BET_batch_summary.csv" in downloads
    assert "BET_comparison_isotherm.png" not in downloads


def test_bjh_missing_cumulative_column_is_excluded_without_losing_other_samples(monkeypatch):
    files = []
    app, downloads = batch_app(monkeypatch, files)
    template = downloads["BET_template.csv"].decode("utf-8-sig")
    template = template.split("[BJH]")[0] + "[BJH]\nrp_nm,dVp_drp\n1.5,0.01\n2,0.02\n"
    raw = (ROOT / "examples/reference_mesoporous.xlsx").read_bytes()
    files.extend([("缺少累积列.csv", template.encode("utf-8-sig")), ("A.xlsx", raw), ("B.xlsx", raw)])
    app.run()
    start(app)
    app.radio(key="comparison_kind").set_value("BJH 累积孔容").run()
    assert not app.exception
    assert set(comparison_csv(downloads, "bjh_cumulative")["序号"]) == {2, 3}
    assert any("缺少累积列" in warning.value for warning in app.warning)
    app.radio(key="analysis_mode").set_value("样品分析").run()
    assert app.selectbox(key="batch_detail")
    assert not app.exception
