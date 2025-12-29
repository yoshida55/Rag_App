"""
登録ページ - シンプル版
カテゴリ + 説明文 + 画像（オプション）、他はAI自動生成
"""
import streamlit as st
import json
import uuid
from pathlib import Path
from config.settings import CATEGORIES, CONTENT_TYPES, logger
from modules.database import ChromaManager
from modules.data_manager import DataManager
from modules.llm import generate_simple_response, analyze_image

# 画像保存先
IMAGES_DIR = Path(__file__).parent.parent / "data" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# ページ設定
st.set_page_config(page_title="登録", page_icon="📝", layout="wide")

logger.info("=== 登録ページ表示 ===")

# セッション状態初期化
if "chroma_manager" not in st.session_state:
    st.session_state.chroma_manager = ChromaManager(persistent=False)
    st.session_state.chroma_manager.load_from_json()

if "data_manager" not in st.session_state:
    st.session_state.data_manager = DataManager()


def process_content_all_in_one(raw_text: str) -> dict:
    """1回のAI呼び出しで全て処理（整形・タイトル・タグ・コード抽出）"""
    prompt = f"""以下のテキストを分析して、すべての情報を抽出・整形してください。

入力テキスト:
{raw_text[:2000]}

以下の形式でJSON形式のみで回答してください（余計な説明不要）:
{{
    "title": "内容を表す簡潔なタイトル（15〜20文字）",
    "description": "Markdown形式に整形した説明文（見出し・箇条書き・太字を適切に使用、誤字修正済み）",
    "tags": ["関連タグ1", "関連タグ2", "関連タグ3", "関連タグ4", "関連タグ5"],
    "has_code": true または false,
    "code_html": "HTMLコードがあれば抽出、なければnull",
    "code_css": "CSSコードがあれば抽出、なければnull",
    "code_js": "JavaScriptコードがあれば抽出、なければnull"
}}

注意:
- descriptionは元の情報を省略せず、読みやすく整形
- コードは説明文から分離して専用フィールドに
- タグは具体的なキーワードを5つ程度
"""
    try:
        response = generate_simple_response(prompt)
        response = response.strip()
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        result = json.loads(response.strip())

        # nullをNoneに変換
        for key in ["code_html", "code_css", "code_js"]:
            if result.get(key) == "null" or result.get(key) == "":
                result[key] = None

        logger.debug(f"[処理] 完了: {result.get('title', '無題')}")
        return result
    except Exception as e:
        logger.error(f"[処理] エラー: {e}")
        return {
            "title": "無題",
            "description": raw_text,
            "tags": [],
            "has_code": False,
            "code_html": None,
            "code_css": None,
            "code_js": None
        }


# ヘッダー（小さく）
st.markdown("#### 📝 登録")

# カテゴリ・タイプ選択（横並び）
col1, col2 = st.columns([1, 1])
with col1:
    category = st.selectbox(
        "カテゴリ",
        options=list(CATEGORIES.keys()),
        format_func=lambda x: CATEGORIES[x],
        label_visibility="collapsed"
    )
with col2:
    content_type = st.radio(
        "タイプ",
        options=list(CONTENT_TYPES.keys()),
        format_func=lambda x: CONTENT_TYPES[x],
        horizontal=True,
        label_visibility="collapsed"
    )

# 説明文入力
description = st.text_area(
    "説明文（コード含めてOK、ラフ入力OK）",
    height=200,
    placeholder="・やりたいこと\n・コード例\n.class { display: flex; }\n・注意点など\n\n何でも貼り付けてOK！AIが整形します。",
    label_visibility="collapsed"
)

# 画像アップロード（オプション）
st.markdown("###### 📷 画像（任意）")
uploaded_image = st.file_uploader(
    "画像をアップロード",
    type=["png", "jpg", "jpeg", "gif", "webp"],
    label_visibility="collapsed",
    help="スクリーンショットや参考画像をアップロードすると、AIが自動分析します"
)

# 画像プレビュー
if uploaded_image:
    st.image(uploaded_image, caption="アップロード画像", use_container_width=True)

# 登録ボタン
if st.button("✨ 登録", type="primary", use_container_width=True):
    if not description and not uploaded_image:
        st.error("説明文または画像を入力してください")
    else:
        with st.spinner("🔄 AI処理中..."):
            logger.info("[登録] AI処理開始")

            image_path = None
            image_analysis = None

            # 画像がある場合は先に分析・保存
            if uploaded_image:
                with st.spinner("🖼️ 画像分析中..."):
                    image_data = uploaded_image.getvalue()

                    # 画像AI分析
                    image_analysis = analyze_image(image_data, description[:100] if description else "")
                    logger.info(f"[登録] 画像分析完了: {len(image_analysis.get('description', ''))}文字")

                    # 画像保存
                    ext = uploaded_image.name.split(".")[-1] if "." in uploaded_image.name else "png"
                    image_filename = f"{uuid.uuid4().hex[:12]}.{ext}"
                    image_path = IMAGES_DIR / image_filename

                    with open(image_path, "wb") as f:
                        f.write(image_data)
                    logger.info(f"[登録] 画像保存: {image_path}")

                    # 相対パスに変換（data/images/xxx.png）
                    image_path = f"data/images/{image_filename}"

            # テキスト処理
            if description:
                result = process_content_all_in_one(description)
            else:
                # 画像のみの場合
                result = {
                    "title": "無題",
                    "description": "",
                    "tags": [],
                    "has_code": False,
                    "code_html": None,
                    "code_css": None,
                    "code_js": None
                }

            title = result.get("title", "無題")
            tags = result.get("tags", [])
            formatted_desc = result.get("description", description or "")
            has_code = result.get("has_code", False)

            # 画像分析結果をマージ
            if image_analysis:
                # 画像の説明を追記
                if image_analysis.get("description"):
                    formatted_desc += f"\n\n### 📷 画像の説明\n{image_analysis['description']}"

                # タグをマージ（重複除去）
                image_tags = image_analysis.get("tags", [])
                tags = list(dict.fromkeys(tags + image_tags))[:10]  # 最大10個

                # キーワードを説明に追加（検索用）
                if image_analysis.get("keywords"):
                    formatted_desc += f"\n\n**キーワード**: {image_analysis['keywords']}"

            # content_typeを自動判定
            actual_content_type = "code" if has_code else "manual"

            # データ作成
            practice = {
                "title": title,
                "category": category,
                "content_type": actual_content_type,
                "description": formatted_desc,
                "tags": tags,
                "code_html": result.get("code_html"),
                "code_css": result.get("code_css"),
                "code_js": result.get("code_js"),
                "notes": "",
                "image_path": image_path
            }

            # 保存
            try:
                practice_id = st.session_state.data_manager.add(practice)
                practice["id"] = practice_id
                st.session_state.chroma_manager.add_practice(practice)

                st.success(f"✅ 登録完了！")
                st.markdown(f"**タイトル**: {title}")
                st.markdown(f"**タグ**: {', '.join(tags)}")
                if image_path:
                    st.markdown(f"**画像**: 保存済み")
                logger.info(f"[登録] 完了: {practice_id}")

            except Exception as e:
                st.error(f"❌ 登録エラー: {e}")
                logger.error(f"[登録] エラー: {e}")

# フッター
st.markdown("---")
col_info1, col_info2 = st.columns(2)
with col_info1:
    st.caption(f"📊 登録数: {len(st.session_state.data_manager.get_all())}件")
with col_info2:
    st.caption("💡 一括登録は「一括登録」ページへ")
