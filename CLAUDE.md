# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CSS/HTML & 汎用ベストプラクティス RAG システム - A retrieval-augmented generation system for searching and managing code snippets (HTML/CSS/JS) and general manuals/procedures.

## Tech Stack

- **UI**: Streamlit
- **Vector DB**: ChromaDB (in-memory, rebuilt from JSON on startup)
- **Embedding**: Gemini text-embedding-004
- **LLM**: Gemini 3.0 Pro (answers), Gemini 2.5 Flash (formatting/SVG生成)
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
│   ├── llm.py            # Gemini Pro (answer), Flash (SVG/HTML生成)
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
- ✅ 自然言語検索 → ChromaDB類似度検索
- ✅ AI回答生成（ストリーミング対応）
- ✅ カテゴリフィルタ

### 2. AI回答キャッシュ
- ✅ セッションキャッシュ（同一セッション内の完全一致）
- ✅ 永続キャッシュ（`data/answer_cache.json`）
- ✅ 類似クエリマッチング（85%以上で既存回答を返す）
- ✅ キャッシュ使用時に「💾 キャッシュ使用（類似度: XX%）」表示

### 3. 図解・HTML生成
- ✅ AI回答から図解（SVG）生成
- ✅ AI回答からHTML生成
- ✅ 生成した図解/HTMLを保存可能
- ✅ 保存済み図解の自動表示（類似度65%以上）
- ✅ 保存済み画像の自動表示（類似度65%以上）

### 4. 削除機能
- ✅ 図解削除（チャット結果セクションで🗑ボタン）
- ✅ 画像削除（チャット結果セクションで🗑ボタン）
- ✅ データ削除（一覧ページ・検索結果から）

### 5. UI改善
- ✅ 起動時に自動で検索ページへ遷移（app.py → st.switch_page）
- ✅ サイドバー幅を180pxに縮小
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

| 機能 | 閾値 | 説明 |
|------|------|------|
| AI回答キャッシュ | 85% | 類似クエリで既存回答を返す |
| 図解検索 | 65% | 関連する保存済み図解を表示 |
| 画像検索 | 65% | 関連する保存済み画像を表示 |

---

## 現在の開発フェーズ (Phase 2: 機能拡張)

### 🔴 進行中: A. セクション別図解生成
- AI回答を `##` 見出しで分割
- 各セクションに図解生成ボタン追加
- 既存の「全体図解」も維持

### ⏳ 次: C. コード学習ページ
- HTML/CSS/画像を登録して学習
- AI自動分割 + スライダー範囲選択
- 選択部分への質問・図解生成

### ⏳ 次: B. 記憶ページ
- 学習リスト管理（未学習/覚えた）
- 進捗表示
- `data/learning_progress.json` で進捗保存

**詳細仕様: `docs/rag-specification.md` セクション15参照**

---

## 今後やるべきこと (Phase 3以降)

### Phase 3: クラウド連携
- Google Drive同期の確認
- Streamlit Cloud デプロイ

### Phase 4: 拡張
- URL自動取得（コード学習）
- エクスポート/インポート機能
- 複数ユーザー対応

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
   - 対応: `google.genai` パッケージへの移行が必要

2. **ポート競合**
   - 複数回起動するとポートが使用中になる
   - 対応: `--server.port 8503` などで別ポート指定

---

## 🔴 コード学習ページ (7_📖_コード学習.py) 現在の問題点

### 概要
コード学習ページはリデザイン中。サイドバー非表示 + 上部ナビ方式に変更済み。

### ✅ 解決済み
- タイトルフリッカー（「コード学習」↔「Streamlit」の切り替わり）
  - 原因: session_state更新による無限rerun
  - 対処: 毎回のsession_state更新を削除

### ❌ 未解決: 保存機能が動作しない

#### 症状
- 💾保存ボタンを押しても反応なし
- デバッグ表示: `html_val長さ: 0 / css_val長さ: 0`
- st_aceエディタに入力した内容が取得できていない

