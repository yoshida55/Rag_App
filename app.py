"""
RAG Best Practices - メインアプリケーション
Streamlit エントリーポイント
→ 自動的に検索ページへ遷移
"""
import streamlit as st
from config.settings import logger

# ページ設定
st.set_page_config(
    page_title="RAG Best Practices",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

logger.info("=== アプリケーション起動 ===")

# 自動的に検索ページへ遷移
st.switch_page("pages/1_🔍_検索.py")

logger.info("検索ページへ遷移")
