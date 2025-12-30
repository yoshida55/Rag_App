# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CSS/HTML & 汎用ベストプラクティス RAG システム - A retrieval-augmented generation system for searching and managing code snippets (HTML/CSS/JS) and general manuals/procedures.

## Tech Stack

- **UI**: Streamlit
- **Vector DB**: ChromaDB (in-memory, rebuilt from JSON on startup)
- **Embedding**: Gemini text-embedding-004
- **LLM**: Gemini 3.0 Pro (answers), Gemini 2.5 Flash (formatting/SVG 生成)
- **Storage**: Google Drive (data persistence), local JSON cache
- **Deploy**: Streamlit Cloud

## Commands

```bash
# Setup
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Run locally
streamlit run app.py --server.port 8503

# Deploy
# Push to GitHub → Streamlit Cloud auto-deploys
```

## Architecture

```
app.py                    # Entry point (自動で検索ページへ遷移)
├── config/
│   └── settings.py       # Categories, constants, GEMINI_MODELS
├── modules/
│   ├── embedding.py      # Gemini Embedding (text-embedding-004)
│   ├── database.py       # ChromaDB operations (search, search_visuals, search_images)
│   ├── llm.py            # Gemini Pro (answer/SVG生成), Flash (整形)
│   ├── answer_cache.py   # 永続キャッシュ（類似度85%マッチング）
│   ├── data_manager.py   # JSON CRUD operations
│   ├── usage_tracker.py  # API usage logging
│   └── drive_utils.py    # Google Drive sync
├── pages/
│   ├── 1_🔍_検索.py      # Search page (main) - AI回答 + セクション別図解
│   ├── 2_📝_登録.py      # Registration page
│   ├── 3_📋_一覧.py      # List page with delete functions
│   ├── 4_📥_一括登録.py  # Bulk import page
│   ├── 5_⚙️_設定.py      # Settings/usage page
│   ├── 6_🧠_記憶.py      # Learning list (未学習/覚えた tabs)
│   └── 7_📖_コード学習.py # Code learning (slider range + question/diagram)
└── data/
    ├── practices.json    # Data store (synced with Drive)
    ├── answer_cache.json # AI回答キャッシュ（永続）
    ├── usage_log.json    # API usage log
    └── images/           # Uploaded images
```

---

## 実装済み機能 (2024-12)

### 1. 検索機能

- ✅ 自然言語検索 → ChromaDB 類似度検索
- ✅ AI 回答生成（ストリーミング対応）
- ✅ カテゴリフィルタ

### 2. AI 回答キャッシュ

- ✅ セッションキャッシュ（同一セッション内の完全一致）
- ✅ 永続キャッシュ（`data/answer_cache.json`）
- ✅ 類似クエリマッチング（85%以上で既存回答を返す）
- ✅ キャッシュ使用時に「💾 キャッシュ使用（類似度: XX%）」表示

### 3. 図解・HTML 生成

- ✅ AI 回答から図解（SVG）生成
- ✅ AI 回答から HTML 生成
- ✅ 生成した図解/HTML を保存可能
- ✅ 保存済み図解の自動表示（類似度 65%以上）
- ✅ 保存済み画像の自動表示（類似度 65%以上）

### 4. 削除機能

- ✅ 図解削除（チャット結果セクションで 🗑 ボタン）
- ✅ 画像削除（チャット結果セクションで 🗑 ボタン）
- ✅ データ削除（一覧ページ・検索結果から）

### 5. UI 改善

- ✅ 起動時に自動で検索ページへ遷移（app.py → st.switch_page）
- ✅ サイドバー幅を 180px に縮小
- ✅ 上部余白調整（padding-top: 3rem）

---

## Data Structure

```python
# practices.json entry
{
    "id": "uuid-v4",
    "title": "タイトル",
    "category": "html_css",  # html_css, javascript, python, gas, vba, other
    "content_type": "code",  # code or manual
    "description": "説明文（Markdown可）",
    "tags": ["tag1", "tag2"],
    "code_html": "...",      # null if manual
    "code_css": "...",
    "code_js": "...",
    "image_path": "data/images/xxx.png",
    "generated_svg": "<svg>...</svg>",   # AI生成した図解
    "generated_html": "<!DOCTYPE...>",   # AI生成したHTML
    "notes": "補足",
    "created_at": "ISO8601",
    "updated_at": "ISO8601"
}

# answer_cache.json entry
{
    "entries": [
        {
            "query": "検索クエリ",
            "embedding": [0.1, 0.2, ...],  # 768次元
            "answer": "AI回答テキスト",
            "category": "html_css",
            "created_at": "ISO8601"
        }
    ]
}
```

---

## ChromaDB メタデータ

```python
metadata = {
    "title": "タイトル",
    "category": "html_css",
    "content_type": "code",
    "tags": "tag1,tag2",
    "has_svg": True/False,    # generated_svgがあるか
    "has_html": True/False,   # generated_htmlがあるか
    "has_image": True/False   # image_pathがあるか
}
```

---

## 類似度閾値設定

| 機能              | 閾値 | 説明                       |
| ----------------- | ---- | -------------------------- |
| AI 回答キャッシュ | 85%  | 類似クエリで既存回答を返す |
| 図解検索          | 65%  | 関連する保存済み図解を表示 |
| 画像検索          | 65%  | 関連する保存済み画像を表示 |

---

## 現在の開発フェーズ (Phase 3: 運用・メンテナンス)

### ✅ 完了済み機能

- セクション別図解生成
- コード学習ページ（HTML/CSS 入力、AI 分析、質問機能）
- 記憶ページ（未学習/覚えた管理、進捗表示）
- Google Drive 同期

### 🔄 今後の改善候補

- `google.genai` パッケージへの移行
- 大きなファイルのリファクタリング（検索ページ、一覧ページ）
- UI コンポーネントの共通化
- ダークモード対応
- テスト追加

---

## Secrets Management

**CRITICAL**: Keep secrets in `secrets/` folder (gitignored)

```
secrets/
├── .env                  # GOOGLE_API_KEY, GOOGLE_DRIVE_FOLDER_ID
└── credentials.json      # Google OAuth2 credentials
```

For Streamlit Cloud, use `.streamlit/secrets.toml` (not committed).

---

## 既知の問題

1. **google.generativeai パッケージ非推奨警告**

   - 警告: `All support for the google.generativeai package has ended`
   - 対応: `google.genai` パッケージへの移行を検討中

2. **ポート競合**
   - 複数回起動するとポートが使用中になる
   - 対応: `--server.port 8503` などで別ポート指定

---

## Specification

Full specification: `docs/rag-specification.md`
