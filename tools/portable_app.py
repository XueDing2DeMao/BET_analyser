"""便携入口：串行执行分析，保护 Matplotlib 的全局绘图状态。"""
from pathlib import Path
import runpy
import threading

import streamlit as st


@st.cache_resource(show_spinner=False)
def analysis_lock():
    """所有浏览器会话共用同一把锁；切换页面时不会重建。"""
    return threading.RLock()


with analysis_lock():
    runpy.run_path(str(Path(__file__).with_name('app_bet.py')), run_name='__main__')
