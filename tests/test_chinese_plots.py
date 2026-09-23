"""验证汉化后图像的数值、中文字体和单位上标。"""

from io import BytesIO
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from bet_analysis import read_bet_xls
from tplot_analysis import TPlotAnalyser
import zh_cn


REFERENCE = Path(__file__).resolve().parents[1] / "examples" / "reference_mesoporous.xlsx"


def test_matplotlib_rendering_is_serialized_across_streamlit_threads():
    rendering = getattr(zh_cn, "matplotlib_rendering", None)
    assert rendering is not None, "需要为 Matplotlib 的共享公式解析器提供进程级绘图锁"

    ready = Barrier(8)

    def render(index):
        ready.wait()
        with rendering():
            fig, ax = plt.subplots(figsize=(3, 2))
            try:
                ax.plot([0, 1], [index, index + 1])
                ax.set_xlabel(r"相对压力 ($p/p_0$)")
                ax.set_ylabel(r"吸附量 (cm$^3$ g$^{-1}$ STP)")
                zh_cn.prepare_figure(fig)
                fig.tight_layout()
                output = BytesIO()
                fig.savefig(output, format="png")
                return output.getvalue()
            finally:
                plt.close(fig)

    with ThreadPoolExecutor(max_workers=8) as pool:
        images = list(pool.map(render, range(8)))

    assert all(image.startswith(b"\x89PNG\r\n\x1a\n") for image in images)


def test_chinese_tplot_keeps_pore_fractions_and_unit_glyphs(monkeypatch, caplog):
    data = read_bet_xls(str(REFERENCE))
    analyser = TPlotAnalyser(
        pressure=data["ads"][:, 0], volume_adsorbed=data["ads"][:, 1],
        s_bet=data["summary"]["S_BET"], total_pore_volume=data["summary"]["Vp_total"],
    )
    close = plt.close
    monkeypatch.setattr(plt, "close", lambda *args, **kwargs: None)
    try:
        analyser.plot_tplot(save_path=BytesIO(), sample_name="中文样品")
        fig = plt.gcf()
        heights = [bar.get_height() for bar in fig.axes[1].patches]
        assert pytest.approx([0.0, 100.0]) == heights
        assert ["微孔", "介孔 + 大孔"] == [tick.get_text() for tick in fig.axes[1].get_xticklabels()]
        assert [] == [message for message in caplog.messages if "glyph" in message.lower()]
    finally:
        close("all")
