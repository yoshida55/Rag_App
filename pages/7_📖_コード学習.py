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
from modules.llm import generate_simple_response, generate_preview_svg, analyze_image, analyze_html_css_relations, analyze_html_css_relations
from modules.data_manager import DataManager
from modules.database import ChromaManager
from modules.answer_cache import AnswerCache

# ... (imports omitted) ...

# ============================================================
# 分析モード（クラス対応関係の表示）
# ============================================================
if st.session_state.get("show_analysis_mode", False):
    st.markdown("### 🔍 クラスとスタイルの対応分析")
    st.info("AIがコードを解析し、関係性をコメントで追記しました。")

    if st.button("🔙 エディタに戻る"):
        st.session_state.show_analysis_mode = False
        st.rerun()

    # 分析結果の取得（なければ実行）
    if "analyzed_html" not in st.session_state or "analyzed_css" not in st.session_state:
        with st.spinner("AIがコードを分析中...（約5~10秒）"):
            current_html = st.session_state.get("html_editor", "")
            current_css = st.session_state.get("css_editor", "")
            a_html, a_css = analyze_html_css_relations(current_html, current_css)
            st.session_state.analyzed_html = a_html
            st.session_state.analyzed_css = a_css

    # 左右に並べて表示
    a_col1, a_col2 = st.columns(2)
    with a_col1:
        st.markdown("**📄 HTML (解説付き)**")
        st.code(st.session_state.analyzed_html, language="html")
    with a_col2:
        st.markdown("**🎨 CSS (解説付き)**")
        st.code(st.session_state.analyzed_css, language="css")
    
    st.markdown("---")

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
# 分析ボタン
# ------------------------------------------------------------
if not st.session_state.get("show_analysis_mode", False):
    if st.button("🔍 クラス対応を分析する（AI解説）", help="HTMLとCSSの関係性をAIが分析してコメントを付けます"):
        # エディタの最新値で分析するために一旦リロードが必要
        # session_stateはon_change等でないと更新されないため、ここでの値取得には注意が必要だが
        # 基本的に直前の操作が反映されている前提
        
        # 既存の分析結果をクリア（新しいコードで再分析）
        if "analyzed_html" in st.session_state: del st.session_state["analyzed_html"]
        if "analyzed_css" in st.session_state: del st.session_state["analyzed_css"]
        
        st.session_state.show_analysis_mode = True
        st.rerun()

# ------------------------------------------------------------

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
