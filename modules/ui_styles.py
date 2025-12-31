"""
共通UIスタイルモジュール
各ページで使用するCSS定義を集約
"""


def get_dark_mode_styles() -> str:
    """ダークモード用CSS（CSS変数でテーマ切り替え）"""
    return '''<style>
    /* ダークモード変数 */
    [data-theme="dark"] {
        --bg-primary: #1a1a2e !important;
        --bg-secondary: #16213e !important;
        --bg-tertiary: #0f3460 !important;
        --text-primary: #eaeaea !important;
        --text-secondary: #b8b8b8 !important;
        --accent-color: #4fc3f7 !important;
        --border-color: #3a3a5c !important;
        --success-color: #4caf50 !important;
        --warning-color: #ff9800 !important;
        --error-color: #f44336 !important;
    }
    
    /* ダークモード適用 */
    [data-theme="dark"] .stApp,
    [data-theme="dark"] .main,
    [data-theme="dark"] section.main {
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
    }
    
    [data-theme="dark"] [data-testid="stSidebar"] {
        background-color: var(--bg-secondary) !important;
    }
    
    [data-theme="dark"] [data-testid="stMarkdownContainer"],
    [data-theme="dark"] .stMarkdown,
    [data-theme="dark"] p, 
    [data-theme="dark"] span,
    [data-theme="dark"] label {
        color: var(--text-primary) !important;
    }
    
    [data-theme="dark"] h1, 
    [data-theme="dark"] h2, 
    [data-theme="dark"] h3, 
    [data-theme="dark"] h4, 
    [data-theme="dark"] h5 {
        color: var(--text-primary) !important;
    }
    
    /* ダークモード: 見出しスタイル調整 */
    [data-theme="dark"] h2,
    [data-theme="dark"] div[data-testid="stMarkdownContainer"] h2 {
        background-color: var(--bg-tertiary) !important;
        border-left-color: var(--accent-color) !important;
    }
    
    [data-theme="dark"] h3,
    [data-theme="dark"] div[data-testid="stMarkdownContainer"] h3 {
        border-bottom-color: var(--accent-color) !important;
    }
    
    [data-theme="dark"] h4,
    [data-theme="dark"] div[data-testid="stMarkdownContainer"] h4 {
        color: var(--text-secondary) !important;
    }
    
    /* ダークモード: コンテナ・カード */
    [data-theme="dark"] [data-testid="stContainer"],
    [data-theme="dark"] .stContainer {
        background-color: var(--bg-secondary) !important;
        border-color: var(--border-color) !important;
    }
    
    [data-theme="dark"] [data-testid="stExpander"] {
        background-color: var(--bg-secondary) !important;
        border-color: var(--border-color) !important;
    }
    
    [data-theme="dark"] .streamlit-expanderHeader {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
    }
    
    /* ダークモード: フォーム要素 */
    [data-theme="dark"] .stTextInput > div > div > input,
    [data-theme="dark"] .stTextArea > div > div > textarea,
    [data-theme="dark"] .stSelectbox > div > div > div {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
        border-color: var(--border-color) !important;
    }
    
    [data-theme="dark"] .stButton > button {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border-color: var(--accent-color) !important;
    }
    
    [data-theme="dark"] .stButton > button:hover {
        background-color: var(--accent-color) !important;
        color: var(--bg-primary) !important;
    }
    
    /* ダークモード: メトリクス */
    [data-theme="dark"] [data-testid="stMetric"],
    [data-theme="dark"] [data-testid="stMetricLabel"],
    [data-theme="dark"] [data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
    }
    
    /* ダークモード: テーブル */
    [data-theme="dark"] .stTable,
    [data-theme="dark"] table {
        background-color: var(--bg-secondary) !important;
    }
    
    [data-theme="dark"] th {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
    }
    
    [data-theme="dark"] td {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
        border-color: var(--border-color) !important;
    }
    
    /* ダークモード: コードブロック */
    [data-theme="dark"] .stCodeBlock,
    [data-theme="dark"] pre,
    [data-theme="dark"] code {
        background-color: #0d1117 !important;
        color: #c9d1d9 !important;
    }
    
    /* ダークモード: アラート */
    [data-theme="dark"] .stAlert {
        background-color: var(--bg-tertiary) !important;
        border-color: var(--border-color) !important;
    }
    
    /* ダークモード: タブ */
    [data-theme="dark"] .stTabs [data-baseweb="tab-list"] {
        background-color: var(--bg-secondary) !important;
    }
    
    [data-theme="dark"] .stTabs [data-baseweb="tab"] {
        color: var(--text-secondary) !important;
    }
    
    [data-theme="dark"] .stTabs [aria-selected="true"] {
        color: var(--accent-color) !important;
        border-bottom-color: var(--accent-color) !important;
    }
</style>'''


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
                         include_compact_title: bool = False,
                         dark_mode: bool = False) -> str:
    """
    共通スタイルを一括で取得
    
    Args:
        include_headings: 見出しスタイルを含めるか
        sidebar_mode: "narrow"=180px幅, "hidden"=非表示, "default"=変更なし
        include_compact_title: コンパクトタイトルスタイルを含めるか
        dark_mode: ダークモードを有効にするか
    
    Returns:
        結合されたCSSスタイル文字列
    """
    styles = []
    
    # ダークモードCSS（常に読み込んでおく）
    styles.append(get_dark_mode_styles())
    
    if include_headings:
        styles.append(get_heading_styles())
    
    if sidebar_mode == "narrow":
        styles.append(get_sidebar_narrow_styles())
    elif sidebar_mode == "hidden":
        styles.append(get_sidebar_hidden_styles())
    
    if include_compact_title:
        styles.append(get_compact_title_styles())
    
    # ダークモード適用スクリプト
    if dark_mode:
        styles.append('''<script>
            document.documentElement.setAttribute('data-theme', 'dark');
            document.body.setAttribute('data-theme', 'dark');
            // Streamlitのメイン要素にも適用
            setTimeout(() => {
                const app = document.querySelector('.stApp');
                if (app) app.setAttribute('data-theme', 'dark');
            }, 100);
        </script>''')
    
    return "\n".join(styles)


def apply_dark_mode_script(enabled: bool) -> str:
    """ダークモード切り替え用のJavaScriptを返す"""
    theme = "dark" if enabled else "light"
    return f'''<script>
        document.documentElement.setAttribute('data-theme', '{theme}');
        document.body.setAttribute('data-theme', '{theme}');
        const app = document.querySelector('.stApp');
        if (app) app.setAttribute('data-theme', '{theme}');
    </script>'''

