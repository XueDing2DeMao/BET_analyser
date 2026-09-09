"""ASAP 单表报告读取的数值保真与错误边界。"""
import numpy as np
import pytest
from bet_analysis import read_bet_xls
from tests.asap_fixture import make_asap_frame, save_asap_workbook


@pytest.mark.parametrize("offset", [(0, 0), (8, 4)])
def test_asap_report_is_identified_by_headers(tmp_path, offset):
    path = tmp_path / "ASAP.xlsx"
    expected, bet_points = save_asap_workbook(path, row_offset=offset[0], col_offset=offset[1])
    actual = read_bet_xls(str(path))
    for key in ("ads", "des", "bjh"):
        np.testing.assert_allclose(expected[key], actual[key])
    np.testing.assert_allclose(bet_points, actual["bet_pts"])
    assert expected["summary"]["S_BET"] == actual["summary"]["S_BET"]
    assert expected["summary"]["Vm"] == actual["summary"]["Vm"]
    assert 0 == actual["summary"]["start_pt"]
    assert len(bet_points)-1 == actual["summary"]["end_pt"]


def load_frame(monkeypatch, frame):
    monkeypatch.setattr("bet_analysis._load_sheets", lambda _: (["Report"], {"Report": frame}))
    return read_bet_xls("report.XLS")


def test_asap_checks_adsorption_units(monkeypatch):
    frame, _, _ = make_asap_frame()
    frame.iat[3, 4] = "Quantity Adsorbed (mmol/g)"
    with pytest.raises(ValueError, match="cm³.*STP"):
        load_frame(monkeypatch, frame)


def test_asap_rejects_incomplete_measurement_row(monkeypatch):
    frame, _, _ = make_asap_frame()
    frame.iat[5, 4] = np.nan
    with pytest.raises(ValueError, match="缺失|非数值"):
        load_frame(monkeypatch, frame)


def test_asap_reports_absent_bjh_without_zero(monkeypatch):
    frame, _, _ = make_asap_frame()
    frame.iloc[:, 12:] = np.nan
    frame.iat[1, 20], frame.iat[1, 21] = "Analysis adsorptive:", "N2"
    data = load_frame(monkeypatch, frame)
    assert (0, 4) == data["bjh"].shape
    assert data["summary"]["S_BJH"] is None
    assert data["summary"]["Vp_BJH"] is None


def test_asap_requires_matching_bjh_diameter_grid(monkeypatch):
    frame, _, _ = make_asap_frame()
    frame.iat[4, 19] *= 1.1
    with pytest.raises(ValueError, match="BJH.*孔径.*一致"):
        load_frame(monkeypatch, frame)


def test_asap_rejects_multiple_samples(monkeypatch):
    frame, _, _ = make_asap_frame()
    import pandas as pd
    duplicate = pd.concat([frame, frame], axis=1, ignore_index=True)
    with pytest.raises(ValueError, match="多个.*报告"):
        load_frame(monkeypatch, duplicate)


def test_blank_spacer_does_not_drop_later_measurements(monkeypatch):
    import pandas as pd
    frame, expected, _ = make_asap_frame()
    spacer = pd.DataFrame(np.nan, index=[0], columns=frame.columns)
    frame = pd.concat([frame.iloc[:8], spacer, frame.iloc[8:]], ignore_index=True)
    actual = load_frame(monkeypatch, frame)
    np.testing.assert_allclose(expected["ads"], actual["ads"])


def test_other_adsorptive_is_not_analysed_as_nitrogen(monkeypatch):
    frame, _, _ = make_asap_frame()
    frame.iat[1, 21] = "Ar"
    with pytest.raises(ValueError, match="N₂|氮气"):
        load_frame(monkeypatch, frame)


def test_missing_adsorptive_requests_metadata(monkeypatch):
    frame, _, _ = make_asap_frame()
    frame.iat[1, 20] = np.nan
    with pytest.raises(ValueError, match="吸附质"):
        load_frame(monkeypatch, frame)


def test_mislabeled_branches_are_rejected(monkeypatch):
    frame, _, _ = make_asap_frame()
    frame.iat[2, 3] = "Synthetic : Desorption"
    with pytest.raises(ValueError, match="吸附支.*标记"):
        load_frame(monkeypatch, frame)


def test_bet_linearisation_must_match_adsorption_amount(monkeypatch):
    frame, _, _ = make_asap_frame()
    frame.iat[7, 10] *= 2
    with pytest.raises(ValueError, match="BET.*线性化.*一致"):
        load_frame(monkeypatch, frame)
