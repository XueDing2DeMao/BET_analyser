"""验证中文报告的编码、名称保真，以及模板上传兼容性。"""

from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_SECONDS = 30


def run_upload(monkeypatch, data, name):
    def uploader(*args, **kwargs):
        uploaded = BytesIO(data)
        uploaded.name = name
        return [uploaded] if kwargs.get("accept_multiple_files") else uploaded

    monkeypatch.setattr("streamlit.file_uploader", uploader)
    return AppTest.from_file(str(ROOT / "app_bet.py"), default_timeout=TIMEOUT_SECONDS).run()


def test_report_is_excel_readable_and_preserves_sample(monkeypatch):
    downloads = {}
    monkeypatch.setattr("streamlit.download_button", lambda **kw: downloads.update({kw["file_name"]: kw["data"]}))
    data = (ROOT / "examples" / "reference_mesoporous.xlsx").read_bytes()
    app = run_upload(monkeypatch, data, "样品_α.xlsx")

    assert [] == [error.message for error in app.exception]
    report = downloads["样品_α_BET_report.csv"]
    assert b"\xef\xbb\xbf" == report[:3]
    rows = pd.read_csv(StringIO(report.decode("utf-8-sig")))
    assert ["参数", "数值"] == list(rows.columns)
    assert "样品_α" == rows.iloc[0]["数值"]
    assert float(rows.loc[rows["参数"] == "BET 比表面积 S_BET (m²/g)", "数值"].iloc[0]) == pytest.approx(177.279, abs=.001)
    assert "IV(a) 型" == rows.loc[rows["参数"] == "等温线类型", "数值"].iloc[0]
    assert "样品_α_BET_analysis.png" not in downloads
    app.button(key="detail_png_generate").click().run()
    assert not app.exception
    assert b"\x89PNG\r\n\x1a\n" == downloads["样品_α_BET_analysis.png"][:8]


def test_chinese_csv_template_can_be_uploaded(monkeypatch):
    downloads = {}
    monkeypatch.setattr("streamlit.download_button", lambda **kw: downloads.update({kw["file_name"]: kw["data"]}))
    home = AppTest.from_file(str(ROOT / "app_bet.py"), default_timeout=TIMEOUT_SECONDS).run()
    template = downloads["BET_template.csv"]

    assert "填写说明" in template.decode("utf-8-sig")
    assert "[ISOTHERM]" in template.decode("utf-8-sig")
    app = run_upload(monkeypatch, template, "中文模板.csv")
    assert [] == [error.value for error in app.error]
    assert [] == [error.message for error in app.exception]
    assert "📊 总览" in [tab.label for tab in app.tabs]


def test_invalid_csv_has_chinese_diagnostic(monkeypatch):
    app = run_upload(monkeypatch, b"pressure,adsorbed\n0.1,1\n", "invalid.csv")
    assert [] == [error.message for error in app.exception]
    assert 1 == len(app.error)
    assert "至少需要 5 个数据点" in app.error[0].value
