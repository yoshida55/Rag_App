"""
コード学習ページ
- サイドバー非表示 + 上部ナビ
- 左: コード表示（常時）
- 右: 質問チャット + 図解生成
- プレビュー: 折りたたみ式
"""
import streamlit as st
import streamlit.components.v1 as components
import json
import uuid
import base64
from pathlib import Path
from datetime import datetime
from config.settings import CATEGORIES, logger, PROJECT_ROOT
from modules.llm import generate_simple_response, generate_preview_svg, analyze_image
from modules.data_manager import DataManager
from modules.database import ChromaManager
from modules.answer_cache import AnswerCache

# 色付きコードエディタ
try:
    from streamlit_ace import st_ace
    HAS_ACE = True
except ImportError:
    HAS_ACE = False
    logger.warning("streamlit-ace not installed")

# クリップボード貼り付け
try:
    from streamlit_paste_button import paste_image_button
    HAS_PASTE_BUTTON = True
except ImportError:
    HAS_PASTE_BUTTON = False

# ページ設定（wide + サイドバー非表示）
st.set_page_config(page_title="コード学習", page_icon="📖", layout="wide", initial_sidebar_state="collapsed")

# サイドバー完全非表示 + 左余白最小化
st.markdown("""
<style>
    [data-testid="stSidebar"] { display: none; }
    [data-testid="stSidebarNav"] { display: none; }
    section[data-testid="stSidebar"] { display: none; }
    header[data-testid="stHeader"] { display: none; }
    .block-container {
        padding-top: 1.5rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 100%;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("### 📖 コード学習")

logger.info("=== コード学習ページ表示 ===")

# データマネージャー初期化
if "data_manager" not in st.session_state:
    st.session_state.data_manager = DataManager()
if "chroma_manager" not in st.session_state:
    st.session_state.chroma_manager = ChromaManager()

# セッション状態初期化
if "code_learning" not in st.session_state:
    st.session_state.code_learning = {
        "code_text": "",
        "sections": [],
        "image_bytes": None,
        "image_path": None,
        "image_analysis": "",
        "chat_history": [],
        "saved_id": None
    }

# 読み込みフラグ処理
if st.session_state.get("load_practice_id"):
    practice_id = st.session_state.load_practice_id
    st.session_state.load_practice_id = None
    p = st.session_state.data_manager.get_by_id(practice_id)
    if p:
        # HTMLとCSSを取得（別フィールドの場合と結合されている場合に対応）
        html_part = p.get("code_html", "") or ""
        css_part = p.get("code_css", "") or ""

        # CSSが空、またはHTMLと同じ値（バグで同じ値が入った場合）なら分離処理
        need_split = (not css_part) or (css_part == html_part)
        logger.info(f"[読込] need_split={need_split}, has_style={'<style' in html_part.lower()}")

        if need_split and html_part and "<style" in html_part.lower():
            import re
            # 全ての<style>タグの中身を抽出
            style_matches = re.findall(r'<style[^>]*>(.*?)</style>', html_part, re.DOTALL | re.IGNORECASE)
            if style_matches:
                css_part = "\n\n".join(style_matches).strip()
                html_part = re.sub(r'<style[^>]*>.*?</style>', '', html_part, flags=re.DOTALL | re.IGNORECASE).strip()
                logger.info(f"[読込] 分離成功: HTML={len(html_part)}文字, CSS={len(css_part)}文字")
            else:
                css_part = ""
                logger.info("[読込] <style>タグ見つからず")

        # 結合コードも保存
        combined = html_part
        if css_part:
            combined = f"{html_part}\n\n<style>\n{css_part}\n</style>"
        st.session_state.code_learning["code_text"] = combined

        # セッションステートとtext_areaの値を直接設定（固定key使用）
        st.session_state["loaded_html"] = html_part
        st.session_state["loaded_css"] = css_part
        st.session_state["html_editor"] = html_part
        st.session_state["css_editor"] = css_part

        logger.info(f"[読込] HTML: {len(html_part)}文字, CSS: {len(css_part)}文字")

        try:
            notes = p.get("notes", "")
            if notes and notes.startswith("["):
                st.session_state.code_learning["sections"] = json.loads(notes)
        except:
            pass
        if p.get("image_path"):
            img_path = PROJECT_ROOT / p["image_path"]
            if img_path.exists():
                with open(img_path, "rb") as f:
                    st.session_state.code_learning["image_bytes"] = f.read()
        # チャット履歴も復元（永続キャッシュ）
        if p.get("chat_history"):
            st.session_state.code_learning["chat_history"] = p["chat_history"]
            logger.info(f"[読込] チャット履歴復元: {len(p['chat_history'])}件")
        st.session_state.code_learning["saved_id"] = p["id"]
        st.toast("✅ 読み込み完了", icon="📚")
        st.rerun()

IMAGES_DIR = PROJECT_ROOT / "data" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 関数
# ============================================================
def save_image(image_bytes: bytes, filename: str) -> str:
    """画像保存"""
    path = IMAGES_DIR / filename
    with open(path, "wb") as f:
        f.write(image_bytes)
    return f"data/images/{filename}"


def ask_code_question(code: str, question: str, image_bytes: bytes = None, history: list = None) -> str:
    """コード/画像について質問（簡潔回答）"""
    from modules.usage_tracker import record_usage

    logger.debug(f"[質問] {question[:30]}...")

    # 履歴を構築（直近3件）
    history_text = ""
    if history:
        for h in history[-3:]:
            history_text += f"Q: {h['question']}\nA: {h['answer'][:150]}\n\n"

    # トークン概算（日本語対応）
    def estimate_tokens(text: str) -> int:
        if not text:
            return 0
        jp_chars = sum(1 for c in text if ord(c) > 127)
        en_chars = len(text) - jp_chars
        return int(jp_chars + en_chars / 4)

    # 画像がある場合は画像重視のプロンプト
    if image_bytes:
        prompt = f"""【画像とコードを両方見て回答】

添付画像: デザインカンプ/スクリーンショット
コード:
```
{code[:8000]}
```

{f"前の会話:\n{history_text}" if history_text else ""}

質問: {question}

【回答ルール】
- 画像の見た目とCSSコードを照らし合わせて説明
- 「display: flex」「grid」などの実際のプロパティ値を具体的に
- 画像のどの部分がコードのどこに対応するか説明
- 3〜5文で簡潔に（箇条書きOK）
"""
        try:
            from PIL import Image
            import io
            image = Image.open(io.BytesIO(image_bytes))
            import google.generativeai as genai
            model_name = "gemini-2.0-flash"
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([prompt, image])
            result = response.text

            # 使用量記録（画像は概算1000トークン）
            input_tokens = 1000 + estimate_tokens(prompt)
            output_tokens = estimate_tokens(result)
            record_usage(model_name, input_tokens, output_tokens)
            logger.debug(f"[画像質問] 記録: {model_name} in={input_tokens} out={output_tokens}")

            return result
        except Exception as e:
            logger.error(f"[画像質問] エラー: {e}")
            return f"エラー: {e}"
    else:
        # コードのみ（generate_simple_responseは内部でrecord_usage呼んでる）
        prompt = f"""以下のコードについて質問に回答。

コード:
```
{code[:8000]}
```

{f"前の会話:\n{history_text}" if history_text else ""}

質問: {question}

【回答ルール】
- 具体的なCSSプロパティ名と値を示す
- 3〜5文で簡潔に
"""
        try:
            return generate_simple_response(prompt, use_pro=True)
        except Exception as e:
            logger.error(f"[質問] エラー: {e}")
            return f"エラー: {e}"


def save_to_database(title: str, category: str, html_code: str, css_code: str, sections: list,
                     image_path: str = None, chat_history: list = None) -> str:
    """保存（HTML/CSS別々に）+ チャット履歴も保存"""
    description = "## コード学習\n\n"
    for i, sec in enumerate(sections, 1):
        description += f"### {i}. {sec['title']}\n{sec.get('description', '')}\n\n"

    sections_json = json.dumps(sections, ensure_ascii=False)

    new_practice = {
        "title": title,
        "category": category,
        "content_type": "code",
        "description": description,
        "tags": ["コード学習"],
        "code_html": html_code,
        "code_css": css_code if css_code else None,
        "code_js": None,
        "image_path": image_path,
        "notes": sections_json,
        "generated_svg": None,
        "generated_html": None,
        "chat_history": chat_history if chat_history else []  # チャット履歴永続保存
    }

    try:
        practice_id = st.session_state.data_manager.add(new_practice)
        new_practice["id"] = practice_id
        st.session_state.chroma_manager.add_practice(new_practice)
        return practice_id
    except Exception as e:
        logger.error(f"[保存] エラー: {e}")
        return None


# ============================================================
# UI: 上部ナビゲーション
# ============================================================
nav_cols = st.columns([1, 1, 1, 1, 4])
with nav_cols[0]:
    if st.button("🔍 検索", use_container_width=True):
        st.switch_page("pages/1_🔍_検索.py")
with nav_cols[1]:
    if st.button("📋 一覧", use_container_width=True):
        st.switch_page("pages/3_📋_一覧.py")
with nav_cols[2]:
    if st.button("⚙️ 設定", use_container_width=True):
        st.switch_page("pages/5_⚙️_設定.py")
with nav_cols[3]:
    if st.button("💾 保存済み", use_container_width=True):
        st.session_state.show_saved = not st.session_state.get("show_saved", False)
        st.rerun()

st.markdown("---")

# ============================================================
# 保存済みデータ（トグル表示）
# ============================================================
if st.session_state.get("show_saved", False):
    st.markdown("##### 💾 保存済みコード学習データ")
    all_practices = st.session_state.data_manager.get_all()
    code_learning_practices = [p for p in all_practices if "コード学習" in p.get("tags", [])]

    if not code_learning_practices:
        st.info("まだ保存されたデータがありません")
    else:
        for p in code_learning_practices[:5]:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{p.get('title', '無題')}** ({p.get('category', '')})")
            with col2:
                if st.button("📚 読込", key=f"load_{p['id']}"):
                    st.session_state.load_practice_id = p["id"]
                    st.session_state.show_saved = False
                    st.rerun()
    st.markdown("---")

# ============================================================
# プレビュー（折りたたみ）
# ============================================================
with st.expander("📷 プレビュー画像（クリックで展開）", expanded=False):
    prev_cols = st.columns([2, 1])
    with prev_cols[0]:
        if st.session_state.code_learning.get("image_bytes"):
            st.image(st.session_state.code_learning["image_bytes"], use_container_width=True)
        else:
            st.info("画像なし")
    with prev_cols[1]:
        # 画像アップロード
        if HAS_PASTE_BUTTON:
            paste_result = paste_image_button("📋 Ctrl+V", key="paste_btn")
            if paste_result.image_data is not None:
                try:
                    image_bytes = base64.b64decode(paste_result.image_data.split(",")[1])
                    st.session_state.code_learning["image_bytes"] = image_bytes
                    st.rerun()
                except:
                    pass

        uploaded = st.file_uploader("画像選択", type=["png", "jpg", "jpeg", "gif"], key="img_upload", label_visibility="collapsed")
        if uploaded:
            # 新しい画像の場合のみ更新（無限ループ防止）
            new_bytes = uploaded.getvalue()
            if st.session_state.code_learning.get("image_bytes") != new_bytes:
                st.session_state.code_learning["image_bytes"] = new_bytes
                st.rerun()

        if st.session_state.code_learning.get("image_bytes"):
            if st.button("🗑️ 画像削除"):
                st.session_state.code_learning["image_bytes"] = None
                st.rerun()

# ============================================================
# メインレイアウト: HTML(狭) | CSS(広め) | 質問
# ============================================================

# コードからHTML/CSS分離
def split_html_css(code: str) -> tuple[str, str]:
    """コードをHTMLとCSSに分離"""
    html_part = ""
    css_part = ""

    # <style>タグ内をCSS、それ以外をHTMLに
    import re
    style_match = re.search(r'<style[^>]*>(.*?)</style>', code, re.DOTALL | re.IGNORECASE)
    if style_match:
        css_part = style_match.group(1).strip()
        html_part = re.sub(r'<style[^>]*>.*?</style>', '', code, flags=re.DOTALL | re.IGNORECASE).strip()
    else:
        html_part = code

    return html_part, css_part

# 現在のコードを分離（読み込み時に設定された値を使う）
html_val = st.session_state.get("loaded_html", "")
css_val = st.session_state.get("loaded_css", "")

# ------------------------------------------------------------
with st.expander("📄 HTML", expanded=True):
    # ウィジェット表示前にセッションステートを初期化
    if "html_editor" not in st.session_state:
        st.session_state["html_editor"] = html_val
    
    # st.text_areaを使用（st_aceは無限ループを引き起こすため無効化）
    html_input = st.text_area(
        "HTMLコード",
        height=300,
        key="html_editor"
    )

# ------------------------------------------------------------
# CSS | 質問
# ------------------------------------------------------------
col_css, col_chat = st.columns([3, 2])

with col_css:
    # ウィジェット表示前にセッションステートを初期化
    if "css_editor" not in st.session_state:
        st.session_state["css_editor"] = css_val
    
    # st.text_areaを使用（st_aceは無限ループを引き起こすため無効化）
    css_input = st.text_area(
        "CSSコード",
        height=700,
        key="css_editor"
    )

# 空文字列対策
html_input = html_input if html_input else ""
css_input = css_input if css_input else ""

# combined_codeは保存時のみ使う（毎回session_state更新しない）
combined_code = html_input
if css_input.strip():
    combined_code = f"{html_input}\n\n<style>\n{css_input}\n</style>"

# 保存エリア（HTML/CSS列の下）
with st.container():
    save_cols = st.columns([2, 1, 1, 1])
    with save_cols[0]:
        title_input = st.text_input("タイトル", placeholder="例: Flexboxレイアウト", key="title_in")
    with save_cols[1]:
        category = st.selectbox("カテゴリ", list(CATEGORIES.keys()), format_func=lambda x: CATEGORIES[x], key="cat_sel")
    with save_cols[2]:
        if st.button("💾 保存", use_container_width=True):
            # session_stateから直接値を取得（keyで管理されている）
            save_html = st.session_state.get("html_editor", "")
            save_css = st.session_state.get("css_editor", "")
            save_title = st.session_state.get("title_in", "")
            
            # デバッグ: 何が入ってるか確認
            logger.info(f"[保存ボタン] 押下検知")
            logger.info(f"[保存] title='{save_title}', html_len={len(save_html)}, css_len={len(save_css)}")
            st.info(f"🔍 デバッグ: title='{save_title}', html={len(save_html)}文字, css={len(save_css)}文字")

            has_code = bool(save_html.strip()) or bool(save_css.strip())
            has_title = bool(save_title.strip())

            if not has_title:
                st.warning("⚠️ タイトルを入力してください")
                logger.info("[保存] タイトルなし")
            elif not has_code:
                st.warning("⚠️ HTMLまたはCSSを入力してください")
                logger.info("[保存] コードなし")
            else:
                logger.info("[保存] 条件OK、保存開始...")
                sections = [{"title": "全体", "start_line": 1, "end_line": len(save_html.split('\n')), "description": "コード全体", "content": save_html}]
                image_path = None
                if st.session_state.code_learning.get("image_bytes"):
                    filename = f"{uuid.uuid4().hex[:8]}.png"
                    image_path = save_image(st.session_state.code_learning["image_bytes"], filename)
                    logger.info(f"[保存] 画像保存: {image_path}")
                saved_id = save_to_database(save_title, category, save_html, save_css, sections, image_path, 
                                            st.session_state.code_learning.get("chat_history", []))
                if saved_id:
                    st.session_state.code_learning["saved_id"] = saved_id
                    st.success(f"✅ 保存完了！ ID: {saved_id[:8]}...")
                    logger.info(f"[保存] 成功: {saved_id}")
                else:
                    st.error("❌ 保存に失敗しました")
                    logger.error("[保存] 失敗")
    with save_cols[3]:
        if st.button("🗑️ クリア", key="clear_code", use_container_width=True):
            st.session_state.code_learning = {
                "code_text": "", "sections": [], "image_bytes": None,
                "image_path": None, "image_analysis": "", "chat_history": [], "saved_id": None
            }
            if "html_area" in st.session_state:
                del st.session_state["html_area"]
            if "css_area" in st.session_state:
                del st.session_state["css_area"]
            st.rerun()

# ------------------------------------------------------------
# 右: 質問チャット
# ------------------------------------------------------------
with col_chat:
    st.markdown("##### 💬 質問")

    # 質問入力
    question = st.text_input(
        "質問を入力",
        placeholder="例: このCSSの構成は？ / flexboxはどう使ってる？",
        key="question_input"
    )

    q_cols = st.columns([2, 1])
    with q_cols[0]:
        if st.button("🤖 質問する", type="primary", use_container_width=True):
            # 現在のエディタ内容を使用（combined_code）
            code_for_question = combined_code if combined_code.strip() else st.session_state.code_learning.get("code_text", "")

            if question.strip() and code_for_question.strip():
                # キャッシュ初期化（未初期化なら）
                if "code_answer_cache" not in st.session_state:
                    st.session_state.code_answer_cache = AnswerCache()
                
                # 類似クエリをキャッシュから検索（質問+コードの最初の200文字で検索）
                cache_query = f"{question} | code:{code_for_question[:200]}"
                cached = st.session_state.code_answer_cache.find_similar(cache_query)
                
                if cached:
                    # キャッシュヒット！
                    answer = cached["answer"]
                    st.toast(f"💾 キャッシュ使用（類似度: {cached['similarity']:.0%}）")
                    st.session_state.code_learning["chat_history"].append({
                        "question": question,
                        "answer": answer,
                        "from_cache": True
                    })
                    st.session_state.code_learning["code_text"] = code_for_question
                    st.rerun()
                else:
                    # 新規生成
                    with st.spinner("回答生成中..."):
                        answer = ask_code_question(
                            code_for_question,
                            question,
                            st.session_state.code_learning.get("image_bytes"),
                            st.session_state.code_learning.get("chat_history", [])
                        )
                        # キャッシュに保存
                        st.session_state.code_answer_cache.add(cache_query, answer)
                        st.session_state.code_learning["chat_history"].append({
                            "question": question,
                            "answer": answer
                        })
                        st.session_state.code_learning["code_text"] = code_for_question
                        st.rerun()
            elif not code_for_question.strip():
                st.warning("コードを入力してください")
            else:
                st.warning("質問を入力")
    with q_cols[1]:
        if st.button("🗑️ クリア", key="clear_chat", use_container_width=True):
            st.session_state.code_learning["chat_history"] = []
            st.rerun()

    st.markdown("---")

    # チャット履歴（新しい順）
    chat_history = st.session_state.code_learning.get("chat_history", [])
    if chat_history:
        for i, h in enumerate(reversed(chat_history)):
            idx = len(chat_history) - 1 - i

            # 質問
            st.markdown(f"**Q:** {h['question']}")

            # 回答
            st.markdown(f"**A:** {h['answer']}")

            # 図解生成ボタン（チャット履歴に保存してキャッシュ）
            diagram_key = f"diagram_{idx}"
            
            # 既に図解がある場合は表示キーに設定
            if h.get("svg") and f"svg_{idx}" not in st.session_state:
                st.session_state[f"svg_{idx}"] = h["svg"]

            if st.button(f"📐 図解生成", key=diagram_key):
                # キャッシュ確認（チャット履歴に保存済みの図解）
                if h.get("svg"):
                    st.session_state[f"svg_{idx}"] = h["svg"]
                    st.toast("💾 キャッシュから取得")
                    st.rerun()
                else:
                    with st.spinner("図解生成中..."):
                        svg = generate_preview_svg(h['answer'][:500], h['question'][:30])
                        if svg:
                            # チャット履歴に図解を保存（永続キャッシュ）
                            st.session_state.code_learning["chat_history"][idx]["svg"] = svg
                            st.session_state[f"svg_{idx}"] = svg
                            st.rerun()
                        else:
                            st.error("図解生成失敗")

            # 生成済みSVG表示（拡大ボタン付き）
            svg_key = f"svg_{idx}"
            if st.session_state.get(svg_key):
                import base64
                import urllib.parse
                svg_content = st.session_state[svg_key]
                # URLエンコードでエスケープ
                svg_encoded = urllib.parse.quote(svg_content, safe='')
                svg_display_html = f"""
                    <div style="background: white; padding: 10px; border-radius: 8px; border: 1px solid #4caf50; position: relative;">
                        <button onclick="var w=window.open('','_blank','width=1000,height=700');w.document.write('<html><head><title>図解</title></head><body style=\\'background:#fff;margin:20px;\\'>' + decodeURIComponent('{svg_encoded}') + '</body></html>');w.document.close();"
                           style="position: absolute; top: 5px; right: 10px; background: #1976d2; color: white; 
                                  padding: 5px 10px; border-radius: 4px; border: none; cursor: pointer; font-size: 12px; z-index: 10;">
                           🔍 拡大表示
                        </button>
                        {svg_content}
                    </div>
                """
                components.html(svg_display_html, height=500)
                
                # 保存ボタン
                col_save_svg, col_close_svg = st.columns([1, 1])
                with col_save_svg:
                    if st.button("💾 図解を保存", key=f"save_svg_{idx}"):
                        # 現在のpracticeに図解を追加保存
                        saved_id = st.session_state.code_learning.get("saved_id")
                        if saved_id:
                            st.session_state.data_manager.update(saved_id, {"generated_svg": svg_content})
                            st.success("✅ 図解を保存しました！")
                        else:
                            # 新規で保存
                            new_practice = {
                                "title": f"図解: {h['question'][:30]}",
                                "category": "html_css",
                                "content_type": "manual",
                                "description": h['answer'][:500],
                                "generated_svg": svg_content,
                                "tags": ["図解", "コード学習"],
                            }
                            practice_id = st.session_state.data_manager.add(new_practice)
                            st.success(f"✅ 新規保存しました！")
                with col_close_svg:
                    if st.button("✖ 閉じる", key=f"close_svg_{idx}"):
                        del st.session_state[svg_key]
                        st.rerun()

            st.markdown("---")
    else:
        st.info("質問するとここに回答が表示されます")

# デバッグ（詳細版）
with st.expander("🐛 デバッグ", expanded=True):
    st.write("### session_state直接確認")
    st.write(f"**st.session_state['html_editor']**: {repr(st.session_state.get('html_editor', 'キーなし'))[:100]}")
    st.write(f"**st.session_state['css_editor']**: {repr(st.session_state.get('css_editor', 'キーなし'))[:100]}")
    st.write(f"**st.session_state['title_in']**: {repr(st.session_state.get('title_in', 'キーなし'))}")
    st.write("---")
    st.write("### 変数確認")
    st.write(f"**html_input長さ**: {len(html_input)} / **css_input長さ**: {len(css_input)}")
    st.write(f"**html_val長さ（loaded_html）**: {len(html_val)} / **css_val長さ（loaded_css）**: {len(css_val)}")
    st.write("---")
    st.write("### session_stateキー一覧")
    editor_keys = [k for k in st.session_state.keys() if 'editor' in k.lower() or 'html' in k.lower() or 'css' in k.lower()]
    st.write(editor_keys)
