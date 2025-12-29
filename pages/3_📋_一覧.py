"""
一覧ページ
登録データの一覧表示・管理
"""
import streamlit as st
from pathlib import Path
from config.settings import CATEGORIES, CONTENT_TYPES, logger
from modules.data_manager import DataManager
import base64

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent

# ページ設定
st.set_page_config(page_title="一覧 - RAG", page_icon="📋", layout="wide")

logger.info("=== 一覧ページ表示 ===")

# カスタムCSSの注入
st.markdown("""
<style>
    /* Expander（カテゴリ）のヘッダースタイル */
    .streamlit-expanderHeader {
        background-color: #f0f2f6;
        border-radius: 4px;
        font-weight: bold;
        font-size: 1.1rem;
        color: #0e1117;
        border: 1px solid #e0e0e0;
    }
    
    /* タグ見出しのスタイル */
    .tag-header {
        color: #1f77b4;
        border-bottom: 2px solid #1f77b4;
        padding-bottom: 5px;
        margin-top: 15px;
        margin-bottom: 10px;
        font-weight: bold;
        display: inline-block;
    }

    /* ボタンの微調整（Streamlitのデフォルトボタンを少し大きく） */
    .stButton button {
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# セッション状態初期化
if "data_manager" not in st.session_state:
    st.session_state.data_manager = DataManager()

if "chroma_manager" not in st.session_state:
    from modules.database import ChromaManager
    st.session_state.chroma_manager = ChromaManager(persistent=False)

# ヘッダー
st.title("📋 登録データ一覧")

# データ取得
all_practices = st.session_state.data_manager.get_all()
st.markdown(f"全 **{len(all_practices)}** 件")
st.markdown("---")

# フィルタ
col1, col2 = st.columns(2)

with col1:
    filter_category = st.selectbox(
        "カテゴリフィルタ",
        options=["all"] + list(CATEGORIES.keys()),
        format_func=lambda x: "すべて" if x == "all" else CATEGORIES[x]
    )

with col2:
    search_keyword = st.text_input(
        "キーワード検索",
        placeholder="タイトル・説明・タグで検索"
    )

# ビューモード切り替え
view_mode = st.radio("表示モード", ["リスト", "ボード"], horizontal=True, label_visibility="collapsed")
st.markdown("---")

# フィルタ適用
filtered_practices = all_practices

if filter_category != "all":
    filtered_practices = [p for p in filtered_practices if p.get("category") == filter_category]

if search_keyword:
    keyword_lower = search_keyword.lower()
    filtered_practices = [
        p for p in filtered_practices
        if keyword_lower in p.get("title", "").lower()
        or keyword_lower in p.get("description", "").lower()
        or any(keyword_lower in tag.lower() for tag in p.get("tags", []))
    ]

st.markdown(f"表示: **{len(filtered_practices)}** 件")

# ==========================================
# ボードビュー（カンバン方式）
# ==========================================
if view_mode == "ボード":
    # カテゴリごとにグループ化
    grouped_practices = {}
    target_categories = [filter_category] if filter_category != "all" else list(CATEGORIES.keys()) + ["other"]
    
    for p in filtered_practices:
        cat = p.get("category", "other")
        if cat not in grouped_practices:
            grouped_practices[cat] = []
        grouped_practices[cat].append(p)

    # カラム表示（3カラムずつ）
    cols_per_row = 3
    display_cats = [c for c in target_categories if c in grouped_practices or filter_category == "all"]
    
    # グリッドレイアウト
    for i in range(0, len(display_cats), cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            if i + j < len(display_cats):
                cat_key = display_cats[i + j]
                cat_name = CATEGORIES.get(cat_key, "その他")
                practices = grouped_practices.get(cat_key, [])
                
                with cols[j]:
                    st.markdown(f"### {cat_name}")
                    st.markdown(f"*{len(practices)} items*")
                    for p in practices:
                        # カード表示
                        with st.container(border=True):
                            icon = "💻" if p.get("content_type") == "code" else "📄"
                            st.markdown(f"**{icon} {p['title']}**")
                            # タグ
                            if p.get("tags"):
                                st.caption(" ".join([f"`{t}`" for t in p["tags"][:3]]))
                            
                            # 詳細ボタン
                            if st.button("詳細", key=f"board_detail_{p['id']}", use_container_width=True):
                                st.session_state[f"detail_view_{p['id']}"] = True
                            
                            # 詳細ダイアログ（擬似）
                            if st.session_state.get(f"detail_view_{p['id']}"):
                                with st.expander("詳細プレビュー", expanded=True):
                                    st.markdown(p.get("description", ""))
                                    if st.button("閉じる", key=f"close_detail_{p['id']}"):
                                        del st.session_state[f"detail_view_{p['id']}"]
                                        st.rerun()

# ==========================================
# リストビュー（階層型・推奨）
# ==========================================
else:
    if filtered_practices:
        # 1. カテゴリごとにグループ化
        grouped_by_cat = {}
        target_cats = [filter_category] if filter_category != "all" else list(CATEGORIES.keys())
        
        for p in filtered_practices:
            c = p.get("category", "other")
            if c not in grouped_by_cat:
                grouped_by_cat[c] = []
            grouped_by_cat[c].append(p)
            
        # カテゴリ順に表示
        for cat_key in target_cats:
            if cat_key not in grouped_by_cat:
                continue
                
            cat_name = CATEGORIES.get(cat_key, "その他")
            practices = grouped_by_cat[cat_key]
            
            # 第1階層: カテゴリ（Expander、初期は開く）
            with st.expander(f"📂 {cat_name} ({len(practices)})", expanded=True):
                
                # タグごとにさらにグループ化
                grouped_by_tag = {}
                no_tag_practices = []
                
                for p in practices:
                    tags = p.get("tags", [])
                    if tags:
                        # 最初のタグを代表タグ（中カテゴリ）とするが、表記揺れを防ぐためタイトルケースに統一
                        # 例: "flexbox" -> "Flexbox", "css" -> "Css" (または手動マッピングも検討余地あり)
                        # ここでは単純に capitalize を使用
                        raw_tag = tags[0]
                        # 英字のみの場合はTitle Case、それ以外はそのまま
                        main_tag = raw_tag.title() if raw_tag.isascii() else raw_tag
                        
                        if main_tag not in grouped_by_tag:
                            grouped_by_tag[main_tag] = []
                        grouped_by_tag[main_tag].append(p)
                    else:
                        no_tag_practices.append(p)
                
                # タググループ表示
                for tag, items in grouped_by_tag.items():
                    # 第2階層: タグ（見出し）- カスタムCSSクラス適用
                    st.markdown(f'<div class="tag-header">🏷️ {tag}</div>', unsafe_allow_html=True)
                    
                    # 第3階層: アイテム（3列グリッド表示 + 詳細フル幅表示）
                    # 3つずつチャンクに分割して処理
                    chunk_size = 3
                    for i in range(0, len(items), chunk_size):
                        chunk = items[i:i + chunk_size]
                        
                        # 1行分の列を作成
                        cols = st.columns(3)
                        
                        # この行で詳細が開かれているアイテムを特定
                        opened_item = None
                        
                        for j, p in enumerate(chunk):
                            with cols[j]:
                                with st.container(border=True):
                                    icon = "💻" if p.get("content_type") == "code" else "📄"
                                    st.markdown(f"**{icon} {p['title']}**")
                                    
                                    # 更新日
                                    st.caption(f"更新: {p.get('updated_at', '')[:10]}")
                                    
                                    # 画像がある場合（詳細が閉じてるときのみ）
                                    detail_key = f"detail_view_{p['id']}"
                                    is_opened = st.session_state.get(detail_key, False)
                                    
                                    if p.get("image_path") and not is_opened:
                                        img_path = PROJECT_ROOT / p["image_path"]
                                        if img_path.exists():
                                            st.image(str(img_path), use_container_width=True)

                                    # 図解サムネイル（詳細が閉じてるときのみ）
                                    if p.get("generated_svg") and not is_opened:
                                        try:
                                            b64 = base64.b64encode(p["generated_svg"].encode('utf-8')).decode("utf-8")
                                            st.image(f"data:image/svg+xml;base64,{b64}", use_container_width=True)
                                        except Exception:
                                            pass

                                    # 詳細ボタン
                                    key_suffix = f"list_{p['id']}"
                                    btn_label = "▼ 詳細を開く" if not is_opened else "▲ 閉じる"
                                    if st.button(btn_label, key=f"btn_{key_suffix}", use_container_width=True):
                                        st.session_state[detail_key] = not is_opened
                                        st.rerun() # リランして表示を更新

                                    if st.session_state.get(detail_key):
                                        opened_item = p
                        
                        # 行の下に詳細ビューを表示（フル幅）
                        if opened_item:
                            st.markdown(f"#### 📖 {opened_item['title']} の詳細")
                            with st.container(border=True):
                                p = opened_item
                                # 編集・削除ボタンと説明の間にビジュアルを表示
                                
                                # 画像（大きく表示）
                                if p.get("image_path"):
                                    img_path = PROJECT_ROOT / p["image_path"]
                                    if img_path.exists():
                                        st.image(str(img_path), use_container_width=True)
                                        # 画像削除ボタン
                                        if st.button("🗑️ 画像を削除", key=f"del_img_list_{p['id']}"):
                                            st.session_state[f"confirm_del_img_{p['id']}"] = True
                                            st.rerun()
                                        
                                        if st.session_state.get(f"confirm_del_img_{p['id']}"):
                                            st.warning("この画像を削除しますか？")
                                            col_y, col_n = st.columns(2)
                                            with col_y:
                                                if st.button("はい", key=f"y_del_img_{p['id']}"):
                                                    st.session_state.data_manager.update(p["id"], {"image_path": ""})
                                                    st.success("画像を削除しました")
                                                    del st.session_state[f"confirm_del_img_{p['id']}"]
                                                    st.rerun()
                                            with col_n:
                                                if st.button("キャンセル", key=f"n_del_img_{p['id']}"):
                                                    del st.session_state[f"confirm_del_img_{p['id']}"]
                                                    st.rerun()
                                
                                # 図解（SVG）
                                generated_svg = p.get("generated_svg")
                                if generated_svg:
                                    st.subheader("📐 図解")
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
                                    components.html(fullscreen_html, height=600, scrolling=True)
                                    
                                    # 図解削除ボタン
                                    if st.button("🗑️ 図解を削除", key=f"del_svg_list_{p['id']}"):
                                        st.session_state[f"confirm_del_svg_{p['id']}"] = True
                                        st.rerun()
                                        
                                    if st.session_state.get(f"confirm_del_svg_{p['id']}"):
                                        st.warning("この図解を削除しますか？")
                                        col_ys, col_ns = st.columns(2)
                                        with col_ys:
                                            if st.button("はい", key=f"y_del_svg_{p['id']}"):
                                                st.session_state.data_manager.update(p["id"], {"generated_svg": ""})
                                                st.success("図解を削除しました")
                                                del st.session_state[f"confirm_del_svg_{p['id']}"]
                                                st.rerun()
                                        with col_ns:
                                            if st.button("キャンセル", key=f"n_del_svg_{p['id']}"):
                                                del st.session_state[f"confirm_del_svg_{p['id']}"]
                                                st.rerun()
                                else:
                                    # 図解生成ボタン
                                    if st.button("📐 図解を生成する", key=f"gen_svg_list_{p['id']}"):
                                        from modules.llm import generate_preview_svg # ここでインポート
                                        with st.spinner("AIが図解を生成中..."):
                                            svg = generate_preview_svg(
                                                p.get("description", "") + "\n" + p.get("title", ""),
                                                p.get("title", "")
                                            )
                                            if svg:
                                                # 保存（自動保存）
                                                st.session_state.data_manager.update(p["id"], {"generated_svg": svg})
                                                updated_p = st.session_state.data_manager.get_by_id(p["id"])
                                                if updated_p:
                                                    st.session_state.chroma_manager.add_practice(updated_p)
                                                
                                                st.success("図解を生成しました！（自動保存されました）")
                                                st.rerun()
                                            else:
                                                st.error("生成に失敗しました")

                                # 説明（ビジュアルの下に移動）
                                if p.get("description"):
                                    st.markdown(p["description"])
                                
                                # コード
                                if p.get("content_type") == "code":
                                    if p.get("code_html"):
                                        st.subheader("HTML")
                                        st.code(p["code_html"], language="html")
                                    if p.get("code_css"):
                                        st.subheader("CSS")
                                        st.code(p["code_css"], language="css")
                                    if p.get("code_js"):
                                        st.subheader("JavaScript")
                                        st.code(p["code_js"], language="javascript")
                                    
                                    # プレビュー
                                    if p.get("code_html") or p.get("code_css"):
                                        html = p.get("code_html", "")
                                        css = p.get("code_css", "")
                                        js = p.get("code_js", "")
                                        
                                        with st.expander("👁️ プレビューを実行"):
                                            import streamlit.components.v1 as components
                                            preview_src = f"""
                                            <html>
                                            <head>
                                                <style>
                                                    body {{ margin: 0; padding: 10px; font-family: sans-serif; }}
                                                    {css}
                                                </style>
                                            </head>
                                            <body>
                                                {html}
                                                <script>{js}</script>
                                            </body>
                                            </html>
                                            """
                                            components.html(preview_src, height=200, scrolling=True)

                                # 補足
                                if p.get("notes"):
                                    st.info(f"💡 **Note:** {p['notes']}")
                                
                                # 編集・削除エリア
                                st.markdown("---")
                                col_btns = st.columns([1, 1, 4])
                                
                                # 編集モード切り替え
                                is_editing_key = f"editing_{p['id']}"
                                is_editing = st.session_state.get(is_editing_key, False)
                                
                                with col_btns[0]:
                                    if st.button("✏️ 編集", key=f"edit_list_{p['id']}"):
                                        st.session_state[is_editing_key] = not is_editing
                                        st.rerun()
                                
                                with col_btns[1]:
                                    if st.button("🗑️ 削除", key=f"del_list_{p['id']}"):
                                        st.session_state[f"confirm_del_{p['id']}"] = True
                                        st.rerun()
                                
                                # 削除確認
                                if st.session_state.get(f"confirm_del_{p['id']}"):
                                    st.warning(f"本当に「{p['title']}」を削除しますか？")
                                    col_yes, col_no = st.columns(2)
                                    with col_yes:
                                        if st.button("はい、削除します", key=f"yes_del_{p['id']}"):
                                            st.session_state.data_manager.delete(p["id"])
                                            st.session_state.chroma_manager.delete(p["id"])
                                            st.success("削除しました")
                                            st.rerun()
                                    with col_no:
                                        if st.button("キャンセル", key=f"no_del_{p['id']}"):
                                            del st.session_state[f"confirm_del_{p['id']}"]
                                            st.rerun()

                                # 編集フォーム
                                if is_editing:
                                    with st.form(key=f"form_edit_{p['id']}"):
                                        new_title = st.text_input("タイトル", p.get("title", ""))
                                        new_desc = st.text_area("説明", p.get("description", ""))
                                        
                                        # コード編集
                                        new_html = p.get("code_html", "")
                                        new_css = p.get("code_css", "")
                                        new_js = p.get("code_js", "")
                                        
                                        if p.get("content_type") == "code":
                                            if new_html or new_css or new_js: # 既存があれば表示
                                                st.subheader("コード編集")
                                                new_html = st.text_area("HTML", new_html)
                                                new_css = st.text_area("CSS", new_css)
                                                new_js = st.text_area("JavaScript", new_js)

                                        new_notes = st.text_area("補足", p.get("notes", ""))
                                        
                                        if st.form_submit_button("保存する"):
                                            update_data = {
                                                "title": new_title,
                                                "description": new_desc,
                                                "code_html": new_html,
                                                "code_css": new_css,
                                                "code_js": new_js,
                                                "notes": new_notes
                                            }
                                            st.session_state.data_manager.update(p["id"], update_data)
                                            # Chroma更新
                                            updated_p = st.session_state.data_manager.get_by_id(p["id"])
                                            if updated_p:
                                                st.session_state.chroma_manager.add_practice(updated_p)
                                            
                                            st.session_state[is_editing_key] = False
                                            st.success("保存しました！")
                                            st.rerun()

                    st.markdown("") # スペース

                # タグなしグループ
                if no_tag_practices:
                    st.markdown('<div class="tag-header">📂 その他</div>', unsafe_allow_html=True)
                    chunk_size = 3
                    for i in range(0, len(no_tag_practices), chunk_size):
                        chunk = no_tag_practices[i:i + chunk_size]
                        cols = st.columns(3)
                        opened_item_nt = None
                        
                        for j, p in enumerate(chunk):
                            with cols[j]:
                                with st.container(border=True):
                                    icon = "💻" if p.get("content_type") == "code" else "📄"
                                    st.markdown(f"**{icon} {p['title']}**")
                                    st.caption(f"更新: {p.get('updated_at', '')[:10]}")
                                    
                                    detail_key_nt = f"detail_view_{p['id']}"
                                    is_opened_nt = st.session_state.get(detail_key_nt, False)

                                    if p.get("image_path") and not is_opened_nt:
                                        img_path = PROJECT_ROOT / p["image_path"]
                                        if img_path.exists():
                                            st.image(str(img_path), use_container_width=True)

                                    # 図解サムネイル（詳細が閉じてるときのみ）
                                    if p.get("generated_svg") and not is_opened_nt:
                                        try:
                                            b64 = base64.b64encode(p["generated_svg"].encode('utf-8')).decode("utf-8")
                                            st.image(f"data:image/svg+xml;base64,{b64}", use_container_width=True)
                                        except Exception:
                                            pass

                                    btn_label = "▼ 詳細" if not is_opened_nt else "▲ 閉じる"
                                    if st.button(btn_label, key=f"btn_nt_{p['id']}", use_container_width=True):
                                        st.session_state[detail_key_nt] = not is_opened_nt
                                        st.rerun()
                                    
                                    if st.session_state.get(detail_key_nt):
                                        opened_item_nt = p

                        # フル幅詳細表示（その他カテゴリ）
                        if opened_item_nt:
                            st.markdown(f"#### 📖 {opened_item_nt['title']} の詳細")
                            with st.container(border=True):
                                # 編集・削除ボタンと説明の間にビジュアルを表示

                                # 画像（大きく表示）
                                if p.get("image_path"):
                                    img_path = PROJECT_ROOT / p["image_path"]
                                    if img_path.exists():
                                        st.image(str(img_path), use_container_width=True)
                                        # 画像削除ボタン
                                        if st.button("🗑️ 画像を削除", key=f"del_img_nt_{p['id']}"):
                                            st.session_state[f"confirm_del_img_nt_{p['id']}"] = True
                                            st.rerun()
                                        
                                        if st.session_state.get(f"confirm_del_img_nt_{p['id']}"):
                                            st.warning("この画像を削除しますか？")
                                            col_y, col_n = st.columns(2)
                                            with col_y:
                                                if st.button("はい", key=f"y_del_img_nt_{p['id']}"):
                                                    st.session_state.data_manager.update(p["id"], {"image_path": ""})
                                                    st.success("画像を削除しました")
                                                    del st.session_state[f"confirm_del_img_nt_{p['id']}"]
                                                    st.rerun()
                                            with col_n:
                                                if st.button("キャンセル", key=f"n_del_img_nt_{p['id']}"):
                                                    del st.session_state[f"confirm_del_img_nt_{p['id']}"]
                                                    st.rerun()

                                # 図解（SVG）
                                generated_svg = p.get("generated_svg")
                                if generated_svg:
                                    st.subheader("📐 図解")
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
                                    components.html(fullscreen_html, height=600, scrolling=True)
                                    
                                    # 図解削除ボタン
                                    if st.button("🗑️ 図解を削除", key=f"del_svg_nt_{p['id']}"):
                                        st.session_state[f"confirm_del_svg_nt_{p['id']}"] = True
                                        st.rerun()
                                        
                                    if st.session_state.get(f"confirm_del_svg_nt_{p['id']}"):
                                        st.warning("この図解を削除しますか？")
                                        col_ys, col_ns = st.columns(2)
                                        with col_ys:
                                            if st.button("はい", key=f"y_del_svg_nt_{p['id']}"):
                                                st.session_state.data_manager.update(p["id"], {"generated_svg": ""})
                                                st.success("図解を削除しました")
                                                del st.session_state[f"confirm_del_svg_nt_{p['id']}"]
                                                st.rerun()
                                        with col_ns:
                                            if st.button("キャンセル", key=f"n_del_svg_nt_{p['id']}"):
                                                del st.session_state[f"confirm_del_svg_nt_{p['id']}"]
                                                st.rerun()
                                else:
                                    # 図解生成ボタン
                                    if st.button("📐 図解を生成する", key=f"gen_svg_nt_{p['id']}"):
                                        from modules.llm import generate_preview_svg
                                        with st.spinner("AIが図解を生成中..."):
                                            svg = generate_preview_svg(
                                                p.get("description", "") + "\n" + p.get("title", ""),
                                                p.get("title", "")
                                            )
                                            if svg:
                                                st.session_state.data_manager.update(p["id"], {"generated_svg": svg})
                                                updated_p = st.session_state.data_manager.get_by_id(p["id"])
                                                if updated_p:
                                                    st.session_state.chroma_manager.add_practice(updated_p)
                                                
                                                st.success("図解を生成しました！（自動保存されました）")
                                                st.rerun()

                                # 説明（ビジュアルの下に移動）
                                if p.get("description"):
                                    st.markdown(p["description"])

                                # 編集・削除エリア
                                st.markdown("---")
                                col_btns = st.columns([1, 1, 4])
                                
                                # 編集モード切り替え
                                is_editing_key = f"editing_{p['id']}"
                                is_editing = st.session_state.get(is_editing_key, False)
                                
                                with col_btns[0]:
                                    if st.button("✏️ 編集", key=f"edit_list_{p['id']}"):
                                        st.session_state[is_editing_key] = not is_editing
                                        st.rerun()
                                
                                with col_btns[1]:
                                    if st.button("🗑️ 削除", key=f"del_list_{p['id']}"):
                                        st.session_state[f"confirm_del_{p['id']}"] = True
                                        st.rerun()
                                
                                # 削除確認
                                if st.session_state.get(f"confirm_del_{p['id']}"):
                                    st.warning(f"本当に「{p['title']}」を削除しますか？")
                                    col_yes, col_no = st.columns(2)
                                    with col_yes:
                                        if st.button("はい、削除します", key=f"yes_del_{p['id']}"):
                                            st.session_state.data_manager.delete(p["id"])
                                            st.session_state.chroma_manager.delete(p["id"])
                                            st.success("削除しました")
                                            st.rerun()
                                    with col_no:
                                        if st.button("キャンセル", key=f"no_del_{p['id']}"):
                                            del st.session_state[f"confirm_del_{p['id']}"]
                                            st.rerun()

                                # 編集フォーム
                                if is_editing:
                                    with st.form(key=f"form_edit_{p['id']}"):
                                        new_title = st.text_input("タイトル", p.get("title", ""))
                                        new_desc = st.text_area("説明", p.get("description", ""))
                                        
                                        # コード編集
                                        new_html = p.get("code_html", "")
                                        new_css = p.get("code_css", "")
                                        new_js = p.get("code_js", "")
                                        
                                        if p.get("content_type") == "code":
                                            if new_html or new_css or new_js: # 既存があれば表示
                                                st.subheader("コード編集")
                                                new_html = st.text_area("HTML", new_html)
                                                new_css = st.text_area("CSS", new_css)
                                                new_js = st.text_area("JavaScript", new_js)

                                        new_notes = st.text_area("補足", p.get("notes", ""))
                                        
                                        if st.form_submit_button("保存する"):
                                            update_data = {
                                                "title": new_title,
                                                "description": new_desc,
                                                "code_html": new_html,
                                                "code_css": new_css,
                                                "code_js": new_js,
                                                "notes": new_notes
                                            }
                                            st.session_state.data_manager.update(p["id"], update_data)
                                            # Chroma更新
                                            updated_p = st.session_state.data_manager.get_by_id(p["id"])
                                            if updated_p:
                                                st.session_state.chroma_manager.add_practice(updated_p)
                                            
                                            st.session_state[is_editing_key] = False
                                            st.success("保存しました！")
                                            st.rerun()


    else:
        st.info("📭 データがありません。「登録」ページから追加してください。")
logger.info(f"[一覧] 表示完了: {len(filtered_practices)}件")
