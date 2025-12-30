# ... (imports omitted) ...
import streamlit as st
import streamlit.components.v1 as components
import json
import uuid
import base64
from pathlib import Path
from datetime import datetime
from config.settings import CATEGORIES, logger, PROJECT_ROOT
from modules.llm import generate_simple_response, generate_preview_svg, analyze_image, analyze_html_css_relations, extract_code_sections
from modules.data_manager import DataManager
from modules.database import ChromaManager
from modules.answer_cache import AnswerCache
from modules.section_cache import get_cached_sections, save_sections_to_cache, get_code_hash

# Monaco Editor (VSCode風エディタ)
try:
    from streamlit_monaco import st_monaco
    MONACO_AVAILABLE = True
except ImportError:
    MONACO_AVAILABLE = False

# 色付きコードエディタ (Optional)
try:
    from streamlit_ace import st_ace
    HAS_ACE = True
except ImportError:
    HAS_ACE = False

# クリップボード貼り付け (Optional)
try:
    from streamlit_paste_button import paste_image_button
    HAS_PASTE_BUTTON = True
except ImportError:
    HAS_PASTE_BUTTON = False

# 1. ページ設定
st.set_page_config(page_title="コード学習", page_icon="📖", layout="wide", initial_sidebar_state="collapsed")

# 2. カスタムCSS（サイドバー非表示等）- 共通モジュール使用
from modules.ui_styles import inject_common_styles, get_compact_title_styles

st.markdown(inject_common_styles(
    include_headings=True,
    sidebar_mode="hidden",
    include_compact_title=True
), unsafe_allow_html=True)

st.markdown('<div class="compact-title">📖 コード学習</div>', unsafe_allow_html=True)
logger.info("=== コード学習ページ表示 ===")

# 3. 初期化（最優先：他のロジックより前に実行）
if "data_manager" not in st.session_state:
    st.session_state.data_manager = DataManager()
    
# 検索用マネージャー初期化
if "chroma_manager" not in st.session_state:
    st.session_state.chroma_manager = ChromaManager(persistent=False)
    # JSONからデータ読み込み（必要なら）
    # st.session_state.chroma_manager.load_from_json()
if "chroma_manager" not in st.session_state:
    st.session_state.chroma_manager = ChromaManager()

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

# 4. ナビゲーション（初期化の直後に配置）
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

# 5. 保存済みデータの読み込みロジック（トグル表示）
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

# 6. 外部からの読み込み処理（一覧ページ等からの遷移）
if st.session_state.get("load_practice_id"):
    practice_id = st.session_state.load_practice_id
    st.session_state.load_practice_id = None
    p = st.session_state.data_manager.get_by_id(practice_id)
    if p:
        # HTMLとCSSを取得
        html_part = p.get("code_html", "") or ""
        css_part = p.get("code_css", "") or ""

        # セッションステートへのセット
        st.session_state["loaded_html"] = html_part
        st.session_state["loaded_css"] = css_part
        st.session_state["html_editor"] = html_part
        st.session_state["css_editor"] = css_part

        # その他データの復元
        try:
            notes = p.get("notes", "")
            if notes and notes.startswith("["):
                sections_data = json.loads(notes)
                # 形式を検証してから復元
                if sections_data and isinstance(sections_data, list) and len(sections_data) > 0:
                    first = sections_data[0]
                    if "html" in first and "css" in first:
                        st.session_state.code_sections = sections_data
                        import hashlib
                        code_hash = hashlib.md5((html_part + css_part).encode('utf-8')).hexdigest()
                        st.session_state.section_code_hash = code_hash
                        st.toast("✅ セクション情報を復元しました（AI解析スキップ）")
                    else:
                        # 古い形式のデータは無視
                        pass
        except:
            pass
        if p.get("image_path"):
            img_path = PROJECT_ROOT / p["image_path"]
            if img_path.exists():
                with open(img_path, "rb") as f:
                    st.session_state.code_learning["image_bytes"] = f.read()
                    # 拡張子を保存
                    st.session_state.code_learning["image_ext"] = img_path.suffix.lower().replace(".", "")
        
        # 図解（SVG）もあればロード（独立して保存）
        if p.get("generated_svg"):
            st.session_state.code_learning["generated_svg_bytes"] = p["generated_svg"].encode('utf-8')
        
        # チャット履歴の復元（なければ空リスト）
        history = p.get("chat_history", [])
        
        # 図解（SVG）がある場合の処理
        loaded_svg = p.get("generated_svg")
        if loaded_svg and history:
            # 履歴がある場合、最後の会話にSVGを紐付ける
            history[-1]["svg"] = loaded_svg
            
        st.session_state.code_learning["chat_history"] = history
        
        st.session_state.code_learning["saved_id"] = p["id"]
        st.toast("✅ 読み込み完了", icon="📚")
        st.rerun()

