"""
共通UIスタイルモジュール
各ページで使用するCSS定義を集約
"""


def get_heading_styles() -> str:
    """共通の見出しスタイル（h2, h3, h4）を返す"""
    return '''<style>
    /* h2: 左アクセントライン + 背景 */
    h2, 
    div[data-testid="stMarkdownContainer"] h2, 
    section.main h2 {
        font-size: 1.4rem !important;
        background-color: rgba(255, 255, 255, 0.1) !important;
        padding: 0.5rem 0.8rem !important;
        border-left: 6px solid #1f77b4 !important;
        border-radius: 4px !important;
        margin-top: 1.5rem !important;
        margin-bottom: 0.8rem !important;
        line-height: 1.5 !important;
        font-family: sans-serif !important;
    }

    /* h3: 下線スタイル */
    h3, 
    div[data-testid="stMarkdownContainer"] h3, 
    section.main h3 {
        font-size: 1.2rem !important;
        border-bottom: 2px solid #1f77b4 !important;
        padding-bottom: 0.3rem !important;
        padding-top: 0.5rem !important;
        margin-top: 1.2rem !important;
        margin-bottom: 0.5rem !important;
        line-height: 1.4 !important;
        font-family: sans-serif !important;
    }

    /* h4: シンプル */
    h4,
    div[data-testid="stMarkdownContainer"] h4 {
        font-size: 1.0rem !important;
        font-weight: bold !important;
        margin-top: 0.8rem !important;
        margin-bottom: 0.4rem !important;
        color: #444 !important;
    }
</style>'''


def get_sidebar_narrow_styles() -> str:
    """サイドバー幅150pxに縮小 + 上部余白調整"""
    return '''<style>
    [data-testid="stSidebar"] { min-width: 150px !important; max-width: 150px !important; }
    .block-container { padding-top: 3rem !important; }
</style>'''


def get_sidebar_hidden_styles() -> str:
    """サイドバー完全非表示"""
    return '''<style>
    [data-testid="stSidebar"] { display: none; }
    [data-testid="stSidebarNav"] { display: none; }
    section[data-testid="stSidebar"] { display: none; }
    header[data-testid="stHeader"] { display: none; }
    .block-container {
        padding-top: 1rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        max-width: 100%;
    }
</style>'''


def get_compact_title_styles() -> str:
    """コンパクトタイトル用クラス"""
    return '''<style>
    .compact-title {
        font-size: 1.2rem;
        font-weight: 700;
        margin: 0;
        padding: 0;
        color: #333;
        margin-bottom: 0.5rem;
    }
</style>'''


def get_list_page_styles() -> str:
    """一覧ページ専用スタイル"""
    return '''<style>
    /* Expander ヘッダースタイル */
    .streamlit-expanderHeader {
        background-color: #f0f2f6;
        border-radius: 4px;
        font-weight: bold;
        font-size: 1.0rem;
        color: #0e1117;
        border: 1px solid #e0e0e0;
    }
    
    /* タグ見出し */
    .tag-header {
        color: #1f77b4;
        border-bottom: 2px solid #1f77b4;
        padding-bottom: 3px;
        margin-top: 10px;
        margin-bottom: 8px;
        font-weight: bold;
        display: inline-block;
        font-size: 0.95rem;
    }

    /* カード高さ統一 */
    [data-testid="stHorizontalBlock"] {
        align-items: stretch !important;
    }
    [data-testid="stVerticalBlock"] > div[data-testid="stContainer"] {
        height: 100% !important;
        display: flex !important;
        flex-direction: column !important;
    }
    
    /* サムネイル画像の最大高さ */
    [data-testid="stImage"] img {
        max-height: 120px !important;
        object-fit: cover !important;
        border-radius: 4px !important;
    }

    /* Expander 枠なし */
    .stExpander {
        border: none !important;
        box-shadow: none !important;
    }
</style>'''


def inject_common_styles(include_headings: bool = True, 
                         sidebar_mode: str = "narrow",
                         include_compact_title: bool = False) -> str:
    """
    共通スタイルを一括で取得
    
    Args:
        include_headings: 見出しスタイルを含めるか
        sidebar_mode: "narrow"=180px幅, "hidden"=非表示, "default"=変更なし
        include_compact_title: コンパクトタイトルスタイルを含めるか
    
    Returns:
        結合されたCSSスタイル文字列
    """
    styles = []
    
    if include_headings:
        styles.append(get_heading_styles())
    
    if sidebar_mode == "narrow":
        styles.append(get_sidebar_narrow_styles())
    elif sidebar_mode == "hidden":
        styles.append(get_sidebar_hidden_styles())
    
    if include_compact_title:
        styles.append(get_compact_title_styles())
    
    return "\n".join(styles)
