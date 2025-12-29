"""
一括登録ページ
テキスト貼り付け / ファイルアップロード / MD+画像一括 → AI整形 → 一括登録
"""
import streamlit as st
import json
import re
import uuid
from pathlib import Path
from config.settings import CATEGORIES, logger
from modules.database import ChromaManager
from modules.data_manager import DataManager
from modules.llm import generate_simple_response, analyze_image

# 画像保存先
IMAGES_DIR = Path(__file__).parent.parent / "data" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# ページ設定
st.set_page_config(page_title="一括登録", page_icon="📥", layout="wide")

logger.info("=== 一括登録ページ表示 ===")

# セッション状態初期化
if "chroma_manager" not in st.session_state:
    st.session_state.chroma_manager = ChromaManager(persistent=False)
    st.session_state.chroma_manager.load_from_json()

if "data_manager" not in st.session_state:
    st.session_state.data_manager = DataManager()

if "bulk_items" not in st.session_state:
    st.session_state.bulk_items = []

if "file_items" not in st.session_state:
    st.session_state.file_items = []


def split_text_auto(text: str) -> list[str]:
    """テキストを自動分割（AIで判断）"""
    if "▢" in text:
        parts = text.split("▢")
        parts = [p.strip() for p in parts if p.strip()]
        logger.debug(f"[分割] ▢で分割: {len(parts)}件")
        return parts

    if "---" in text and text.count("---") >= 2:
        parts = re.split(r'\n-{3,}\n', text)
        parts = [p.strip() for p in parts if p.strip()]
        logger.debug(f"[分割] ---で分割: {len(parts)}件")
        return parts

    if re.search(r'^#{1,2}\s', text, re.MULTILINE):
        parts = re.split(r'\n(?=#{1,2}\s)', text)
        parts = [p.strip() for p in parts if p.strip()]
        logger.debug(f"[分割] 見出しで分割: {len(parts)}件")
        return parts

    return split_text_by_ai(text)


def split_text_by_ai(text: str) -> list[str]:
    """AIでテキストを分割"""
    prompt = f"""以下のテキストを、トピックごとに分割してください。

テキスト:
{text[:3000]}

以下の形式で回答（JSON配列のみ、余計な説明なし）:
["トピック1の全文", "トピック2の全文", "トピック3の全文"]

注意:
- 元のテキストを省略せず、各トピックの全文を含める
- 関連する内容はまとめる
- 最低でも2つ以上に分割
"""
    try:
        response = generate_simple_response(prompt)
        response = response.strip()
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        parts = json.loads(response.strip())
        logger.debug(f"[分割] AIで分割: {len(parts)}件")
        return parts
    except Exception as e:
        logger.error(f"[分割] AIエラー: {e}")
        parts = text.split("\n\n")
        parts = [p.strip() for p in parts if len(p.strip()) > 50]
        return parts if parts else [text]


def process_single_item(text: str, category: str, image_data: bytes = None) -> dict:
    """1つのアイテムをAI処理（1回のAI呼び出しで完結）"""
    prompt = f"""以下のテキストを分析して、すべての情報を抽出・整形してください。

テキスト:
{text[:2000]}

以下の形式でJSON形式のみで回答してください（余計な説明不要）:
{{
    "title": "内容を表す簡潔なタイトル（15〜20文字）",
    "description": "Markdown形式に整形した説明文（見出し・箇条書き・太字を適切に使用、誤字修正済み）",
    "tags": ["関連タグ1", "関連タグ2", "関連タグ3"],
    "has_code": true または false,
    "code_html": "HTMLコードがあれば抽出、なければnull",
    "code_css": "CSSコードがあれば抽出、なければnull",
    "code_js": "JavaScriptコードがあれば抽出、なければnull"
}}

注意:
- descriptionは元の情報を省略せず、読みやすく整形
- コードは説明文から分離して専用フィールドに
- タグは具体的なキーワードを3つ程度
"""
    try:
        response = generate_simple_response(prompt)
        response = response.strip()
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        info = json.loads(response.strip())
    except Exception as e:
        logger.error(f"[処理] エラー: {e}")
        info = {"title": "無題", "description": text, "tags": [], "has_code": False}

    # nullをNoneに変換
    for key in ["code_html", "code_css", "code_js"]:
        if info.get(key) == "null" or info.get(key) == "":
            info[key] = None

    # 画像処理
    image_path = None
    if image_data:
        try:
            # 画像分析
            image_analysis = analyze_image(image_data, info.get("title", ""))

            # 画像保存
            image_filename = f"{uuid.uuid4().hex[:12]}.png"
            image_full_path = IMAGES_DIR / image_filename
            with open(image_full_path, "wb") as f:
                f.write(image_data)
            image_path = f"data/images/{image_filename}"

            # 分析結果をマージ
            if image_analysis.get("description"):
                info["description"] = info.get("description", "") + f"\n\n### 📷 画像の説明\n{image_analysis['description']}"

            if image_analysis.get("tags"):
                existing_tags = info.get("tags", [])
                info["tags"] = list(dict.fromkeys(existing_tags + image_analysis["tags"]))[:10]

            if image_analysis.get("keywords"):
                info["description"] = info.get("description", "") + f"\n\n**キーワード**: {image_analysis['keywords']}"

            logger.info(f"[一括登録] 画像保存: {image_path}")
        except Exception as e:
            logger.error(f"[一括登録] 画像処理エラー: {e}")

    return {
        "title": info.get("title", "無題"),
        "category": category,
        "content_type": "code" if info.get("has_code") else "manual",
        "description": info.get("description", text),
        "tags": info.get("tags", []),
        "code_html": info.get("code_html"),
        "code_css": info.get("code_css"),
        "code_js": info.get("code_js"),
        "notes": "",
        "image_path": image_path
    }