IMAGES_DIR = PROJECT_ROOT / "data" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# 7. 関数定義
def save_image(image_bytes: bytes, filename: str) -> str:
    path = IMAGES_DIR / filename
    with open(path, "wb") as f:
        f.write(image_bytes)
    return f"data/images/{filename}"

def ask_code_question(code: str, question: str, image_bytes: bytes = None, history: list = None) -> str:
    """コードに関する質問をAIに送信（会話履歴を考慮）"""
    from modules.usage_tracker import record_usage
    
    # 直近3件の会話履歴を構築
    history_text = ""
    if history:
        for h in history[-3:]:
            history_text += f"Q: {h['question']}\nA: {h['answer'][:200]}\n\n"
    
    # プロンプト構築（履歴を含める）
    if history_text:
        prompt = f"""過去の会話:
{history_text}
---
コード:
```
{code[:8000]}
```

新しい質問: {question}

上記の会話の流れを踏まえて回答してください。"""
    else:
        prompt = f"コード: ```{code[:8000]}```\n質問: {question}"
    
    try:
        return generate_simple_response(prompt, use_pro=True)
    except Exception as e:
        return f"エラー: {e}"

def save_to_database(title: str, category: str, html_code: str, css_code: str, sections: list,
                     image_path: str = None, chat_history: list = None) -> str:
    # (省略: 元のロジックと同じ)
    description = "## コード学習\n\n"
    for i, sec in enumerate(sections, 1):
        description += f"### {i}. {sec['title']}\n{sec.get('description', '')}\n\n"
    sections_json = json.dumps(sections, ensure_ascii=False)
    new_practice = {
        "title": title, "category": category, "content_type": "code", "description": description,
        "tags": ["コード学習"], "code_html": html_code, "code_css": css_code,
        "image_path": image_path, "notes": sections_json, "chat_history": chat_history or []
    }
    try:
        pid = st.session_state.data_manager.add(new_practice)
        new_practice["id"] = pid
        st.session_state.chroma_manager.add_practice(new_practice)
        return pid
    except Exception as e:
        logger.error(e)
        return None

# 8. 分析モードのビュー（初期化後に配置）
if st.session_state.get("show_analysis_mode", False):
    st.markdown("### 🔍 クラスとスタイルの対応分析")
    st.info("AIがコードを解析し、関係性をコメントで追記しました。")

    if st.button("🔙 エディタに戻る"):
        st.session_state.show_analysis_mode = False
        st.rerun()

    if "analyzed_html" not in st.session_state or "analyzed_css" not in st.session_state:
        with st.spinner("AIがコードを分析中...（約5~10秒）"):
            current_html = st.session_state.get("html_editor", "")
            current_css = st.session_state.get("css_editor", "")
            a_html, a_css = analyze_html_css_relations(current_html, current_css)
            st.session_state.analyzed_html = a_html
            st.session_state.analyzed_css = a_css

    a_col1, a_col2 = st.columns(2)
    with a_col1:
        st.markdown("**📄 HTML (解説付き)**")
        st.code(st.session_state.analyzed_html, language="html")
    with a_col2:
        st.markdown("**🎨 CSS (解説付き)**")
        st.code(st.session_state.analyzed_css, language="css")
    st.markdown("---")

