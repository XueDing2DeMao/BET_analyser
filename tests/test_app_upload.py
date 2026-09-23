"""验证网页上传在 Windows 等没有 /tmp 的环境中可用。"""

from io import BytesIO
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_TIMEOUT_SECONDS = 30


@pytest.mark.parametrize(
    "filename", ["reference_mesoporous.xlsx", "betsi_HKUST-1.csv"]
)
def test_uploaded_example_reaches_analysis(monkeypatch, filename):
    uploaded = BytesIO((PROJECT_ROOT / "examples" / filename).read_bytes())
    uploaded.name = filename
    monkeypatch.setattr("streamlit.file_uploader", lambda *args, **kwargs: [uploaded])

    app = AppTest.from_file(
        str(PROJECT_ROOT / "app_bet.py"), default_timeout=APP_TIMEOUT_SECONDS
    ).run()

    assert [] == [error.value for error in app.error]
    assert [] == [error.message for error in app.exception]
    assert "📊 总览" in [tab.label for tab in app.tabs]
    assert any(list(df.value.columns) == ["参数", "数值", "单位"] for df in app.dataframe)


def test_home_page_uses_chinese():
    app = AppTest.from_file(str(PROJECT_ROOT / "app_bet.py")).run()

    assert [] == [error.message for error in app.exception]
    assert "🔬 BET / BJH 比表面积与孔结构分析" == app.main.title[0].value
    assert any("自动识别" in caption.value for caption in app.caption)
    assert "样品名称" == app.text_input[0].label