def process_image_only(image_data: bytes, filename: str, category: str) -> dict:
    """画像のみをAI処理"""
    try:
        image_analysis = analyze_image(image_data, filename)

        # 画像保存
        ext = filename.split(".")[-1] if "." in filename else "png"
        image_filename = f"{uuid.uuid4().hex[:12]}.{ext}"
        image_full_path = IMAGES_DIR / image_filename
        with open(image_full_path, "wb") as f:
            f.write(image_data)
        image_path = f"data/images/{image_filename}"

        title = image_analysis.get("tags", [filename])[0] if image_analysis.get("tags") else filename
        description = image_analysis.get("description", "")
        if image_analysis.get("keywords"):
            description += f"\n\n**キーワード**: {image_analysis['keywords']}"

        return {
            "title": title[:20] if len(title) > 20 else title,
            "category": category,
            "content_type": "manual",
            "description": description,
            "tags": image_analysis.get("tags", []),
            "code_html": None,
            "code_css": None,
            "code_js": None,
            "notes": "",
            "image_path": image_path
        }
    except Exception as e:
        logger.error(f"[一括登録] 画像のみ処理エラー: {e}")
        return None


def match_files(uploaded_files) -> list[dict]:
    """アップロードファイルをMDと画像でマッチング"""
    md_files = {}
    image_files = {}

    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

    for f in uploaded_files:
        name = f.name
        stem = Path(name).stem.lower()  # 拡張子なしのファイル名
        ext = Path(name).suffix.lower()

        if ext in [".md", ".txt"]:
            md_files[stem] = f
        elif ext in image_extensions:
            image_files[stem] = f

    matched_items = []
    used_images = set()

    # MDファイルを処理
    for stem, md_file in md_files.items():
        item = {
            "type": "md",
            "md_file": md_file,
            "image_file": None,
            "name": md_file.name
        }
        # 同名の画像があれば紐づけ
        if stem in image_files:
            item["image_file"] = image_files[stem]
            item["type"] = "md+image"
            used_images.add(stem)
        matched_items.append(item)

    # 単独の画像ファイル
    for stem, img_file in image_files.items():
        if stem not in used_images:
            matched_items.append({
                "type": "image",
                "md_file": None,
                "image_file": img_file,
                "name": img_file.name
            })

    return matched_items


# ヘッダー
st.markdown("#### 📥 一括登録")

# カテゴリ選択
category = st.selectbox(
    "カテゴリ（全アイテム共通）",
    options=list(CATEGORIES.keys()),
    format_func=lambda x: CATEGORIES[x]
)

# 入力方法タブ
tab1, tab2, tab3 = st.tabs(["📋 テキスト貼り付け", "📁 単一ファイル", "🗂️ MD+画像一括"])

input_text = ""

with tab1:
    input_text = st.text_area(
        "テキストを貼り付け（Ctrl+V）",
        height=250,
        placeholder="複数のナレッジをまとめて貼り付けてください。\n\n▢ や --- や ## などで区切られていると自動で分割します。",
        key="paste_input"
    )

    if st.button("🔍 分割プレビュー", use_container_width=True, key="btn_preview_text"):
        if not input_text:
            st.warning("テキストを入力してください")
        else:
            with st.spinner("🔄 分割中..."):
                parts = split_text_auto(input_text)
                st.session_state.bulk_items = [{"raw": p, "image": None} for p in parts]
                st.success(f"✅ {len(parts)}件に分割されました")