# 8.5. セクション別表示モード（フォーカスモード）
if st.session_state.get("show_section_mode", False):
    st.markdown("### 🔍 セクション別表示（フォーカスモード）")
    st.info("AIがコードを機能ごとのセクションに分割しました。見たい部分を選択してください。")

    if st.button("🔙 全体表示に戻る", key="back_from_section"):
        st.session_state.show_section_mode = False
        st.rerun()

    # セクション分割実行（キャッシュロジック強化）
    # コードの取得（エディタの値 または ロードなどの初期値）
    current_html = st.session_state.get("html_editor", "") or st.session_state.get("loaded_html", "")
    current_css = st.session_state.get("css_editor", "") or st.session_state.get("loaded_css", "")

    # コード変更検知用のハッシュ作成
    code_hash = get_code_hash(current_html, current_css)
    
    # セクションデータの検証（古いフォーマットを検知してクリア）
    def validate_sections(sections):
        """セクションデータが正しいフォーマットか検証"""
        if not sections:
            return False
        # 最初のセクションにhtml, cssキーがあるか確認
        first = sections[0] if sections else {}
        return "html" in first and "css" in first
    
    # 1. まずセッションキャッシュをチェック
    existing_sections = st.session_state.get("code_sections", [])
    stored_hash = st.session_state.get("section_code_hash", "")
    
    # セッションキャッシュが有効かチェック
    session_cache_valid = (
        existing_sections 
        and stored_hash == code_hash 
        and validate_sections(existing_sections)
    )
    
    # 2. セッションがなければ永続キャッシュをチェック
    if not session_cache_valid:
        persistent_sections = get_cached_sections(current_html, current_css)
        if persistent_sections:
            # 永続キャッシュをセッションに復元
            st.session_state.code_sections = persistent_sections
            st.session_state.section_code_hash = code_hash
            existing_sections = persistent_sections
            session_cache_valid = True
            st.toast("✅ キャッシュから復元しました（AI解析スキップ）")
    
    # デバッグ情報（画面表示）
    debug_msg = f"キャッシュ: 既存={len(existing_sections)}件, 有効={session_cache_valid}"
    st.caption(f"🔧 {debug_msg}")
    
    # 3. キャッシュがなければAI解析
    if not session_cache_valid:
        if not current_html.strip() and not current_css.strip():
            st.warning("⚠️ 解析するコードがありません。コードを入力してから実行してください。")
        else:
            with st.spinner("AIがコードをセクション分割中...（約5~10秒）"):
                logger.info(f"[セクション分割開始] HTML: {len(current_html)}文字, CSS: {len(current_css)}文字")
                sections = extract_code_sections(current_html, current_css)
                
                # 結果を検証、不正ならフォールバック
                if not validate_sections(sections):
                    logger.warning(f"[セクション] AIの返却が不正、フォールバック使用")
                    sections = [{"name": "全体", "html": current_html, "css": current_css}]
                
                # セッションに保存
                st.session_state.code_sections = sections
                st.session_state.section_code_hash = code_hash
                
                # 永続キャッシュにも保存
                save_sections_to_cache(current_html, current_css, sections)
                
                logger.info(f"[セクション] 保存完了: {len(sections)}件")
    
    # セクション選択
    sections = st.session_state.get("code_sections", [])
    if sections:
        # --- Custom CSS for Focus Mode Layout Tweak ---
        st.markdown("""
        <style>
            /* カラム間の隙間を極小にする */
            [data-testid="column"] {
                padding: 0 !important;
            }
            [data-testid="stHorizontalBlock"] {
                gap: 0.3rem !important;
            }
            /* ヘッダーの余白を詰める */
            div[data-testid="stMarkdownContainer"] > p {
                margin-bottom: 0.2rem !important;
            }
            /* チャットエリアの調整 */
            .stTextInput {
                margin-bottom: 0.5rem !important;
            }
            /* コードブロックを左詰めにする */
            [data-testid="stCode"] {
                padding-left: 0 !important;
            }
            [data-testid="stCode"] pre {
                padding-left: 0.5rem !important;
                margin-left: 0 !important;
            }
        </style>
        """, unsafe_allow_html=True)

        # セクション選択UI
        # 古いセッションデータとの互換性対応 (nameキーがない場合)
        sec_names = [s.get("name", f"Section {i+1}") for i, s in enumerate(sections)]
        selected_idx = st.radio("表示するセクション", range(len(sec_names)), 
                                format_func=lambda i: sec_names[i],
                                horizontal=True, label_visibility="collapsed")
        
        # インデックスベースで選択（名前マッチングの問題を回避）
        selected_sec = sections[selected_idx] if selected_idx < len(sections) else None
        
        if selected_sec:
            # 3カラムレイアウト: HTML | CSS | Chat
            # HTML:2.5, CSS:2.5, Chat:4.0 (Chatをさらに広く)
            col_h, col_c, col_q = st.columns([2.5, 2.5, 4.0])
            
            # 高さ設定
            AREA_HEIGHT = 650
            
            # --- HTML Column ---
            with col_h:
                st.markdown(f"**📄 HTML**")
                html_content = selected_sec.get("html", "(データなし)")
                if MONACO_AVAILABLE:
                    st_monaco(
                        value=html_content,
                        language="html",
                        height=f"{AREA_HEIGHT}px",
                        theme="vs-dark",
                    )
                else:
                    with st.container(height=AREA_HEIGHT):
                        st.code(html_content, language="html")

            # --- CSS Column ---
            with col_c:
                st.markdown(f"**🎨 CSS**")
                css_content = selected_sec.get("css", "(データなし)")
                if MONACO_AVAILABLE:
                    st_monaco(
                        value=css_content,
                        language="css",
                        height=f"{AREA_HEIGHT}px",
                        theme="vs-dark",
                    )
                else:
                    with st.container(height=AREA_HEIGHT):
                        st.code(css_content, language="css")

            # --- Chat Column ---
            with col_q:
                st.markdown("**💬 AIチャット**")
                
                # 参考画像表示 (フォーカスモード)
                if st.session_state.code_learning.get("image_bytes"):
                    with st.expander("📌 参考画像", expanded=False):
                        img_data = st.session_state.code_learning["image_bytes"]
                        img_ext = st.session_state.code_learning.get("image_ext", "")
                        
                        try:
                            # 拡張子で判定
                            is_svg = (img_ext == "svg")
                            
                            if is_svg:
                                # SVGはst.imageで表示されない場合があるためcomponents.htmlを使用
                                svg_code = img_data.decode("utf-8")
                                
                                # SVGタグ抽出（余計な文字を除去）
                                start = svg_code.find("<svg")
                                if start != -1:
                                    svg_code = svg_code[start:]
                                    end = svg_code.rfind("</svg>")
                                    if end != -1:
                                        svg_code = svg_code[:end+6]

                                # DEBUG: データの中身を確認
                                st.text_area("SVG Data (Debug)", value=svg_code[:500], height=100)
                                st.caption(f"Length: {len(svg_code)}")

                                # 完全なHTML構造でラップして表示（安定化）
                                html_content = f"""
                                <!DOCTYPE html>
                                <html>
                                <head>
                                    <style>
                                        body {{ margin: 0; padding: 20px; background-color: #ffffff; display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
                                        svg {{ max-width: 100%; height: auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                                    </style>
                                </head>
                                <body>
                                    {svg_code}
                                </body>
                                </html>
                                """
                                st.components.v1.html(html_content, height=450, scrolling=True)
                            else:
                                st.image(img_data, use_container_width=True)
                        except Exception as e:
                            st.error(f"画像表示エラー: {e}")
                
                with st.container(height=AREA_HEIGHT):
                    # Chat Logic
                    f_question = st.text_input("質問", placeholder="解説して...", key="focus_q_input")
                    
                    if st.button("送信", key="focus_q_btn", use_container_width=True, type="primary"):
                        if f_question.strip():
                            f_code_context = f"HTML:\n{selected_sec.get('html', '')}\n\nCSS:\n{selected_sec.get('css', '')}"
                            with st.spinner("思考中..."):
                                f_answer = ask_code_question(
                                    f_code_context, f_question, None, st.session_state.code_learning.get("chat_history", [])
                                )
                                
                                # 関連図解検索（ベクトル検索）
                                related_visuals = []
                                try:
                                    if "chroma_manager" in st.session_state:
                                        # 設定値の類似度で検索
                                        visual_results = st.session_state.chroma_manager.search_visuals(
                                            f_question, 
                                            min_score=st.session_state.get("related_visual_threshold", 0.70), 
                                            top_k=1
                                        )
                                        if visual_results:
                                            # 実データの取得
                                            for res in visual_results:
                                                p_data = st.session_state.data_manager.get_by_id(res["id"])
                                                if p_data and p_data.get("generated_svg"):
                                                    related_visuals.append({
                                                        "svg": p_data["generated_svg"],
                                                        "score": res["score"],
                                                        "title": p_data.get("title", "関連図解")
                                                    })
                                                    st.toast(f"💡 関連図解発見 ({res['score']:.0%})")
                                except Exception as e:
                                    logger.error(f"Visual search failed: {e}")

                                st.session_state.code_learning["chat_history"].append({
                                    "question": f_question, 
                                    "answer": f_answer,
                                    "related_visuals": related_visuals
                                })
                                st.rerun()

                    st.markdown("---")

                    # Chat History - 最新の1件のみ表示（ユーザー要望）
                    history = st.session_state.code_learning.get("chat_history", [])
                    if history:
                        st.markdown("##### 💬 最新の回答")
                        
                        # 最新の1件を取得
                        h = history[-1]
                        idx = len(history) - 1
                        
                        st.markdown(f"**🧑‍💻 Q:** {h['question']}")
                        st.markdown(f"**🤖 AI:** \n\n{h['answer']}")
                        
                        # 関連図解の表示
                        if h.get("related_visuals"):
                            for vis in h["related_visuals"]:
                                with st.expander(f"💡 関連図解: {vis.get('title', '図解')} - 一致度{vis.get('score', 0):.0%}", expanded=True):
                                    import urllib.parse
                                    svg_encoded = urllib.parse.quote(vis["svg"], safe='')
                                    svg_html = f"""
                                    <div style="background:white;padding:10px;position:relative;">
                                        <button onclick="var w=window.open('','_blank','width=1200,height=800');w.document.write('<html><body style=\\'margin:0;display:flex;justify-content:center;align-items:center;height:100vh;\\'>' + decodeURIComponent('{svg_encoded}') + '</body></html>');w.document.close();" 
                                        style="position:absolute;top:5px;right:5px;z-index:100;cursor:pointer;background:#1976d2;color:white;border:none;padding:5px 10px;border-radius:4px;">🔍 拡大</button>
                                        {vis["svg"]}
                                    </div>
                                    """
                                    st.components.v1.html(svg_html, height=300, scrolling=True)
                        
                        # Diagram Generation & Display
                        diagram_key = f"focus_diagram_{idx}"
                        if h.get("svg") and f"focus_svg_{idx}" not in st.session_state:
                            st.session_state[f"focus_svg_{idx}"] = h["svg"]

                        if st.button(f"📐 図解生成", key=diagram_key):
                            if h.get("svg"):
                                st.session_state[f"focus_svg_{idx}"] = h["svg"]
                                st.toast("💾 キャッシュから取得")
                                st.rerun()
                            else:
                                with st.spinner("図解生成中..."):
                                    svg = generate_preview_svg(h['answer'][:500], h['question'][:30])
                                    if svg:
                                        st.session_state.code_learning["chat_history"][idx]["svg"] = svg
                                        st.session_state[f"focus_svg_{idx}"] = svg
                                        st.rerun()
                                    else:
                                        st.error("図解生成失敗")
                        
                        # Show SVG
                        svg_key = f"focus_svg_{idx}"
                        if st.session_state.get(svg_key):
                            import urllib.parse
                            svg_content = st.session_state[svg_key]
                            svg_encoded = urllib.parse.quote(svg_content, safe='')
                            
                            # Enlarge Button & View
                            svg_display_html = f"""
                                <div style="background: white; padding: 10px; border-radius: 8px; border: 1px solid #4caf50; position: relative;">
                                    <button onclick="var w=window.open('','_blank','width=1200,height=800');w.document.write('<html><head><title>図解拡大</title></head><body style=\\'background:#fff;margin:0;display:flex;justify-content:center;align-items:center;height:100vh;\\'>' + decodeURIComponent('{svg_encoded}') + '</body></html>');w.document.close();"
                                        style="position: absolute; top: 5px; right: 10px; background: #1976d2; color: white; padding: 5px 10px; border-radius: 4px; border: none; cursor: pointer; font-size: 12px; z-index: 100;">
                                        🔍 拡大
                                    </button>
                                    {svg_content}
                                </div>
                            """
                            components.html(svg_display_html, height=350, scrolling=True)
                            
                            # Save Button & Delete Button
                            col_save, col_del = st.columns([1, 1])
                            with col_save:
                                if st.button("💾 図解を保存", key=f"focus_save_svg_{idx}"):
                                    # タイトルを自動生成（質問内容から短く）
                                    short_title = h['question'][:20] + "..." if len(h['question']) > 20 else h['question']
                                    
                                    new_practice = {
                                        "title": f"【図解】{short_title}",
                                        "category": "html_css", # Default category
                                        "content_type": "diagram", # New type for diagrams
                                        "description": h['answer'][:500] + "...", # Summary
                                        "html_code": selected_sec['html'], # Context HTML
                                        "css_code": selected_sec['css'],   # Context CSS
                                        "generated_svg": svg_content,
                                        "tags": ["図解", "Diagram", selected_sec['name']],
                                        "chat_history": [h] # Save this specific overlapping chat
                                    }
                                    try:
                                        s_id = st.session_state.data_manager.add(new_practice)
                                        st.success(f"✅ 保存完了 (ID: {s_id[:6]})")
                                    except Exception as e:
                                        st.error(f"保存エラー: {e}")
                            with col_del:
                                if st.button("🗑️ 削除", key=f"focus_del_svg_{idx}"):
                                    # 履歴からsvgを削除
                                    if "svg" in st.session_state.code_learning["chat_history"][idx]:
                                        del st.session_state.code_learning["chat_history"][idx]["svg"]
                                    # キャッシュ削除
                                    if f"focus_svg_{idx}" in st.session_state:
                                        del st.session_state[f"focus_svg_{idx}"]
                                    st.rerun()
                        
                        st.divider()



        else:
            st.error("セクションデータが見つかりませんでした。")
            
        # デバッグ用：生データ表示（開発中のみ）
        with st.expander("🐛 セクション分割データ（Raw Output）"):
            st.json(sections)
    else:
        st.warning("セクションをうまく分割できませんでした。")
    st.markdown("---")

