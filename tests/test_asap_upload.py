"""直接上传 ASAP 报告及 SMP 配套导出流程。"""
from io import BytesIO
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from tests.asap_fixture import save_asap_workbook
from bet_analysis import read_bet_xls

ROOT = Path(__file__).parents[1]
SMP_BYTES = b"^vMIC##&&FS\x000200" + b"\x00" * 32


def upload_value(data, name):
    uploaded = BytesIO(data)
    uploaded.name = name
    return uploaded


def run_app():
    return AppTest.from_file(str(ROOT / "app_bet.py"), default_timeout=40).run()


def test_asap_upload_reaches_all_analysis_tabs(monkeypatch, tmp_path):
    path = tmp_path / "asap.xlsx"
    save_asap_workbook(path)
    monkeypatch.setattr("streamlit.file_uploader", lambda *args, **kw: upload_value(path.read_bytes(), "asap.XLSX"))
    app = run_app()
    assert [] == [e.message for e in app.exception]
    assert 7 == len(app.tabs)
    assert not any("失败" in e.value for e in app.error)


def test_smp_requests_export_without_analysis(monkeypatch):
    def uploader(*args, **kwargs):
        if kwargs.get("key") == "smp_export":
            return None
        assert "smp" in kwargs["type"]
        return upload_value(SMP_BYTES, "sample.SMP")
    monkeypatch.setattr("streamlit.file_uploader", uploader)
    app = run_app()
    assert [] == [e.message for e in app.exception]
    assert 0 == len(app.tabs)
    assert any("SMP" in e.value and "XLS" in e.value for e in app.info)


def test_smp_with_export_reaches_analysis(monkeypatch, tmp_path):
    path = tmp_path / "sample.xlsx"
    save_asap_workbook(path)
    def uploader(*args, **kwargs):
        if kwargs.get("key") == "smp_export":
            return upload_value(path.read_bytes(), "sample.xlsx")
        return upload_value(SMP_BYTES, "sample.SMP")
    monkeypatch.setattr("streamlit.file_uploader", uploader)
    app = run_app()
    assert [] == [e.message for e in app.exception]
    assert 7 == len(app.tabs)


def test_invalid_smp_is_explained_before_analysis(monkeypatch):
    monkeypatch.setattr("streamlit.file_uploader", lambda *args, **kw: upload_value(b"not a sample file", "wrong.smp"))
    app = run_app()
    assert [] == [e.message for e in app.exception]
    assert any("无法识别此 SMP" in e.value for e in app.error)


def test_smp_cli_explains_export_requirement(tmp_path):
    path = tmp_path / "sample.SMP"
    path.write_bytes(SMP_BYTES)
    with pytest.raises(ValueError, match="SMP.*XLS"):
        read_bet_xls(str(path))