#### 原因分析
```
1. st_aceの値取得問題
   - st_aceはStreamlit独自のウィジェットで、keyベースで値を管理
   - ace_reload_counter でkey動的生成 → 値が正しく取得できない可能性
   - st_aceはNoneを返すことがある（初回レンダリング時など）

2. session_stateとの同期問題
   - loaded_html / loaded_css はデータ読み込み時のみ設定
   - st_aceに入力後、その値がsession_stateに反映されない
   - ボタン押下時、st_aceの戻り値が空になる

3. Streamlitのrerun問題
   - st_aceの値変更がrerunをトリガーする場合がある
   - rerun後にst_aceの値がリセットされる可能性
```

#### 現在のコード構造
```python
# 1. 読み込み時 (load_practice_id処理)
st.session_state["loaded_html"] = html_part
st.session_state["loaded_css"] = css_part
st.session_state["ace_reload_counter"] += 1

# 2. エディタ表示時
html_val = st.session_state.get("loaded_html", "")
css_val = st.session_state.get("loaded_css", "")
ace_counter = st.session_state.get("ace_reload_counter", 0)

html_input = st_ace(value=html_val, key=f"html_ace_{ace_counter}")
css_input = st_ace(value=css_val, key=f"css_ace_{ace_counter}")

# 3. 保存時
# html_input と css_input が空になっている ← 問題点
```

#### 試すべき対策

1. **st_aceをst.text_areaに戻す（確実に動作確認）**
   ```python
   # まずtext_areaで動作確認
   html_input = st.text_area("HTML", value=html_val, height=300)
   ```

2. **st_aceのkey固定**
   ```python
   # カウンタを使わず固定keyにする
   html_input = st_ace(value=html_val, key="html_ace_fixed")
   ```

3. **値変更時にsession_stateを明示的に更新**
   ```python
   if html_input:
       st.session_state["current_html"] = html_input
   # 保存時はsession_stateから読む
   ```

4. **on_changeコールバック使用**
   ```python
   # st_aceがon_change対応しているか確認必要
   ```

### ❌ 未解決: HTML/CSS分離問題

#### 症状
- 保存済みデータを読み込むと、HTMLとCSSが同じ内容になる
- または片方が空になる

#### 原因
1. **過去の保存時のバグ**
   - 以前の実装で`code_html`と`code_css`に同じ値が保存された
   - データ自体が壊れている

2. **読み込みロジックの問題**
   ```python
   # 現在の処理
   need_split = (not css_part) or (css_part == html_part)
   if need_split and "<style" in html_part.lower():
       # <style>タグから分離を試みる
   ```
   - ユーザーのデータは `<style>` タグを使っていない（別ファイル）
   - → 分離ロジックが機能しない

#### 試すべき対策
1. **practices.jsonのデータを直接確認・修正**
   - `code_html`と`code_css`が正しく分離されているか
   - 壊れたデータは手動修正

2. **保存時に確実に分離**
   ```python
   # 保存時
   save_to_database(title, category, html_input, css_input, ...)
   # html_inputとcss_inputを別々に渡す（現在の実装）
   ```

### UI構成（現在）

```
+----------------------------------------------------------+
| 🔍検索 | 📋一覧 | ⚙️設定 | 💾保存済み |                    |
+----------------------------------------------------------+
| [📷 プレビュー画像（折りたたみ）]                          |
+----------------------------------------------------------+
| [📄 HTML（折りたたみ）] - st_ace (monokai theme)          |
+----------------------------------------------------------+
| 🎨 CSS (st_ace)              | 💬 質問                   |
| [コードエディタ]              | [質問入力]                 |
|                              | [🤖質問する] [🗑️クリア]    |
|                              | [チャット履歴]             |
|                              | [📐図解生成]               |
+----------------------------------------------------------+
| タイトル | カテゴリ | 💾保存 | 🗑️クリア                  |
+----------------------------------------------------------+
| [🐛 デバッグ（折りたたみ）]                                |
+----------------------------------------------------------+
```

### 依存パッケージ
- `streamlit-ace`: 色付きコードエディタ（問題の可能性あり）
- `streamlit-paste-button`: クリップボード画像貼り付け

### 次のアクション
1. st_aceを一旦st.text_areaに戻して保存機能テスト
2. 保存が動いたらst_aceの問題を調査
3. practices.jsonの既存データを確認・修正

---

## Specification

Full specification: `docs/rag-specification.md`