# 9. メインビュー（プレビュー・エディタ）
if not st.session_state.get("show_analysis_mode", False) and not st.session_state.get("show_section_mode", False):
    # プレビュー
    has_image = bool(st.session_state.code_learning.get("image_bytes"))
    with st.expander("📷 参考画像", expanded=has_image):
        prev_cols = st.columns([2, 1])
        with prev_cols[0]:
            img_data = st.session_state.code_learning.get("image_bytes")
            img_ext = st.session_state.code_learning.get("image_ext", "")
            if img_data:
                try:
                    # 拡張子判定
                    is_svg = (img_ext == "svg")
                    
                    if is_svg:
                        # SVGはst.imageで表示されない場合があるためcomponents.htmlを使用
                        svg_code = img_data.decode("utf-8")
                        
                        # SVGタグ抽出（余計な文字を除去）
                        start = svg_code.find("<svg")
                        if start != -1:
                            svg_code = svg_code[start:]
                            end = svg_code.rfind("</svg>")
                            if end != -1:
                                svg_code = svg_code[:end+6]

                        # 完全なHTML構造でラップ
                        html_content = f"""
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <style>
                                body {{ margin: 0; padding: 20px; background-color: #ffffff; display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
                                svg {{ max-width: 100%; height: auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                            </style>
                        </head>
                        <body>
                            {svg_code}
                        </body>
                        </html>
                        """
                        st.components.v1.html(html_content, height=450, scrolling=True)
                    else:
                        st.image(img_data, use_container_width=True)
                except Exception as e:
                    st.error(f"画像表示エラー: {e}")
            else:
                st.info("画像なし")
        with prev_cols[1]:
            if HAS_PASTE_BUTTON:
                paste_result = paste_image_button("📋 Ctrl+V", key="paste_btn")
                if paste_result.image_data is not None:
                    st.session_state.code_learning["image_bytes"] = base64.b64decode(paste_result.image_data.split(",")[1])
                    st.rerun()

    # 現在のコード値取得
    html_val = st.session_state.get("loaded_html", "")
    css_val = st.session_state.get("loaded_css", "")

    # 分析・セクションボタン（通常モード時のみ）
    col_ana1, col_ana2 = st.columns(2)
    with col_ana1:
        if st.button("🔍 クラス対応を分析する（AI解説）", help="HTMLとCSSの関係性をAIが分析してコメントを付けます", use_container_width=True):
            st.session_state.show_analysis_mode = True
            st.rerun()
    with col_ana2:
        if st.button("🧩 セクションごとに表示（フォーカス）", help="ヘッダーやフッターなど、機能単位でコードを抽出して表示します", use_container_width=True):
            st.session_state.show_section_mode = True
            # キャッシュはコード変更時のみクリア（ハッシュ比較で自動判定）
            st.rerun()

    # エディタ部
    with st.expander("📄 HTML", expanded=True):
        if "html_editor" not in st.session_state: st.session_state["html_editor"] = html_val
        html_input = st.text_area("HTMLコード", height=300, key="html_editor")

    col_css, col_chat = st.columns([3, 2])
    with col_css:
        if "css_editor" not in st.session_state: st.session_state["css_editor"] = css_val
        css_input = st.text_area("CSSコード", height=700, key="css_editor")

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
                    cache_threshold = st.session_state.get("answer_cache_threshold", 0.85)
                    cached = st.session_state.code_answer_cache.find_similar(cache_query, threshold=cache_threshold)
                    
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
                            
                            # 関連図解検索（ベクトル検索）
                            related_visuals = []
                            try:
                                if "chroma_manager" in st.session_state:
                                    visual_results = st.session_state.chroma_manager.search_visuals(
                                        question, 
                                        min_score=st.session_state.get("related_visual_threshold", 0.70), 
                                        top_k=1
                                    )
                                    if visual_results:
                                        for res in visual_results:
                                            p_data = st.session_state.data_manager.get_by_id(res["id"])
                                            if p_data and p_data.get("generated_svg"):
                                                related_visuals.append({
                                                    "svg": p_data["generated_svg"],
                                                    "score": res["score"],
                                                    "title": p_data.get("title", "関連図解")
                                                })
                                                st.toast(f"💡 関連図解発見 ({res['score']:.0%})")
                            except Exception as e:
                                logger.error(f"Visual search failed: {e}")

                            # キャッシュに保存
                            st.session_state.code_answer_cache.add(cache_query, answer)
                            st.session_state.code_learning["chat_history"].append({
                                "question": question,
                                "answer": answer,
                                "related_visuals": related_visuals
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

        # チャット履歴（最新の1件のみ表示 - ユーザー要望）
        chat_history = st.session_state.code_learning.get("chat_history", [])
        
        if chat_history:
            st.markdown("##### 💬 最新の回答")
            
            h = chat_history[-1]
            idx = len(chat_history) - 1

            # 質問
            st.markdown(f"**Q:** {h['question']}")

            # 回答
            st.markdown(f"**A:** {h['answer']}")

            # 関連図解の表示
            if h.get("related_visuals"):
                for vis in h["related_visuals"]:
                    with st.expander(f"💡 関連図解: {vis.get('title', '図解')} - 一致度{vis.get('score', 0):.0%}", expanded=True):
                        import urllib.parse
                        svg_encoded = urllib.parse.quote(vis["svg"], safe='')
                        svg_html = f"""
                        <div style="background:white;padding:10px;position:relative;">
                            <button onclick="var w=window.open('','_blank','width=1200,height=800');w.document.write('<html><body style=\\'margin:0;display:flex;justify-content:center;align-items:center;height:100vh;\\'>' + decodeURIComponent('{svg_encoded}') + '</body></html>');w.document.close();" 
                            style="position:absolute;top:5px;right:5px;z-index:100;cursor:pointer;background:#1976d2;color:white;border:none;padding:5px 10px;border-radius:4px;">🔍 拡大</button>
                            {vis["svg"]}
                        </div>
                        """
                        st.components.v1.html(svg_html, height=300, scrolling=True)

            # 図解生成ボタン（チャット履歴に保存してキャッシュ）
            diagram_key = f"diagram_{idx}"
            
            # SVGデータの確認
            svg_data = h.get("svg")
            if svg_data:
                if f"svg_{idx}" not in st.session_state:
                    st.session_state[f"svg_{idx}"] = svg_data

            if st.button(f"📐 図解生成", key=diagram_key):
                if svg_data:
                    st.session_state[f"svg_{idx}"] = svg_data
                    st.toast("💾 キャッシュから取得")
                    st.rerun()
                else:
                    with st.spinner("図解生成中..."):
                        svg = generate_preview_svg(h['answer'][:500], h['question'][:30])
                        if svg:
                            st.session_state.code_learning["chat_history"][idx]["svg"] = svg
                            st.session_state[f"svg_{idx}"] = svg
                            st.rerun()
                        else:
                            st.error("図解生成失敗")
            
            # SVG表示
            svg_key = f"svg_{idx}"
            current_svg = st.session_state.get(svg_key)
            
            if current_svg:
                import urllib.parse
                svg_encoded = urllib.parse.quote(current_svg, safe='')
                
                # 拡大ボタン付きコンテナ
                svg_display_html = f"""
                    <div style="background: white; padding: 10px; border-radius: 8px; border: 1px solid #4caf50; position: relative;">
                        <button onclick="var w=window.open('','_blank','width=1200,height=800');w.document.write('<html><head><title>図解拡大</title></head><body style=\\'background:#fff;margin:0;display:flex;justify-content:center;align-items:center;height:100vh;\\'>' + decodeURIComponent('{svg_encoded}') + '</body></html>');w.document.close();"
                            style="position: absolute; top: 5px; right: 10px; background: #1976d2; color: white; padding: 5px 10px; border-radius: 4px; border: none; cursor: pointer; font-size: 12px; z-index: 100;">
                            🔍 拡大
                        </button>
                        {current_svg}
                    </div>
                """
                components.html(svg_display_html, height=350, scrolling=True)




