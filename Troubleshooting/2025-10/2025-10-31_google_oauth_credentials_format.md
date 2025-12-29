# Google Sheets API認証エラー - credentials.json形式の違い

**日付**: 2025-10-31
**Keywords**: Google Sheets, OAuth 2.0, サービスアカウント, credentials.json, 認証, token.pickle
**Error**: `Service account info was not in the expected format, missing fields client_email, token_uri`
**影響範囲**: Google Sheetsアップロード機能
**重要度**: 🔴 Critical

---

## 症状

Google Sheets アップロード実行時に認証エラー発生:

```
Service account info was not in the expected format, missing fields client_email, token_uri.
```

**期待動作**: Google Sheets APIで認証成功
**実際の動作**: 認証失敗、アップロード不可

---

## 原因

`config/credentials.json` が **OAuth 2.0クライアント形式** だが、コードは **サービスアカウント形式** を期待:

### OAuth 2.0クライアント形式 (実際のファイル):
```json
{
  "installed": {
    "client_id": "xxxxx.apps.googleusercontent.com",
    "project_id": "project-name",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_secret": "xxxxx"
  }
}
```

### サービスアカウント形式 (コードが期待):
```json
{
  "type": "service_account",
  "project_id": "project-name",
  "private_key_id": "xxxxx",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...",
  "client_email": "service-account@project.iam.gserviceaccount.com",
  "token_uri": "https://oauth2.googleapis.com/token"
}
```

**根本原因**:
- コードが単一形式（サービスアカウント）のみ対応
- Google Cloud Consoleで作成した認証情報の種類を確認せず使用

---

## 対処

OAuth 2.0認証フローに対応し、**両形式をサポート**:

```python
# 修正後のコード (file_reader.py)
import json
import pickle
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

def read_google_sheets(spreadsheet_id, credentials_path, sheet_name=None):
    creds = None
    token_path = 'config/token.pickle'

    # トークンキャッシュ確認
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    # 認証が必要な場合
    if not creds or not creds.valid:
        # credentials.jsonの形式を判定
        with open(credentials_path, 'r') as f:
            cred_data = json.load(f)

        if 'installed' in cred_data or 'web' in cred_data:
            # OAuth 2.0 → ブラウザ認証
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
            )
            creds = flow.run_local_server(port=0)

            # トークンを保存（次回から自動認証）
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        else:
            # サービスアカウント → 従来通り
            creds = ServiceAccountCredentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
            )

    # Google Sheets API呼び出し
    service = build('sheets', 'v4', credentials=creds)
    # ...
```

**ポイント**:
1. **形式判定**: `'installed'` or `'web'` キーの有無
2. **OAuth 2.0フロー**: ブラウザで認証 → トークン保存
3. **トークンキャッシュ**: 次回から自動認証

---

## 修正ファイル

- `notion_uploader/core/file_reader.py` (157-201行目)
- `requirements.txt` (`google-auth-oauthlib` 追加)
- `.gitignore` (`config/token.pickle` 追加)

---

## 初回実行の流れ

```
1. Google Sheets読み込み実行
   ↓
2. credentials.json 読み込み → OAuth 2.0形式検出
   ↓
3. ブラウザが自動で開く
   ↓
4. Googleアカウントでログイン
   ↓
5. 権限許可（スプレッドシート読み取り）
   ↓
6. 認証成功 → token.pickle 保存
   ↓
7. 次回から自動認証（ブラウザ不要）
```

---

## 依存追加

```bash
pip install google-auth-oauthlib
```

**requirements.txt**:
```
google-auth-oauthlib>=1.0.0
```

---

## セキュリティ注意事項

**`.gitignore` 必須**:
```gitignore
config/credentials.json
config/token.pickle
```

**理由**:
- `credentials.json`: クライアントシークレット含む
- `token.pickle`: アクセストークン含む
- **リポジトリにコミット厳禁**

---

## 予防策

**Google Cloud Console設定確認**:
1. **OAuth 2.0クライアント作成時**:
   - アプリケーションタイプ: デスクトップアプリ
   - 承認済みのリダイレクトURI: `http://localhost`

2. **サービスアカウント作成時**:
   - キーのタイプ: JSON
   - ダウンロード後の命名: `service-account.json`

**命名規則で区別**:
```
config/
├── credentials_oauth.json      # OAuth 2.0クライアント
└── credentials_service.json    # サービスアカウント
```

---

## 関連問題

- Google Sheets URL自動入力: `2025-10-31_google_sheets_url_auto_population.md`
- Google Sheets URL→ID変換: `2025-10-31_google_sheets_url_to_id.md`

---

## 学んだこと

1. **Google認証の2つの方式**:
   - **OAuth 2.0**: ユーザー認証、ブラウザフロー、トークン有効期限あり
   - **サービスアカウント**: サーバー間認証、ブラウザ不要、キーファイルのみ

2. **トークンキャッシュの重要性**:
   - 毎回ブラウザ認証は UX 悪い
   - `token.pickle` で2回目以降は自動

3. **形式判定のベストプラクティス**:
   ```python
   # JSONの構造で判定
   if 'installed' in data or 'web' in data:
       # OAuth 2.0
   elif 'type' in data and data['type'] == 'service_account':
       # サービスアカウント
   ```

4. **依存関係の明示**:
   - OAuth 2.0には `google-auth-oauthlib` 必須
   - サービスアカウントには不要
