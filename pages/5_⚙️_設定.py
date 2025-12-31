"""
設定ページ
- 使用モデル一覧
- API使用量・料金表示
- ダークモード設定
"""
import streamlit as st
from config.settings import GEMINI_MODELS, EMBEDDING_DIMENSIONS, logger
from modules.usage_tracker import get_current_month_usage, get_all_usage, reset_usage, PRICING, USD_TO_JPY

# ページ設定
st.set_page_config(page_title="設定", page_icon="⚙️", layout="wide")

# ダークモード初期化
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# 共通スタイル適用（サイドバー統一 + ダークモード）
from modules.ui_styles import inject_common_styles, apply_dark_mode_script
st.markdown(inject_common_styles(
    include_headings=True, 
    sidebar_mode="narrow",
    dark_mode=st.session_state.dark_mode
), unsafe_allow_html=True)

logger.info("=== 設定ページ表示 ===")

# ヘッダー
st.markdown("#### ⚙️ 設定")

# ダークモード設定
st.markdown("### 🌙 表示設定")

col_dark, col_space = st.columns([1, 3])
with col_dark:
    dark_mode = st.toggle("ダークモード", value=st.session_state.dark_mode, key="dark_mode_toggle")
    if dark_mode != st.session_state.dark_mode:
        st.session_state.dark_mode = dark_mode
        st.rerun()

if st.session_state.dark_mode:
    st.caption("🌙 ダークモードが有効です")
else:
    st.caption("☀️ ライトモードが有効です")

st.markdown("---")

# プレビュー生成設定
st.markdown("### 🎨 プレビュー生成")

# デフォルト設定の初期化
if "preview_format" not in st.session_state:
    st.session_state.preview_format = "svg"

preview_format = st.radio(
    "デフォルト生成形式",
    options=["svg", "html"],
    format_func=lambda x: "📐 SVG（図解イメージ）" if x == "svg" else "🌐 HTML（動くプレビュー）",
    horizontal=True,
    index=0 if st.session_state.preview_format == "svg" else 1,
    help="説明文からプレビューを生成する時のデフォルト形式"
)
st.session_state.preview_format = preview_format

st.caption("💡 検索結果で「📝 生成」ボタンを押すと、説明文から図解/プレビューを作成します")

st.markdown("---")

# モデル設定
st.markdown("### 🤖 使用モデル")

model_data = [
    {"用途": "🔍 検索回答", "モデル": GEMINI_MODELS["answer"], "説明": "高品質な回答生成（ストリーミング対応）"},
    {"用途": "✨ 整形・生成", "モデル": GEMINI_MODELS["format"], "説明": "登録時のタイトル・タグ・説明文生成"},
    {"用途": "🔢 Embedding", "モデル": GEMINI_MODELS["embedding"], "説明": f"ベクトル検索用（{EMBEDDING_DIMENSIONS}次元）"},
]

st.table(model_data)

st.markdown("---")

# API使用量
st.markdown("### 📊 API使用量（今月）")

usage = get_current_month_usage()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("API呼び出し回数", f"{usage.get('calls', 0):,} 回")

with col2:
    st.metric("入力トークン", f"{usage.get('input_tokens', 0):,}")

with col3:
    st.metric("出力トークン", f"{usage.get('output_tokens', 0):,}")

with col4:
    cost_jpy = usage.get('cost_jpy', 0.0)
    st.metric("推定料金", f"¥{cost_jpy:.1f}")

# モデル別使用量
st.markdown("#### モデル別内訳")

by_model = usage.get("by_model", {})
if by_model:
    model_usage_data = []
    for model_name, model_usage in by_model.items():
        cost_jpy = model_usage.get("cost_usd", 0) * USD_TO_JPY
        model_usage_data.append({
            "モデル": model_name,
            "呼び出し": f"{model_usage.get('calls', 0):,}",
            "入力トークン": f"{model_usage.get('input_tokens', 0):,}",
            "出力トークン": f"{model_usage.get('output_tokens', 0):,}",
            "料金": f"¥{cost_jpy:.2f}"
        })
    st.table(model_usage_data)
else:
    st.info("まだAPI使用履歴がありません")

st.markdown("---")

# 料金表
st.markdown("### 💰 料金表（参考）")

pricing_data = []
for model_name, prices in PRICING.items():
    input_jpy = prices["input"] * USD_TO_JPY / 1000  # 1Kトークンあたり
    output_jpy = prices["output"] * USD_TO_JPY / 1000
    pricing_data.append({
        "モデル": model_name,
        "入力（¥/1Kトークン）": f"¥{input_jpy:.4f}",
        "出力（¥/1Kトークン）": f"¥{output_jpy:.4f}",
        "備考": "概算値"
    })

