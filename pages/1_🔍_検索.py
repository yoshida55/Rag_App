"""
検索ページ - メイン機能
自然言語検索 + AI回答 + インライン編集
"""
import streamlit as st
import re
import base64
from pathlib import Path
from config.settings import CATEGORIES, logger
from modules.database import ChromaManager
from modules.data_manager import DataManager
from modules.llm import generate_answer_stream, generate_preview_svg, generate_preview_html, generate_simple_response
from modules.answer_cache import AnswerCache
from modules.learning_manager import add_to_learning_list, is_in_learning_list
import uuid

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent


def extract_code_from_text(text: str) -> dict:
    """テキストからHTMLとCSSコードブロックを抽出"""
    html_codes = re.findall(r'```html\s*(.*?)```', text, re.DOTALL | re.IGNORECASE)
    css_codes = re.findall(r'```css\s*(.*?)```', text, re.DOTALL | re.IGNORECASE)
    js_codes = re.findall(r'```(?:javascript|js)\s*(.*?)```', text, re.DOTALL | re.IGNORECASE)

    return {
        "html": "\n".join(html_codes).strip(),
        "css": "\n".join(css_codes).strip(),
        "js": "\n".join(js_codes).strip()
    }


def strip_html_tags(text: str) -> str:
    """HTMLタグを除去（マークダウン表示用）"""
    if not text:
        return ""
    # HTMLタグを除去
    clean = re.sub(r'<[^>]+>', '', text)
    return clean.strip()


def split_answer_into_sections(answer_text: str) -> list[dict]:
    """
    AI回答を ## / ### 見出しで階層分割

    Returns:
        [{"title": "セクション名", "content": "内容", "level": 2or3, "parent": "親タイトル"}, ...]
    """
    if not answer_text:
        return []

    logger.debug(f"[セクション分割] 開始: {len(answer_text)}文字")

    sections = []
    lines = answer_text.split('\n')
    current_main_title = None  # ## のタイトル
    current_title = None
    current_level = 0
    current_content = []

    for line in lines:
        # ### サブセクション（レベル3）
        match_sub = re.match(r'^###\s+(.+?)$', line)
        # ## メインセクション（レベル2）
        match_main = re.match(r'^##\s+([^#].+?)$', line)

        if match_sub:
            # 前のセクションを保存
            if current_title is not None and current_content:
                sections.append({
                    "title": current_title,
                    "content": '\n'.join(current_content).strip(),
                    "level": current_level,
                    "parent": current_main_title
                })
            current_title = match_sub.group(1).strip()
            current_level = 3
            current_content = []

        elif match_main:
            # 前のセクションを保存
            if current_title is not None and current_content:
                sections.append({
                    "title": current_title,
                    "content": '\n'.join(current_content).strip(),
                    "level": current_level,
                    "parent": current_main_title if current_level == 3 else None
                })
            elif current_content:
                # 最初の ## より前の内容（イントロ）
                sections.append({
                    "title": "概要",
                    "content": '\n'.join(current_content).strip(),
                    "level": 2,
                    "parent": None
                })

            # 新しいメインセクション開始
            current_main_title = match_main.group(1).strip()
            current_title = current_main_title
            current_level = 2
            current_content = []

        else:
            current_content.append(line)

    # 最後のセクションを保存
    if current_title is not None and current_content:
        sections.append({
            "title": current_title,
            "content": '\n'.join(current_content).strip(),
            "level": current_level,
            "parent": current_main_title if current_level == 3 else None
        })
    elif current_content:
        sections.append({
            "title": "回答",
            "content": '\n'.join(current_content).strip(),
            "level": 2,
            "parent": None
        })

    # 空のセクションを除外
    sections = [s for s in sections if s["content"]]

    logger.debug(f"[セクション分割] 完了: {len(sections)}セクション")
    for i, s in enumerate(sections):
        indent = "  " if s.get("level") == 3 else ""
        logger.debug(f"  {indent}{i+1}. {s['title']}: {len(s['content'])}文字")

    return sections


def render_preview(html_code: str, css_code: str, js_code: str, key: str):
    """プレビューをレンダリング（目立たずシンプル）"""
    if not html_code and not css_code:
        return

    with st.expander("👁️ プレビュー", expanded=False):
        preview_html = f"""
        <html>
        <head>
            <style>
                body {{ margin: 0; padding: 10px; font-family: sans-serif; }}
                {css_code}
            </style>
        </head>
        <body>
            {html_code}
            <script>{js_code}</script>
        </body>
        </html>
        """
        st.components.v1.html(preview_html, height=200, scrolling=True)

# ページ設定
st.set_page_config(page_title="検索 - RAG", page_icon="🔍", layout="wide")

# ダークモード初期化
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# サイドバーを狭く + 共通スタイル適用 + ダークモード
from modules.ui_styles import inject_common_styles

st.markdown(inject_common_styles(
    include_headings=True,
    sidebar_mode="narrow",
    include_compact_title=False,
    dark_mode=st.session_state.dark_mode
), unsafe_allow_html=True)

logger.info("=== 検索ページ表示 ===")

# セッション状態初期化
if "chroma_manager" not in st.session_state:
    logger.info("[検索] ChromaManager初期化")
    st.session_state.chroma_manager = ChromaManager(persistent=False)
    # JSONからデータ読み込み
    count = st.session_state.chroma_manager.load_from_json()
    logger.info(f"[検索] データ読み込み完了: {count}件")

if "data_manager" not in st.session_state:
    st.session_state.data_manager = DataManager()

if "answer_cache" not in st.session_state:
    st.session_state.answer_cache = AnswerCache()

# 登録モード初期化
if "learning_registration_mode" not in st.session_state:
    st.session_state.learning_registration_mode = False