with tab2:
    uploaded_file = st.file_uploader(
        "テキストファイル or Markdownファイル",
        type=["txt", "md"],
        key="file_input"
    )
    if uploaded_file:
        file_text = uploaded_file.read().decode("utf-8")
        st.text_area("ファイル内容プレビュー", file_text[:500] + "..." if len(file_text) > 500 else file_text, height=150, disabled=True)

        if st.button("🔍 分割プレビュー", use_container_width=True, key="btn_preview_file"):
            with st.spinner("🔄 分割中..."):
                parts = split_text_auto(file_text)
                st.session_state.bulk_items = [{"raw": p, "image": None} for p in parts]
                st.success(f"✅ {len(parts)}件に分割されました")

with tab3:
    st.markdown("**MDファイルと画像をまとめてアップロード**")
    st.caption("同名のMDと画像は自動で紐づけ（例: flexbox.md + flexbox.png）")

    uploaded_files = st.file_uploader(
        "ファイルを選択（複数可）",
        type=["md", "txt", "png", "jpg", "jpeg", "gif", "webp"],
        accept_multiple_files=True,
        key="multi_file_input"
    )

    if uploaded_files:
        matched = match_files(uploaded_files)

        st.markdown(f"**解析結果: {len(matched)}件**")

        for item in matched:
            icon = "📄" if item["type"] == "md" else "🖼️" if item["type"] == "image" else "📎"
            st.markdown(f"- {icon} {item['name']}" + (f" + 🖼️ {item['image_file'].name}" if item.get('image_file') and item['type'] == "md+image" else ""))

        if st.button("✨ 一括登録（MD+画像）", type="primary", use_container_width=True, key="btn_multi_register"):
            progress = st.progress(0)
            status = st.empty()

            success_count = 0
            error_count = 0

            for i, item in enumerate(matched):
                status.text(f"処理中... {i+1}/{len(matched)}: {item['name']}")
                progress.progress((i + 1) / len(matched))

                try:
                    if item["type"] == "image":
                        # 画像のみ
                        image_data = item["image_file"].getvalue()
                        processed = process_image_only(image_data, item["name"], category)
                    else:
                        # MD or MD+画像
                        md_text = item["md_file"].read().decode("utf-8")
                        item["md_file"].seek(0)  # リセット

                        image_data = None
                        if item.get("image_file"):
                            image_data = item["image_file"].getvalue()

                        processed = process_single_item(md_text, category, image_data)

                    if processed:
                        practice_id = st.session_state.data_manager.add(processed)
                        processed["id"] = practice_id
                        st.session_state.chroma_manager.add_practice(processed)
                        success_count += 1
                        logger.info(f"[一括登録] {i+1}/{len(matched)} 完了: {processed['title']}")
                    else:
                        error_count += 1

                except Exception as e:
                    error_count += 1
                    logger.error(f"[一括登録] {i+1} エラー: {e}")

            progress.empty()
            status.empty()

            if error_count == 0:
                st.success(f"✅ {success_count}件すべて登録完了！")
            else:
                st.warning(f"⚠️ {success_count}件成功、{error_count}件エラー")

# テキスト分割後の一括登録
if st.session_state.bulk_items:
    st.markdown("---")
    st.markdown(f"**{len(st.session_state.bulk_items)}件** を登録します")

    # プレビュー
    for i, item in enumerate(st.session_state.bulk_items[:5]):
        with st.expander(f"📄 アイテム {i+1}（{len(item['raw'])}文字）", expanded=(i < 2)):
            st.text(item["raw"][:300] + "..." if len(item["raw"]) > 300 else item["raw"])

    if len(st.session_state.bulk_items) > 5:
        st.caption(f"...他 {len(st.session_state.bulk_items) - 5}件")

    if st.button("✨ 一括登録", type="primary", use_container_width=True, key="btn_bulk_register"):
        progress = st.progress(0)
        status = st.empty()

        success_count = 0
        error_count = 0

        for i, item in enumerate(st.session_state.bulk_items):
            status.text(f"処理中... {i+1}/{len(st.session_state.bulk_items)}")
            progress.progress((i + 1) / len(st.session_state.bulk_items))

            try:
                processed = process_single_item(item["raw"], category, item.get("image"))

                practice_id = st.session_state.data_manager.add(processed)
                processed["id"] = practice_id
                st.session_state.chroma_manager.add_practice(processed)

                success_count += 1
                logger.info(f"[一括登録] {i+1}/{len(st.session_state.bulk_items)} 完了: {processed['title']}")

            except Exception as e:
                error_count += 1
                logger.error(f"[一括登録] {i+1} エラー: {e}")

        progress.empty()
        status.empty()

        if error_count == 0:
            st.success(f"✅ {success_count}件すべて登録完了！")
        else:
            st.warning(f"⚠️ {success_count}件成功、{error_count}件エラー")

        st.session_state.bulk_items = []

# フッター
st.markdown("---")
st.caption(f"📊 現在の登録数: {len(st.session_state.data_manager.get_all())}件")
