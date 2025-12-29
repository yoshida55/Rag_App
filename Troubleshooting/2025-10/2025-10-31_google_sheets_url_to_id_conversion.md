# Google Sheets URL→ID抽出

**日付**: 2025-10-31
**Keywords**: Google Sheets, URL, スプレッドシートID, 文字列分割, 正規表現
**Error**: なし（機能不全）
**ログ**: `スプレッドシートID: https://docs.google.com/spreadsheets/d/1ro2FD_...`
**影響範囲**: Google Sheetsアップロード機能
**重要度**: 🟡 Important

---

## 症状

ログにURL全体が出力され、Google Sheets API呼び出しが失敗する可能性:

```
スプレッドシートID: https://docs.google.com/spreadsheets/d/1ro2FD_xxxxx/edit#gid=0
```

**期待動作**: スプレッドシートID `1ro2FD_xxxxx` のみ抽出
**実際の動作**: URL全体をIDとして使用

---

## 原因

`pattern['source']['path']` に**URL全体**が保存されているが、Google Sheets API は **ID のみ** を要求:

```python
# 問題のコード
spreadsheet_id = pattern['source']['path']
# → "https://docs.google.com/spreadsheets/d/1ro2FD_xxxxx/edit#gid=0"

# API呼び出し
service.spreadsheets().values().get(
    spreadsheetId=spreadsheet_id,  # ← URL全体を渡している
    range=sheet_name
).execute()
```

**Google Sheets URLの構造**:
```
https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid={SHEET_ID}
                                        ^^^^^^^^^^^^^^^^
                                        この部分だけ必要
```

---

## 対処

URLからIDを抽出するロジック追加:

```python
# 修正後のコード
spreadsheet_url = pattern['source']['path']

if '/spreadsheets/d/' in spreadsheet_url:
    # URLからID抽出
    spreadsheet_id = spreadsheet_url.split('/spreadsheets/d/')[1].split('/')[0]
else:
    # 既にID形式の場合はそのまま使用
    spreadsheet_id = spreadsheet_url

logger.info(f"スプレッドシートID: {spreadsheet_id}")
```

**動作例**:
```python
url = "https://docs.google.com/spreadsheets/d/1ro2FD_xxxxx/edit#gid=0"

# ステップ1: '/spreadsheets/d/' で分割
parts = url.split('/spreadsheets/d/')
# → ['https://docs.google.com', '1ro2FD_xxxxx/edit#gid=0']

# ステップ2: [1]を取得して '/' で分割
id_part = parts[1].split('/')
# → ['1ro2FD_xxxxx', 'edit#gid=0']

# ステップ3: [0]がID
spreadsheet_id = id_part[0]
# → '1ro2FD_xxxxx'
```

---

## 修正ファイル

- `notion_uploader/gui/upload_tab.py` (370-378行目)

---

## 予防策

**設計改善案**:

### Option 1: config.json に ID を直接記載
```json
{
  "source": {
    "type": "google_sheets",
    "spreadsheet_id": "1ro2FD_xxxxx",
    "sheet_name": "Sheet1"
  }
}
```

### Option 2: URLとID両方をサポート
```python
def extract_spreadsheet_id(input_str):
    """URLまたはIDを受け取り、IDを返す"""
    if input_str.startswith('http'):
        # URL
        return input_str.split('/spreadsheets/d/')[1].split('/')[0]
    else:
        # 既にID
        return input_str
```

### Option 3: 正規表現で厳密に抽出
```python
import re

def extract_spreadsheet_id(url):
    """正規表現でIDを抽出"""
    pattern = r'/spreadsheets/d/([a-zA-Z0-9-_]+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return url  # URLでない場合はそのまま
```

---

## テストケース

```python
test_cases = [
    # URL形式
    ("https://docs.google.com/spreadsheets/d/1ro2FD_xxxxx/edit#gid=0", "1ro2FD_xxxxx"),
    ("https://docs.google.com/spreadsheets/d/1ro2FD_xxxxx/", "1ro2FD_xxxxx"),

    # ID形式
    ("1ro2FD_xxxxx", "1ro2FD_xxxxx"),

    # エッジケース
    ("https://docs.google.com/spreadsheets/d/1ro2FD_xxxxx", "1ro2FD_xxxxx"),
]

for input_url, expected_id in test_cases:
    result = extract_spreadsheet_id(input_url)
    assert result == expected_id, f"Failed: {input_url}"
```

---

## 関連問題

- Google Sheets URL自動入力: `2025-10-31_google_sheets_url_auto_population.md`
- Google OAuth認証: `2025-10-31_google_oauth_credentials.md`

---

## 学んだこと

1. **Google Sheets IDの特徴**:
   - 文字数: 44文字程度
   - 使用文字: 英数字、ハイフン、アンダースコア
   - 例: `1ro2FD_K-9xLm3QwErTyU1pAsD8fGhJ2kLmNoP5qRsTuV`

2. **URL解析の3つのアプローチ**:
   ```python
   # 方法1: 文字列分割（シンプル）
   id = url.split('/spreadsheets/d/')[1].split('/')[0]

   # 方法2: 正規表現（厳密）
   id = re.search(r'/spreadsheets/d/([^/]+)', url).group(1)

   # 方法3: urllib.parse（複雑なURLに）
   from urllib.parse import urlparse
   path = urlparse(url).path
   id = path.split('/')[3]
   ```

3. **柔軟な入力対応**:
   - URLとID両方を受け付ける設計
   - ユーザーが間違えても動作する
   - エラーメッセージで正しい形式を案内