st.table(pricing_data)

st.caption(f"※ 換算レート: $1 = ¥{USD_TO_JPY}")
st.caption("※ トークン数は概算（1トークン≒4文字で計算）")
st.caption("※ 実際の料金はGoogle Cloud Consoleで確認してください")

st.markdown("---")

# 累計
st.markdown("### 📈 累計使用量")

all_usage = get_all_usage()
total = all_usage.get("total", {})

col_t1, col_t2, col_t3 = st.columns(3)
with col_t1:
    st.metric("累計入力トークン", f"{total.get('input_tokens', 0):,}")
with col_t2:
    st.metric("累計出力トークン", f"{total.get('output_tokens', 0):,}")
with col_t3:
    st.metric("累計料金", f"¥{total.get('cost_jpy', 0.0):.1f}")

st.markdown("---")

# リセットボタン
st.markdown("### 🔧 管理")

# セクションキャッシュ
from modules.section_cache import clear_cache, get_cache_stats

st.markdown("#### 📂 セクションキャッシュ")
cache_stats = get_cache_stats()
col_c1, col_c2, col_c3 = st.columns(3)
with col_c1:
    st.metric("キャッシュ数", f"{cache_stats['entry_count']} 件")
with col_c2:
    st.metric("総セクション数", f"{cache_stats['total_sections']} 件")
with col_c3:
    st.metric("ファイルサイズ", f"{cache_stats['file_size_kb']} KB")

st.caption("💡 セクションキャッシュは、コード学習ページのセクション分析結果を保存しています。")

if st.button("🗑️ セクションキャッシュをクリア", type="secondary"):
    if clear_cache():
        st.success("✅ セクションキャッシュをクリアしました")
        st.rerun()
    else:
        st.warning("キャッシュファイルが存在しません")

st.markdown("---")

st.markdown("---")

# 検索設定
st.markdown("#### 🧠 検索設定")

col_s1, col_s2, col_s3 = st.columns(3)

with col_s1:
    # 全体検索の閾値
    if "global_search_threshold" not in st.session_state:
        st.session_state.global_search_threshold = 0.64
    
    st.session_state.global_search_threshold = st.slider(
        "🔍 全体検索 (0.00-1.00)",
        min_value=0.0,
        max_value=1.0,
        value=float(st.session_state.global_search_threshold),
        step=0.01,
        format="%.2f",
        help="検索ページで結果を表示するための最低類似度。標準: 0.64"
    )

with col_s2:
    # 関連図解の閾値
    if "related_visual_threshold" not in st.session_state:
        st.session_state.related_visual_threshold = 0.70
        
    st.session_state.related_visual_threshold = st.slider(
        "📐 関連図解 (0.00-1.00)",
        min_value=0.0,
        max_value=1.0,
        value=float(st.session_state.related_visual_threshold),
        step=0.01,
        format="%.2f",
        help="チャットで図解を表示するための最低類似度。標準: 0.70"
    )

with col_s3:
    # AI回答キャッシュの閾値
    if "answer_cache_threshold" not in st.session_state:
        st.session_state.answer_cache_threshold = 0.85
        
    st.session_state.answer_cache_threshold = st.slider(
        "💾 キャッシュ (0.00-1.00)",
        min_value=0.0,
        max_value=1.0,
        value=float(st.session_state.answer_cache_threshold),
        step=0.01,
        format="%.2f",
        help="既存のAI回答を再利用するための類似度。標準: 0.85"
    )

st.divider()

# ChromaDB同期
st.markdown("#### 🔄 データベース管理")
col_db1, col_db_space = st.columns([1, 3])



with col_db1:
    if st.button("🔄 ChromaDB全件再同期", help="全てのデータを検索DBに登録し直します"):
        with st.spinner("データベース同期中..."):
            from modules.database import ChromaManager
            # セッションになければ一時作成
            cm = st.session_state.get("chroma_manager") or ChromaManager()
            count = cm.load_from_json()
            st.success(f"✅ 同期完了: {count}件")

st.markdown("---")

# API使用量リセット
st.markdown("#### 📊 API使用量")
col_reset, col_space = st.columns([1, 3])
with col_reset:
    if st.button("🗑️ 使用量リセット", type="secondary"):
        st.session_state["confirm_reset"] = True

if st.session_state.get("confirm_reset"):
    st.warning("本当に使用量データをリセットしますか？")
    col_yes, col_no = st.columns(2)
    with col_yes:
        if st.button("はい、リセット"):
            reset_usage()
            del st.session_state["confirm_reset"]
            st.success("リセット完了")
            st.rerun()
    with col_no:
        if st.button("キャンセル"):
            del st.session_state["confirm_reset"]
            st.rerun()
