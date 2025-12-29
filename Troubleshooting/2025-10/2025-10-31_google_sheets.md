# Google Sheets 対応で発生した問題群

**日付**: 2025-10-31
**影響範囲**: Google Sheets読み込み全般
**重要度**: 🔴 Critical

---

## 🐛 パターンID抽出エラー
### 症状
パターン名「ウェブ(web)アプリ開発_専門用語 (wab_senmonyougo)」選択時に、エラー `パターン 'web' が見つかりません` が発生

### 原因
パターン名に括弧 `()` が複数含まれる場合、最初の括弧を取得してしまう
```python
pattern_id = selected.split("(")[1].split(")")[0]
# → "ウェブ(web)..." から "web" を抽出（誤）
```

### 対処
最後の括弧からIDを抽出するよう修正
```python
pattern_id = selected.rsplit("(", 1)[1].rstrip(")")
# → "...(wab_senmonyougo)" から "wab_senmonyougo" を抽出（正）
```

**修正ファイル**: `notion_uploader/gui/upload_tab.py` (250行目, 341行目)

---

## 🌐 Google Sheets URL自動入力されない
### 症状
Google Sheets パターン選択時にファイルパス欄が空になる
ログ: `パターンのファイルが存在しません: https://docs.google...`

### 原因
`os.path.exists(URL)` でURLの存在チェック → 常に `False`
Excelファイルと同じロジックでチェックしていた

### 対処
`source_type` で分岐し、Google Sheets は URL をそのまま設定
```python
if source_type == 'google_sheets':
    # URLをそのまま設定（os.path.exists不要）
    if source_path:
        self.file_path_var.set(source_path)
elif source_type == 'excel':
    # ローカルファイルの存在チェック
    if source_path and os.path.exists(source_path):
        self.file_path_var.set(source_path)
```

**修正ファイル**: `notion_uploader/gui/upload_tab.py` (262-283行目)

---

## 🔐 Google Sheets API認証エラー
### 症状
Google Sheets アップロード時にエラー:
`Service account info was not in the expected format, missing fields client_email, token_uri.`

### 原因
`config/credentials.json` が **OAuth 2.0クライアント形式** (`{"installed": {...}}`)
コードは **サービスアカウント形式** を期待 (`{"type": "service_account", ...}`)

### 対処
OAuth 2.0認証フローに対応し、両形式をサポート
```python
# credentials.jsonの形式を判定
if 'installed' in cred_data or 'web' in cred_data:
    # OAuth 2.0 → ブラウザ認証
    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
    creds = flow.run_local_server(port=0)

    # トークンを保存（次回から自動認証）
    with open('config/token.pickle', 'wb') as token:
        pickle.dump(creds, token)
else:
    # サービスアカウント → 従来通り
    creds = ServiceAccountCredentials.from_service_account_file(...)
```

**修正ファイル**:
- `notion_uploader/core/file_reader.py` (157-201行目)
- `requirements.txt` (google-auth-oauthlib追加)
- `.gitignore` (token.pickle追加)

**初回実行**: ブラウザが開く → Google許可 → 次回から自動
**依存追加**: `pip install google-auth-oauthlib`

---

## 🔍 Google Sheets URLからID抽出
### 症状
ログに URL全体が渡される:
`スプレッドシートID: https://docs.google.com/spreadsheets/d/1ro2FD_...`

### 原因
`pattern['source']['path']` に URL が保存されているが、API には ID が必要

### 対処
URL から ID を抽出するロジック追加
```python
spreadsheet_url = pattern['source']['path']
if '/spreadsheets/d/' in spreadsheet_url:
    spreadsheet_id = spreadsheet_url.split('/spreadsheets/d/')[1].split('/')[0]
else:
    spreadsheet_id = spreadsheet_url  # 既にID形式の場合
```

**修正ファイル**: `notion_uploader/gui/upload_tab.py` (370-378行目)

---

## 💡 まとめ・教訓

### Google Sheets対応で必要なこと
1. **URL vs ファイルパス**: source_type で処理を分ける
2. **OAuth 2.0認証**: credentials.json の形式を判定して対応
3. **URL→ID変換**: `/spreadsheets/d/{ID}/` からIDを抽出
4. **トークン保存**: `token.pickle` で次回から自動認証

### パターン名の注意
- **括弧が複数ある場合**: 最後の括弧 `rsplit("(", 1)` を使う
- **ID抽出**: 常に最後の `(ID)` 形式を想定

### セキュリティ
- `credentials.json`, `token.pickle` を `.gitignore` に必ず追加
- トークンはローカルのみ保存、リポジトリにコミットしない
