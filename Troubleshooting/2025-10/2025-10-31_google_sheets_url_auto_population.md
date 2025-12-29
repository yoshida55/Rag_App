# Google Sheets URL自動入力されない

**日付**: 2025-10-31
**Keywords**: Google Sheets, URL, os.path.exists, source_type, ファイルパス, 自動入力
**Error**: なし（機能不全）
**ログ**: `パターンのファイルが存在しません: https://docs.google...`
**影響範囲**: パターン選択時のファイルパス自動入力
**重要度**: 🟡 Important

---

## 症状

Google Sheets パターンを選択した際、ファイルパス欄が空になる。

**期待動作**: Google Sheets URL が自動入力される
**実際の動作**: ファイルパス欄が空のまま
**ログ出力**: `パターンのファイルが存在しません: https://docs.google.com/spreadsheets/d/...`

---

## 原因

`os.path.exists(URL)` でURLの存在チェックを実行 → **常に `False` を返す**

```python
# 問題のコード (upload_tab.py)
source_path = pattern['source']['path']  # → "https://docs.google.com/..."

if source_path and os.path.exists(source_path):
    self.file_path_var.set(source_path)
else:
    logger.warning(f"パターンのファイルが存在しません: {source_path}")
```

**根本原因**:
- `os.path.exists()`: ローカルファイルシステムの存在確認用
- URL（`https://...`）には使用不可
- ExcelファイルとGoogle SheetsのURLを同じロジックで処理していた

---

## 対処

`source_type` で分岐し、Google Sheets は URL をそのまま設定:

```python
# 修正後のコード
source_type = pattern.get('source', {}).get('type', '')
source_path = pattern.get('source', {}).get('path', '')

if source_type == 'google_sheets':
    # URLをそのまま設定（os.path.exists不要）
    if source_path:
        self.file_path_var.set(source_path)
        logger.info(f"Google Sheets URL設定: {source_path}")
elif source_type == 'excel':
    # ローカルファイルの存在チェック
    if source_path and os.path.exists(source_path):
        self.file_path_var.set(source_path)
        logger.info(f"Excelファイル設定: {source_path}")
    else:
        logger.warning(f"Excelファイルが存在しません: {source_path}")
```

**ポイント**:
- `source_type` で処理を明確に分岐
- Google Sheets: URL検証不要（API呼び出し時に検証）
- Excel: ローカルファイル存在確認必須

---

## 修正ファイル

- `notion_uploader/gui/upload_tab.py` (262-283行目)

---

## 予防策

**設計原則**:
1. **異なる入力タイプは異なるロジック**
   - URL vs ファイルパス → 検証方法が異なる

2. **早期分岐**:
   ```python
   if is_url:
       handle_url()
   elif is_file:
       handle_file()
   ```

3. **型の明示**:
   ```python
   # config.json に明記
   "source": {
       "type": "google_sheets",  # or "excel"
       "path": "..."
   }
   ```

---

## 関連問題

- Google Sheets URL→ID変換: `2025-10-31_google_sheets_url_to_id.md`
- Google OAuth認証: `2025-10-31_google_oauth_credentials.md`

---

## 学んだこと

1. **`os.path.exists()` の適用範囲**:
   - ✅ ローカルファイルパス: `/path/to/file.xlsx`
   - ❌ URL: `https://...`
   - ❌ UNCパス（注意が必要）: `\\server\share\file`

2. **URL検証の方法**:
   ```python
   # 方法1: 簡易チェック
   if path.startswith('http://') or path.startswith('https://'):
       # URL

   # 方法2: urlparse
   from urllib.parse import urlparse
   result = urlparse(path)
   if result.scheme in ['http', 'https']:
       # URL
   ```

3. **設定ファイルに型情報を持たせる重要性**:
   - パスだけでは判断困難なケースあり
   - 明示的な `type` フィールドで処理を分岐