# 🔹 登録モード状態表示（ページ上部）
logger.debug(f"[検索] session_state.learning_registration_mode = {st.session_state.get('learning_registration_mode', 'NOT SET')}")

if st.session_state.learning_registration_mode:
    st.success("🔔 登録モードON - 検索結果のチェックボックスで一括選択可能")
    logger.info("[検索] ページ上部: 登録モードON表示")

# 検索入力 + カテゴリ（横並び）
col_search, col_cat = st.columns([3, 1])

with col_search:
    query = st.text_input(
        "検索",
        placeholder="例: 横並びのカードを均等に配置したい",
        label_visibility="collapsed",
        key="search_query"
    )

with col_cat:
    category_options = {"all": "すべて"}
    category_options.update(CATEGORIES)
    selected_category = st.selectbox(
        "カテゴリ",
        options=list(category_options.keys()),
        format_func=lambda x: category_options[x],
        label_visibility="collapsed"
    )

logger.debug(f"[検索] 選択カテゴリ: {selected_category}")

# 検索実行（Enter押下 or クエリ入力時）
if query:
    logger.info(f"[検索] クエリ: {query}")

    with st.spinner("🔄 検索中..."):
        # ChromaDB検索
        category_filter = None if selected_category == "all" else selected_category
        search_results = st.session_state.chroma_manager.search(
            query=query,
            category=category_filter,
            top_k=5
        )
        logger.info(f"[検索] 結果: {len(search_results)}件")

    if search_results:
        # 検索結果からpracticeデータを取得
        practices = []
        for result in search_results:
            practice = st.session_state.data_manager.get_by_id(result["id"])
            if practice:
                practice["_score"] = result["score"]
                practices.append(practice)

        if not practices:
             st.info("🔍 条件に一致する結果は見つかりませんでした。")
        else:
             # スコアでフィルタリング（設定値を使用）
             threshold = st.session_state.get("global_search_threshold", 0.64)
             valid_practices = [p for p in practices if p.get("_score", 0) >= threshold]
             
             if not valid_practices:
                 st.warning(f"⚠️ 関連性の高い結果が見つかりませんでした。（一致度 {threshold:.0%} 未満）")
             else:
                # 検索結果をカード表示（グリッド）
                st.markdown(f"### 🎯 検索結果候補")
                
                chunk_size = 3
                for i in range(0, len(valid_practices), chunk_size):
                    chunk = valid_practices[i:i + chunk_size]
                    cols = st.columns(3)
                    for j, p in enumerate(chunk):
                        with cols[j]:
                            with st.container(border=True):
                                # アイコンとタイトル
                                icon = "💻" if p.get("content_type") == "code" else "📄"
                                st.markdown(f"**{icon} {p['title']}**")
                                
                                # スコアとカテゴリ
                                cat_key = p.get("category")
                                cat_name = CATEGORIES.get(cat_key, "その他") if cat_key in CATEGORIES else "その他"
                                st.caption(f"一致度: {p.get('_score', 0):.0%} | {cat_name}")
                                
                                # サムネイル（画像優先、なければSVG）
                                img_path = PROJECT_ROOT / p["image_path"] if p.get("image_path") else None
                                has_img = img_path and img_path.exists()
                                has_svg = bool(p.get("generated_svg"))
                                
                                if has_img:
                                    st.image(str(img_path), use_container_width=True)
                                elif has_svg:
                                    try:
                                        # Base64エンコードせずに直接SVG文字列を渡す
                                        st.image(p["generated_svg"], use_container_width=True)
                                    except Exception as e:
                                        # エラー時はデバッグ表示
                                        st.caption(f"SVG表示エラー: {e}")
                                
                                # 簡易詳細（Markdownの見出しなどを除去してプレビュー）
                                desc_preview = p.get("description", "")
                                desc_preview = re.sub(r'#+\s+', '', desc_preview)
                                desc_preview = desc_preview[:100] + "..." if len(desc_preview) > 100 else desc_preview
                                st.caption(desc_preview)

                                # 詳細ボタン（ワイド表示用）
                                key_detail = f"btn_search_detail_{p['id']}"
                                is_opened = st.session_state.get(f"search_detail_opened_{p['id']}", False)
                                btn_label = "▼ 詳細を見る" if not is_opened else "▲ 閉じる"
                                
                                if st.button(btn_label, key=key_detail, use_container_width=True):
                                    # 他のを閉じる（オプション：維持したいならこの処理は外す）
                                    # for k in list(st.session_state.keys()):
                                    #     if k.startswith("search_detail_opened_") and k != f"search_detail_opened_{p['id']}":
                                    #         st.session_state[k] = False
                                    
                                    st.session_state[f"search_detail_opened_{p['id']}"] = not is_opened
                                    st.rerun()

                    # --- ワイド詳細表示（行の下に展開） ---
                    # このチャンク（行）の中に開いているアイテムがあれば表示
                    opened_item = None
                    for p_check in chunk:
                         if st.session_state.get(f"search_detail_opened_{p_check['id']}", False):
                             opened_item = p_check
                             break
                    
                    if opened_item:
                         with st.container(border=True):
                            st.markdown(f"#### 📖 {opened_item['title']}")
                            
                            # ビジュアル（画像・図解）があるか確認
                            has_image = bool(opened_item.get("image_path") and (PROJECT_ROOT / opened_item["image_path"]).exists())
                            has_svg = bool(opened_item.get("generated_svg"))
                            has_visual = has_image or has_svg
                            
                            if has_visual:
                                # ビジュアルがある場合はカラム分け（比率調整：ビジュアル4 : 説明6）
                                col_vis, col_desc = st.columns([4, 6])
                                with col_vis:
                                    # 画像
                                    if has_image:
                                        img_path = PROJECT_ROOT / opened_item["image_path"]
                                        st.image(str(img_path), use_container_width=True)
                                    
                                    # 図解（SVG）
                                    if has_svg:
                                        if has_image: st.markdown("---") # 両方ある場合の区切り
                                        st.caption("図解イメージ")
                                        generated_svg = opened_item.get("generated_svg")
                                        # フルスクリーン対応のSVG表示
                                        import urllib.parse
                                        svg_encoded = urllib.parse.quote(generated_svg, safe='')
                                        fullscreen_html = f"""
                                        <div style="border: 1px solid #ddd; border-radius: 4px; padding: 10px; background: #ffffff; position: relative;">
                                            <button onclick="var w=window.open('','_blank','width=1000,height=700');w.document.write('<html><head><title>図解</title></head><body style=\\'background:#fff;margin:20px;\\'>' + decodeURIComponent('{svg_encoded}') + '</body></html>');w.document.close();"
                                               style="position: absolute; top: 5px; right: 10px; background: #1976d2; color: white; 
                                                      padding: 5px 10px; border-radius: 4px; border: none; cursor: pointer; font-size: 12px; z-index: 100;">
                                               🔍 拡大表示
                                            </button>
                                            {generated_svg}
                                        </div>
                                        """
                                        import streamlit.components.v1 as components
                                        components.html(fullscreen_html, height=400, scrolling=True)

                                with col_desc:
                                    st.markdown("**内容:**")
                                    st.markdown(strip_html_tags(opened_item.get("description", "")))
                                    if opened_item.get("tags"):
                                        st.caption(f"タグ: {', '.join(opened_item['tags'])}")
                            else:
                                # ビジュアルがない場合はフル幅で表示
                                st.markdown("**内容:**")
                                st.markdown(strip_html_tags(opened_item.get("description", "")))
                                if opened_item.get("tags"):
                                    st.caption(f"タグ: {', '.join(opened_item['tags'])}")
                            
                            # 2. コード
                            if opened_item.get("code_html") or opened_item.get("code_css") or opened_item.get("code_js"):
                                st.markdown("---")
                                st.markdown("##### 💻 コード")
                                tab_html, tab_css, tab_js = st.tabs(["HTML", "CSS", "JS"])
                                with tab_html:
                                    if opened_item.get("code_html"):
                                        st.code(opened_item["code_html"], language="html")
                                with tab_css:
                                    if opened_item.get("code_css"):
                                        st.code(opened_item["code_css"], language="css")
                                with tab_js:
                                    if opened_item.get("code_js"):
                                        st.code(opened_item["code_js"], language="javascript")

                            # スマート分割機能 (asideタグが含まれる場合のみ表示) - 検索ページ版
                            if "<aside>" in opened_item.get("description", ""):
                                st.markdown("---")
                                if st.button("✂️ AI分割", key=f"search_split_list_{opened_item['id']}", help="<aside>タグで自動分割して、AIで整理します"):
                                    st.session_state[f"search_splitting_{opened_item['id']}"] = True
                                    st.rerun()

                            # 分割モード実行中
                            if st.session_state.get(f"search_splitting_{opened_item['id']}"):
                                st.info("✂️ AI自動分割プレビューモード")
                                
                                if f"search_split_results_{opened_item['id']}" not in st.session_state:
                                    with st.spinner("AIが内容を解析・分割しています..."):
                                        try:
                                            description = opened_item.get("description", "")
                                            chunks = re.split(r'(?=<aside>)', description)
                                            chunks = [c for c in chunks if c.strip()]
                                            
                                            results = []
                                            for i, chunk in enumerate(chunks):
                                                prompt = f"""
                                                あなたは技術ドキュメントの編集者です。
                                                以下のテキストはNotionからエクスポートされた技術メモの一部です（HTMLタグが含まれています）。
                                                
                                                タスク：
                                                1. 内容を理解し、適切な「タイトル」を付けてください。
                                                2. 本文から不要なHTMLタグ（特にasideなど）を取り除き、読みやすいMarkdown形式の「本文」に整形してください。
                                                3. コードブロックがある場合は保持してください。
                                                
                                                元のテキスト:
                                                {chunk}
                                                
                                                出力フォーマット:
                                                タイトル: [ここにタイトル]
                                                本文:
                                                [ここにMarkdown整形された本文]
                                                """
                                                response = generate_simple_response(prompt)
                                                
                                                title_match = re.search(r'タイトル:\s*(.*)', response)
                                                body_match = re.search(r'本文:\s*(.*)', response, re.DOTALL)
                                                
                                                title = title_match.group(1).strip() if title_match else f"{opened_item['title']} ({i+1})"
                                                body = body_match.group(1).strip() if body_match else chunk
                                                title = re.sub(r'^[*#\s]+', '', title)
                                                
                                                results.append({
                                                    "title": title,
                                                    "description": body,
                                                    "category": opened_item.get("category", "other"),
                                                    "content_type": opened_item.get("content_type", "manual"),
                                                    "code_css": opened_item.get("code_css", ""),
                                                    "code_html": opened_item.get("code_html", ""),
                                                    "code_js": opened_item.get("code_js", "")
                                                })
                                            
                                            st.session_state[f"search_split_results_{opened_item['id']}"] = results
                                        except Exception as e:
                                            st.error(f"解析中にエラーが発生しました: {e}")
                                
                                results = st.session_state.get(f"search_split_results_{opened_item['id']}", [])
                                
                                if results:
                                    st.write(f"計 {len(results)} 件に分割されました。内容を確認してください。")
                                    
                                    new_items = []
                                    for i, res in enumerate(results):
                                        with st.expander(f"No.{i+1}: {res['title']}", expanded=True):
                                            n_title = st.text_input(f"タイトル #{i+1}", res['title'], key=f"search_split_title_{opened_item['id']}_{i}")
                                            n_desc = st.text_area(f"本文 #{i+1}", res['description'], key=f"search_split_desc_{opened_item['id']}_{i}", height=150)
                                            new_items.append({**res, "title": n_title, "description": n_desc})
                                    
                                    st.warning("⚠️ 「実行」を押すと、元のデータは削除され、新規登録されます。")
                                    
                                    col_split_exe, col_split_can = st.columns(2)
                                    with col_split_exe:
                                        if st.button("実行して分割登録", key=f"search_do_split_{opened_item['id']}"):
                                            for item in new_items:
                                                new_data = item.copy()
                                                new_data["id"] = str(uuid.uuid4())
                                                st.session_state.data_manager.add(new_data)
                                            
                                            st.session_state.data_manager.delete(opened_item["id"])
                                            st.session_state.chroma_manager.delete(opened_item["id"])
                                            
                                            del st.session_state[f"search_splitting_{opened_item['id']}"]
                                            del st.session_state[f"search_split_results_{opened_item['id']}"]
                                            
                                            st.success("分割登録が完了しました！")
                                            st.rerun()
                                    
                                    with col_split_can:
                                        if st.button("キャンセル", key=f"search_cancel_split_{opened_item['id']}"):
                                            del st.session_state[f"search_splitting_{opened_item['id']}"]
                                            if f"search_split_results_{opened_item['id']}" in st.session_state:
                                                del st.session_state[f"search_split_results_{opened_item['id']}"]
                                            st.rerun()



        st.markdown("---")

        # AI回答表示（永続キャッシュ + 類似クエリマッチング対応）
        st.markdown("### 🤖 AIの回答")

        # 🔹 登録モード取得（早めに取得）
        registration_mode = st.session_state.get("learning_registration_mode", False)

        # セッションキャッシュキー（閾値が変われば別回答として扱う）
        threshold_val = st.session_state.get("global_search_threshold", 0.64)
        session_cache_key = f"answer_{hash(query + str(selected_category) + str(threshold_val))}"

        try:
            # 1. セッションキャッシュ確認（同一セッション内の完全一致）
            if session_cache_key in st.session_state:
                answer_text = st.session_state[session_cache_key]
                logger.debug("[検索] セッションキャッシュ使用")

            else:
                # 2. 永続キャッシュ確認
                cache_threshold = st.session_state.get("answer_cache_threshold", 0.85)
                cached = st.session_state.answer_cache.find_similar(
                    query=query,
                    category=selected_category if selected_category != "all" else None,
                    threshold=cache_threshold
                )

                if cached:
                    # キャッシュヒット
                    answer_text = cached["answer"]
                    st.caption(f"💾 キャッシュ使用（類似度: {cached['similarity']:.0%}、元の質問: {cached['original_query'][:50]}...）")
                    # セッションキャッシュにも保存
                    st.session_state[session_cache_key] = answer_text
                    logger.info(f"[検索] 永続キャッシュヒット（類似度: {cached['similarity']:.1%}）")

                else:
                    # 3. 新規生成
                    # AIにも閾値以上のデータのみを渡す（参考データとの整合性確保）
                    ai_threshold = st.session_state.get("global_search_threshold", 0.64)
                    ai_practices = [p for p in practices if p.get("_score", 0) >= ai_threshold]
                    
                    answer_stream = generate_answer_stream(query, ai_practices)
                    answer_text = st.write_stream(answer_stream)

                    # セッションキャッシュに保存
                    st.session_state[session_cache_key] = answer_text

                    # 永続キャッシュに保存
                    st.session_state.answer_cache.add(
                        query=query,
                        answer=answer_text,
                        category=selected_category if selected_category != "all" else None
                    )
                    logger.info("[検索] AI回答生成完了（永続キャッシュ保存）")

            # 🔹 AI回答の表示方法を登録モードで切り替え
            if registration_mode:
                # 登録モードON: セクションごとにチェックボックス付きで表示
                sections = split_answer_into_sections(answer_text or "")
                logger.info(f"[検索] 登録モード: セクション分割 {len(sections)}件")

                if len(sections) >= 1:
                    st.info("🔔 登録モード: セクション左のチェックボックスで選択できます")
                    selected_answer_sections = []

                    current_main_title = None
                    current_main_content = []

                    for i, section in enumerate(sections):
                        level = section.get("level", 2)
                        section_key = f"ans_sec_{i}_{hash(section['title'])}"

                        if level == 2:
                            # 前のメインセクションを保存
                            if current_main_title and current_main_content:
                                # チェック状態を確認
                                check_key = f"ans_check_{hash(current_main_title)}"
                                if st.session_state.get(check_key, False):
                                    selected_answer_sections.append({
                                        "title": current_main_title,
                                        "content": "\n\n".join(current_main_content)
                                    })

                            # 新しいメインセクション開始
                            current_main_title = section["title"]
                            current_main_content = [section["content"]]

                            # メインセクション表示（チェックボックス付き）
                            col_check, col_content = st.columns([0.05, 0.95])
                            with col_check:
                                st.checkbox("", key=f"ans_check_{hash(section['title'])}", label_visibility="collapsed")
                            with col_content:
                                st.markdown(f"## {section['title']}")
                                st.markdown(section["content"])

                                # 🔹 関連する図解・画像を検索（高関連度のみ）
                                section_query = f"{section['title']} {section['content'][:200]}"
                                logger.debug(f"[検索] セクション関連検索: {section['title'][:30]}")

                                # 図解検索（70%以上）
                                related_svgs = st.session_state.chroma_manager.search_visuals(
                                    query=section_query,
                                    min_score=0.70,
                                    top_k=1
                                )
                                if related_svgs:
                                    svg_practice = st.session_state.data_manager.get_by_id(related_svgs[0]["id"])
                                    if svg_practice and svg_practice.get("generated_svg"):
                                        with st.expander(f"📐 関連図解 ({related_svgs[0]['score']:.0%})", expanded=False):
                                            st.components.v1.html(
                                                f'<div style="background:#fff;padding:10px;">{svg_practice["generated_svg"]}</div>',
                                                height=300, scrolling=True
                                            )

                                # 画像検索（70%以上）
                                related_imgs = st.session_state.chroma_manager.search_images(
                                    query=section_query,
                                    min_score=0.70,
                                    top_k=1
                                )
                                if related_imgs:
                                    img_practice = st.session_state.data_manager.get_by_id(related_imgs[0]["id"])
                                    if img_practice and img_practice.get("image_path"):
                                        img_path = PROJECT_ROOT / img_practice["image_path"]
                                        if img_path.exists():
                                            with st.expander(f"📷 関連画像 ({related_imgs[0]['score']:.0%})", expanded=False):
                                                st.image(str(img_path), use_container_width=True)

                        else:
                            # サブセクション（チェックボックスなし、インデント）
                            current_main_content.append(f"### {section['title']}\n{section['content']}")
                            st.markdown(f"### {section['title']}")
                            st.markdown(section["content"])

                    # 最後のメインセクションをチェック
                    if current_main_title and current_main_content:
                        check_key = f"ans_check_{hash(current_main_title)}"
                        if st.session_state.get(check_key, False):
                            selected_answer_sections.append({
                                "title": current_main_title,
                                "content": "\n\n".join(current_main_content)
                            })

                    # 選択したセクションを学習リストに追加ボタン
                    if selected_answer_sections:
                        if st.button(f"🧠 選択した{len(selected_answer_sections)}セクションを学習リストに追加", type="primary", key="add_answer_sections"):
                            added_count = 0
                            for sec in selected_answer_sections:
                                success = add_to_learning_list(
                                    practice_id=f"ans_section_{hash(sec['title'] + sec['content'][:50])}",
                                    title=sec["title"],
                                    description=sec["content"][:500],
                                    category=selected_category if selected_category != "all" else "other"
                                )
                                if success:
                                    added_count += 1
                            st.success(f"✅ {added_count}セクションを学習リストに追加しました！")
                            st.rerun()
                else:
                    # セクションが1つ以下の場合は通常表示
                    st.markdown(answer_text)
            else:
                # 登録モードOFF: セクションごとに表示（チェックボックスなし）+ 関連図解・画像
                sections = split_answer_into_sections(answer_text or "")

                if len(sections) >= 2:
                    for i, section in enumerate(sections):
                        level = section.get("level", 2)
                        section_key = f"section_{i}_{hash(section['title'])}"

                        if level == 2:
                            # タイトルと図解生成ボタンを同じ行に
                            col_title, col_svg, col_html = st.columns([3.5, 0.75, 0.75])
                            with col_title:
                                st.markdown(f"## {section['title']}")
                            with col_svg:
                                if st.button("📐", key=f"off_svg_{section_key}", help="図解生成"):
                                    with st.spinner("生成中..."):
                                        svg = generate_preview_svg(section['content'], section['title'])
                                        if svg:
                                            st.session_state[f"inline_svg_{section_key}"] = svg
                                            st.session_state[f"inline_section_{section_key}"] = section
                                            st.rerun()
                            with col_html:
                                if st.button("🌐", key=f"off_html_{section_key}", help="HTML生成"):
                                    with st.spinner("生成中..."):
                                        html = generate_preview_html(section['content'], section['title'])
                                        if html:
                                            st.session_state[f"inline_html_{section_key}"] = html
                                            st.session_state[f"inline_section_{section_key}"] = section
                                            st.rerun()
                            st.markdown(section["content"])

                            # 🔹 関連する図解・画像を検索（高関連度のみ）
                            section_query = f"{section['title']} {section['content'][:200]}"
                            logger.debug(f"[検索] セクション関連検索(OFF): {section['title'][:30]}")

                            # 図解検索（70%以上）
                            related_svgs = st.session_state.chroma_manager.search_visuals(
                                query=section_query,
                                min_score=0.70,
                                top_k=1
                            )
                            if related_svgs:
                                svg_practice = st.session_state.data_manager.get_by_id(related_svgs[0]["id"])
                                if svg_practice and svg_practice.get("generated_svg"):
                                    with st.expander(f"📐 関連図解 ({related_svgs[0]['score']:.0%})", expanded=False):
                                        st.components.v1.html(
                                            f'<div style="background:#fff;padding:10px;">{svg_practice["generated_svg"]}</div>',
                                            height=300, scrolling=True
                                        )

                            # 画像検索（70%以上）
                            related_imgs = st.session_state.chroma_manager.search_images(
                                query=section_query,
                                min_score=0.70,
                                top_k=1
                            )
                            if related_imgs:
                                img_practice = st.session_state.data_manager.get_by_id(related_imgs[0]["id"])
                                if img_practice and img_practice.get("image_path"):
                                    img_path = PROJECT_ROOT / img_practice["image_path"]
                                    if img_path.exists():
                                        with st.expander(f"📷 関連画像 ({related_imgs[0]['score']:.0%})", expanded=False):
                                            st.image(str(img_path), use_container_width=True)
                        else:
                            # サブセクション
                            st.markdown(f"### {section['title']}")
                            st.markdown(section["content"])
                else:
                    # セクション分割できない場合は通常表示
                    st.markdown(answer_text)


            # インライン生成結果表示（登録モードON/OFF両方で表示）
            if len(sections) >= 2:
                for i, section in enumerate(sections):
                    section_key = f"section_{i}_{hash(section['title'])}"

                    if st.session_state.get(f"inline_svg_{section_key}"):
                        svg_content = st.session_state[f"inline_svg_{section_key}"]
                        st.markdown(f"**📐 {section['title']} の図解:**")
                        
                        # フルスクリーン対応のSVG表示（JavaScript popup）
                        import urllib.parse
                        svg_encoded = urllib.parse.quote(svg_content, safe='')
                        fullscreen_html = f"""
                        <div style="border: 2px solid #4caf50; border-radius: 8px; padding: 10px; background: #ffffff; position: relative;">
                            <button onclick="var w=window.open('','_blank','width=1000,height=700');w.document.write('<html><head><title>図解</title></head><body style=\\'background:#fff;margin:20px;\\'>' + decodeURIComponent('{svg_encoded}') + '</body></html>');w.document.close();"
                               style="position: absolute; top: 5px; right: 10px; background: #1976d2; color: white; 
                                      padding: 5px 10px; border-radius: 4px; border: none; cursor: pointer; font-size: 12px;">
                               🔍 拡大表示
                            </button>
                            {svg_content}
                        </div>
                        """
                        st.components.v1.html(fullscreen_html, height=600, scrolling=True)

                        col_save, col_close = st.columns([1, 1])
                        with col_save:
                            if st.button("💾 保存", key=f"save_inline_svg_{section_key}"):
                                new_practice = {
                                    "title": f"図解: {section['title'][:30]}",
                                    "category": selected_category if selected_category != "all" else "html_css",
                                    "content_type": "manual",
                                    "description": f"## {section['title']}\n\n{section['content'][:500]}",
                                    "tags": ["図解", "SVG", "セクション"],
                                    "generated_svg": svg_content,
                                    "code_html": None, "code_css": None, "code_js": None,
                                                                        "notes": f"元の検索: {query}", "image_path": None
                                }
                                practice_id = st.session_state.data_manager.add(new_practice)
                                new_practice["id"] = practice_id
                                st.session_state.chroma_manager.add_practice(new_practice)
                                del st.session_state[f"inline_svg_{section_key}"]
                                st.success("✅ 保存しました！")
                        with col_close:
                            if st.button("✖ 閉じる", key=f"close_inline_svg_{section_key}"):
                                del st.session_state[f"inline_svg_{section_key}"]
                                st.rerun()

                    if st.session_state.get(f"inline_html_{section_key}"):
                        html_content = st.session_state[f"inline_html_{section_key}"]
                        st.markdown(f"**🌐 {section['title']} のHTML:**")
                        st.components.v1.html(html_content, height=250, scrolling=True)

                        col_save, col_close = st.columns([1, 1])
                        with col_save:
                            if st.button("💾 保存", key=f"save_inline_html_{section_key}"):
                                new_practice = {
                                    "title": f"HTML: {section['title'][:30]}",
                                    "category": selected_category if selected_category != "all" else "html_css",
                                    "content_type": "code",
                                    "description": f"## {section['title']}\n\n{section['content'][:500]}",
                                    "tags": ["HTML", "プレビュー", "セクション"],
                                    "generated_html": html_content,
                                    "code_html": None, "code_css": None, "code_js": None,
                                                                        "notes": f"元の検索: {query}", "image_path": None
                                }
                                practice_id = st.session_state.data_manager.add(new_practice)
                                new_practice["id"] = practice_id
                                st.session_state.chroma_manager.add_practice(new_practice)
                                del st.session_state[f"inline_html_{section_key}"]
                                st.success("✅ 保存しました！")
                        with col_close:
                            if st.button("✖ 閉じる", key=f"close_inline_html_{section_key}"):
                                del st.session_state[f"inline_html_{section_key}"]
                                st.rerun()





            # 🔹 全体の図解生成ボタン（既存機能を維持）
            st.markdown("---")
            st.markdown("### 📐 全体の図解生成")
            col_ai1, col_ai2, col_ai3 = st.columns([1, 1, 2])
            with col_ai1:
                if st.button("📐 全体図解", key="gen_svg_answer", help="AI回答全体から図解を生成"):
                    with st.spinner("生成中..."):
                        svg = generate_preview_svg(answer_text or query, f"回答: {query[:30]}")
                        if svg:
                            st.session_state["answer_svg"] = svg
                            st.rerun()
            with col_ai2:
                if st.button("🌐 全体HTML", key="gen_html_answer", help="AI回答全体からHTMLを生成"):
                    with st.spinner("生成中..."):
                        html = generate_preview_html(answer_text or query, f"回答: {query[:30]}")
                        if html:
                            st.session_state["answer_html"] = html
                            st.rerun()

            # 生成済みプレビュー表示（直接表示）
            if st.session_state.get("answer_svg"):
                svg_content = st.session_state["answer_svg"]
                logger.info(f"[検索] ★★★ SVG表示開始 ★★★: {len(svg_content)}文字")
                logger.debug(f"[検索] SVG先頭100文字: {svg_content[:100]}")

                st.markdown("---")
                st.markdown("### 📐 生成した図解")
                # SVGをhtml componentで表示（白背景付き）
                svg_html = f"""
                <html>
                <body style="margin:0; padding:20px; background:#ffffff;">
                    <div style="border: 2px solid #1976d2; border-radius: 8px; padding: 15px; background: #ffffff;">
                        {svg_content}
                    </div>
                </body>
                </html>
                """
                st.components.v1.html(svg_html, height=600, scrolling=True)
                logger.info("[検索] ★★★ SVG表示完了 ★★★")

                # 保存ボタン
                if st.button("💾 この図解を保存", key="save_svg_answer"):
                    # AI回答テキストを取得（検索用に使う）
                    cached_answer = st.session_state.get(session_cache_key, "")

                    # 新しいpracticeとして登録（AI回答を含めて検索しやすく）
                    new_practice = {
                        "title": f"図解: {query[:30]}",
                        "category": "html_css",
                        "content_type": "manual",
                        "description": f"## {query}\n\n{cached_answer[:500] if cached_answer else 'AI回答から生成した図解です。'}",
                        "tags": ["図解", "SVG", "自動生成"] + query.split()[:3],  # クエリのキーワードもタグに
                        "generated_svg": st.session_state["answer_svg"],
                        "code_html": None,
                        "code_css": None,
                        "code_js": None,
                        "notes": f"元の検索: {query}",
                        "image_path": None
                    }
                    practice_id = st.session_state.data_manager.add(new_practice)
                    new_practice["id"] = practice_id
                    st.session_state.chroma_manager.add_practice(new_practice)
                    del st.session_state["answer_svg"]
                    st.success(f"✅ 保存しました！（{new_practice['title']}）")
                    logger.info(f"[検索] 図解保存: {practice_id}")

            if st.session_state.get("answer_html"):
                st.markdown("**🌐 HTMLプレビュー:**")
                st.components.v1.html(st.session_state["answer_html"], height=300, scrolling=True)

                # 保存ボタン
                if st.button("💾 このHTMLを保存", key="save_html_answer"):
                    # AI回答テキストを取得（検索用に使う）
                    cached_answer = st.session_state.get(session_cache_key, "")

                    new_practice = {
                        "title": f"HTML: {query[:30]}",
                        "category": "html_css",
                        "content_type": "code",
                        "description": f"## {query}\n\n{cached_answer[:500] if cached_answer else 'AI回答から生成したHTMLプレビューです。'}",
                        "tags": ["HTML", "プレビュー", "自動生成"] + query.split()[:3],
                        "generated_html": st.session_state["answer_html"],
                        "code_html": None,
                        "code_css": None,
                        "code_js": None,
                        "notes": f"元の検索: {query}",
                        "image_path": None
                    }
                    practice_id = st.session_state.data_manager.add(new_practice)
                    new_practice["id"] = practice_id
                    st.session_state.chroma_manager.add_practice(new_practice)
                    del st.session_state["answer_html"]
                    st.success(f"✅ 保存しました！（{new_practice['title']}）")
                    logger.info(f"[検索] HTML保存: {practice_id}")

        except Exception as e:
            logger.error(f"[検索] AI回答生成エラー: {e}")
            st.error(f"⚠️ AI回答の生成に失敗しました: {e}")

        st.markdown("---")

        # 参考データ表示
        # 登録モードチェック
        registration_mode = st.session_state.get("learning_registration_mode", False)
        logger.info(f"[検索] 登録モード状態: {registration_mode}")

        # 🔹 登録モード状態インジケーター（常に表示）
        if registration_mode:
            st.info("🔔 登録モードON: チェックボックスで複数選択可能")
            st.markdown(f"### 📚 参考データ（{len(practices)}件）- 🔔 登録モード")
            st.caption("学習リストに追加したい項目にチェックを入れてください")
            logger.info(f"[検索] チェックボックス表示開始: {len(practices)}件")

            # チェックボックス表示（コンテナで囲む）
            checkbox_container = st.container()
            with checkbox_container:
                selected_items = []
                for idx, practice in enumerate(practices):
                    logger.debug(f"[検索] チェックボックス生成 {idx+1}: {practice['title'][:20]}")
                    in_list = is_in_learning_list(practice["id"])

                    if in_list:
                        st.checkbox(
                            f"✅ {practice['title'][:40]} (登録済み)",
                            value=True,
                            disabled=True,
                            key=f"regcheck_{practice['id']}"  # キー変更
                        )
                    else:
                        checked = st.checkbox(
                            f"📌 {practice['title'][:40]} (スコア: {practice.get('_score', 0):.2f})",
                            key=f"regcheck_{practice['id']}"  # キー変更
                        )
                        if checked:
                            selected_items.append(practice)

                logger.info(f"[検索] チェックボックス表示完了: {len(practices)}件生成")

            # 一括追加ボタン
            if selected_items:
                if st.button(f"✅ 選択した{len(selected_items)}件を学習リストに追加", type="primary"):
                    added_count = 0
                    for p in selected_items:
                        success = add_to_learning_list(
                            practice_id=p["id"],
                            title=p.get("title", "無題"),
                            description=p.get("description", ""),
                            category=p.get("category", "other")
                        )
                        if success:
                            added_count += 1
                    st.success(f"✅ {added_count}件を学習リストに追加しました！")
                    st.rerun()

            st.markdown("---")

        else:
            # 登録モードOFF時
            st.caption("💡 一括追加は「記憶」ページで登録モードをONにしてください")
            # 件数表示（フィルタリング適用）
            cnt_th = st.session_state.get("global_search_threshold", 0.64)
            cnt = len([p for p in practices if p.get("_score", 0) >= cnt_th])
            st.markdown(f"### 📚 参考データ（{cnt}件）")

        # 表示用フィルタリング（全体閾値を適用）
        disp_th = st.session_state.get("global_search_threshold", 0.64)
        disp_practices = [p for p in practices if p.get("_score", 0) >= disp_th]
        
        for practice in disp_practices:
            # カード型デザインに変更（リストビューと統一感を持たせる）
            with st.container(border=True):
                # タイトルとスコア
                col_header, col_score = st.columns([0.8, 0.2])
                with col_header:
                    icon = "💻" if practice.get("content_type") == "code" else "📄"
                    st.markdown(f"**{icon} {practice['title']}**")
                with col_score:
                    st.caption(f"Score: {practice.get('_score', 0):.2f}")

                # 画像がある場合、カード内にサムネイル表示
                if practice.get("image_path"):
                    image_full_path = PROJECT_ROOT / practice["image_path"]
                    if image_full_path.exists():
                        st.image(str(image_full_path), use_container_width=True)

                # タグ
                if practice.get("tags"):
                    tags_str = " ".join([f"`{t}`" for t in practice["tags"]])
                    st.caption(f"🏷 {tags_str}")

                # コンテンツ（省略表示）
                desc = practice.get("description", "")
                if len(desc) > 100:
                    st.markdown(desc[:100] + "...")
                else:
                    st.markdown(desc)

                # 詳細表示（Expanderにするか、ボタンで展開するか）
                # ここではExpanderを使って詳細を表示（画像は上に出ているので重複させないか、あるいは詳細は詳細でフルセット見せるか）
                with st.expander("詳細を見る"):
                    # カテゴリ
                    cat_name = CATEGORIES.get(practice.get("category", "other"), "その他")
                    st.markdown(f"**カテゴリ:** {cat_name}")

                    # 登録モードOFFの場合のみボタン表示
                    if not registration_mode:
                        if is_in_learning_list(practice["id"]):
                            st.success("✅ 学習リストに登録済み")
                        else:
                            if st.button("🧠 学習リストに追加", key=f"learn_add_{practice['id']}"):
                                success = add_to_learning_list(
                                    practice_id=practice["id"],
                                    title=practice.get("title", "無題"),
                                    description=practice.get("description", ""),
                                    category=practice.get("category", "other")
                                )
                                if success:
                                    st.success("✅ 学習リストに追加しました！")
                                    st.rerun()
                    
                    st.markdown("---")

                    # content_typeで表示切り替え
                    if practice.get("content_type") == "code":
                        # コード表示
                        st.markdown("**説明:**")
                        st.markdown(practice.get("description", ""))

                        if practice.get("code_html"):
                            st.markdown("**HTML:**")
                            st.code(practice["code_html"], language="html")

                        if practice.get("code_css"):
                            st.markdown("**CSS:**")
                            st.code(practice["code_css"], language="css")

                        if practice.get("code_js"):
                            st.markdown("**JavaScript:**")
                            st.code(practice["code_js"], language="javascript")

                        # HTMLプレビュー
                        if practice.get("code_html") or practice.get("code_css"):
                            render_preview(
                                practice.get("code_html", ""),
                                practice.get("code_css", ""),
                                practice.get("code_js", ""),
                                f"code_{practice['id']}"
                            )
                    else:
                        # マニュアル表示
                        st.markdown(practice.get("description", ""))

                    # 生成済みプレビュー表示 or 生成ボタン
                    generated_svg = practice.get("generated_svg")
                    generated_html = practice.get("generated_html")

                    if generated_svg or generated_html:
                        if generated_svg:
                            st.markdown("**📐 保存済み図解:**")
                            svg_wrapper = f"""
                            <div style="background: #ffffff; padding: 15px; border: 1px solid #ddd; border-radius: 4px;">
                                {generated_svg}
                            </div>
                            """
                            st.components.v1.html(svg_wrapper, height=600, scrolling=True)
                        if generated_html:
                            st.markdown("**🌐 保存済みHTML:**")
                            st.components.v1.html(generated_html, height=300, scrolling=True)
                    else:
                        # 生成ボタン
                        col_gen1, col_gen2, col_gen3 = st.columns([1, 1, 2])
                        with col_gen1:
                            if st.button("📐 SVG生成", key=f"gen_svg_{practice['id']}", help="説明文から図解を生成"):
                                with st.spinner("生成中..."):
                                    svg = generate_preview_svg(
                                        practice.get("description", ""),
                                        practice.get("title", "")
                                    )
                                    if svg:
                                        st.session_state.data_manager.update(
                                            practice["id"],
                                            {"generated_svg": svg}
                                        )
                                        st.success("生成完了！")
                                        st.rerun()
                        with col_gen2:
                            if st.button("🌐 HTML生成", key=f"gen_html_{practice['id']}", help="説明文からHTMLを生成"):
                                with st.spinner("生成中..."):
                                    html = generate_preview_html(
                                        practice.get("description", ""),
                                        practice.get("title", "")
                                    )
                                    if html:
                                        st.session_state.data_manager.update(
                                            practice["id"],
                                            {"generated_html": html}
                                        )
                                        st.success("生成完了！")
                                        st.rerun()

                    # 補足
                    if practice.get("notes"):
                        st.markdown("---")
                        st.markdown(f"**補足:** {practice['notes']}")

                    # 編集・削除ボタン
                    col1, col2, col3 = st.columns([1, 1, 2])
                    with col1:
                        if st.button("✏️ 編集", key=f"edit_{practice['id']}"):
                            st.session_state[f"editing_{practice['id']}"] = True
                            st.rerun()
                    with col2:
                        if st.button("🗑️ 削除", key=f"delete_{practice['id']}"):
                            st.session_state[f"confirm_delete_{practice['id']}"] = True
                            st.rerun()

                    # 削除確認
                    if st.session_state.get(f"confirm_delete_{practice['id']}"):
                        st.warning(f"「{practice['title']}」を削除しますか？")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("🗑️ 削除する", key=f"confirm_yes_{practice['id']}"):
                                st.session_state.data_manager.delete(practice["id"])
                                st.session_state.chroma_manager.delete(practice["id"])
                                del st.session_state[f"confirm_delete_{practice['id']}"]
                                st.success("削除しました")
                                logger.info(f"[検索] 削除完了: {practice['id']}")
                                st.rerun()
                        with col_no:
                            if st.button("キャンセル", key=f"confirm_no_{practice['id']}"):
                                del st.session_state[f"confirm_delete_{practice['id']}"]
                                st.rerun()

    else:
        st.warning("🔍 該当するデータが見つかりませんでした。")
        logger.info("[検索] 結果なし")

# フッター情報
st.markdown("---")
st.markdown(f"📊 登録データ数: **{st.session_state.chroma_manager.get_count()}**件")

# デバッグ情報
with st.expander("🐛 デバッグ情報", expanded=False):
    st.write(f"登録モード: **{st.session_state.get('learning_registration_mode', False)}**")
    st.write(f"セッション状態キー: {list(st.session_state.keys())[:10]}...")
