"""
設定ファイル - カテゴリ定義・定数管理
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent

# secrets/.env を読み込み
SECRETS_DIR = PROJECT_ROOT / "secrets"
load_dotenv(SECRETS_DIR / ".env")

# ===== API Keys =====
# ===== API Keys =====
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

# Streamlit Cloud対応: 環境変数がなければ st.secrets を確認
try:
    import streamlit as st
    if not GOOGLE_API_KEY and hasattr(st, "secrets"):
        GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY")
    if not GOOGLE_DRIVE_FOLDER_ID and hasattr(st, "secrets"):
        GOOGLE_DRIVE_FOLDER_ID = st.secrets.get("GOOGLE_DRIVE_FOLDER_ID")
except ImportError:
    pass
GOOGLE_DRIVE_CREDENTIALS_PATH = os.getenv(
    "GOOGLE_DRIVE_CREDENTIALS_PATH",
    str(SECRETS_DIR / "credentials.json")
)

# ===== Paths =====
DATA_DIR = PROJECT_ROOT / "data"
IMAGES_DIR = PROJECT_ROOT / "images"
CHROMA_DB_DIR = DATA_DIR / "chroma_db"
PRACTICES_JSON = DATA_DIR / "practices.json"
ANSWER_CACHE_JSON = DATA_DIR / "answer_cache.json"
USAGE_LOG_JSON = DATA_DIR / "usage_log.json"

# ディレクトリ作成
DATA_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)

# ===== Categories =====
CATEGORIES = {
    "html_css": "HTML/CSS",
    "javascript": "JavaScript",
    "python": "Python",
    "gas": "Google Apps Script",
    "vba": "VBA",
    "other": "その他・マニュアル"
}

# ===== Content Types =====
CONTENT_TYPES = {
    "code": "コード",
    "manual": "マニュアル"
}

# ===== Gemini Models =====
GEMINI_MODELS = {
    "embedding": "gemini-embedding-001",      # 最新Embedding（3072次元）
    "answer": "gemini-3-pro-preview",         # 検索回答用（最新Pro）
    "format": "gemini-3-pro-preview",         # AI整形・タイトル生成用（Proに変更）
    "check": "gemini-2.5-flash"               # AIチェック用
}

# Embedding設定
EMBEDDING_DIMENSIONS = 768  # 768, 1536, 3072から選択可能

# ===== ChromaDB =====
CHROMA_COLLECTION_NAME = "best_practices"
SEARCH_TOP_K = 5  # 検索結果の上位件数

# ===== Logging =====
import logging

def setup_logger(name: str, level=logging.DEBUG) -> logging.Logger:
    """ロガー設定（プロトタイプ用：詳細ログ）"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

# グローバルロガー
logger = setup_logger("RAG")
