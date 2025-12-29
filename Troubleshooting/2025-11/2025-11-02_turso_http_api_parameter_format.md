# Turso HTTP API のパラメータ形式エラー (400 Bad Request)

**日付**: 2025-11-02
**Keywords**: Turso, HTTP API, 400 Bad Request, パラメータ形式, JSON parse error, type field, blob, libsql
**Error**: `400 Client Error: Bad Request` / `JSON parse error: unknown field 'type', expected 'blob'`
**影響範囲**: データベースへの全ての書き込み操作
**重要度**: 🔴 Critical

---

## 症状

Turso の HTTP API を使用してデータを保存しようとすると、400 Bad Request エラーが発生。

**エラーメッセージ**:
```
Database request error: 400 Client Error: Bad Request for url: https://youtubeserch-sensha5172-sub.aws-ap-northeast-1.turso.io/
Error detail: {'error': 'JSON parse error: unknown field `type`, expected `blob` at line 1 column 349'}
```

**期待動作**: 
- SQL クエリとパラメータが正しく送信される
- データベースにデータが保存される

**実際の動作**: 
- 400 Bad Request エラー
- パラメータ形式が不正と判定される
- データが一切保存されない

---

## 原因

### 根本原因

Turso HTTP API のパラメータ形式を誤解していた。型情報を含むオブジェクト形式で送信していたが、実際には **単純な値の配列** を期待していた。

**問題のコード**:
```python
def _execute(self, sql, params=None):
    # ❌ 誤った形式: 型情報を含むオブジェクト
    formatted_params = []
    if params:
        for param in params:
            if param is None:
                formatted_params.append({"type": "null"})
            elif isinstance(param, int):
                formatted_params.append({"type": "integer", "value": str(param)})
            elif isinstance(param, float):
                formatted_params.append({"type": "float", "value": param})
            else:
                formatted_params.append({"type": "text", "value": str(param)})
    
    payload = {
        "statements": [{
            "q": sql,
            "params": formatted_params  # ❌ [{"type": "integer", "value": "123"}, ...]
        }]
    }
```

**送信されたペイロード（誤り）**:
```json
{
  "statements": [{
    "q": "INSERT INTO table VALUES (?, ?, ?)",
    "params": [
      {"type": "integer", "value": "123"},
      {"type": "text", "value": "hello"},
      {"type": "null"}
    ]
  }]
}
```

**なぜエラーが発生するか**:
- Turso HTTP API は `type` フィールドを認識しない
- エラーメッセージ: `unknown field 'type', expected 'blob'`
- 期待される形式は単純な値の配列

---

## 対処

### 正しいパラメータ形式

**修正後のコード**:
```python
def _execute(self, sql, params=None):
    # ✅ 正しい形式: 単純な値の配列
    formatted_params = []
    if params:
        for param in params:
            if param is None:
                formatted_params.append(None)
            else:
                formatted_params.append(param)  # そのまま追加
    
    payload = {
        "statements": [{
            "q": sql,
            "params": formatted_params  # ✅ [123, "hello", None]
        }]
    }
    
    response = requests.post(
        f'{self.base_url}',
        headers=self.headers,
        json=payload,
        timeout=30
    )
```

**送信されるペイロード（正しい）**:
```json
{
  "statements": [{
    "q": "INSERT INTO table VALUES (?, ?, ?)",
    "params": [123, "hello", null]
  }]
}
```

**ポイント**:
1. パラメータは **単純な値の配列**
2. 型情報は **不要**（Turso が自動判定）
3. `None` は `null` として送信
4. 数値・文字列はそのまま送信

---

## 修正ファイル

- `database.py` (30-48行目)
  - `_execute` メソッドのパラメータ処理部分を修正

---

## 予防策

### 1. API ドキュメントを必ず確認

```python
# ❌ 推測で実装
params = [{"type": "int", "value": 123}]

# ✅ ドキュメントを確認してから実装
# Turso Docs: https://docs.turso.tech/sdk/http/reference
params = [123, "text", None]
```

### 2. エラーメッセージを注意深く読む

```
JSON parse error: unknown field `type`, expected `blob`
```
→ `type` フィールドは不要、値を直接送信すべき

### 3. 最小限のテストケースで確認

```python
# 最もシンプルなクエリでテスト
payload = {
    "statements": [{
        "q": "SELECT 1",
        "params": []
    }]
}
response = requests.post(url, json=payload)
print(response.json())
```

### 4. 他の言語の実装例を参照

公式ドキュメントに Python 以外の例がある場合、それを参考にする:
```javascript
// JavaScript の例
const payload = {
  statements: [{
    q: "SELECT * FROM users WHERE id = ?",
    params: [123]  // 単純な配列
  }]
};
```

---

## 関連問題

- `2025-11-02_async_event_loop_runtime_error.md` - 非同期/同期の問題
- `2025-11-02_turso_http_api_response_parsing.md` - レスポンスのパース問題

---

## 学んだこと

### 1. API の仕様は推測しない

| ❌ 悪い例 | ✅ 良い例 |
|-----------|-----------|
| 他の API と同じだろう | ドキュメントを確認 |
| 型情報が必要だろう | 最小限のテストで確認 |
| エラーを無視して進める | エラーメッセージを精読 |

### 2. Turso HTTP API の正しい形式

**リクエスト**:
```json
{
  "statements": [
    {
      "q": "INSERT INTO users (id, name, age) VALUES (?, ?, ?)",
      "params": [1, "Alice", 25]
    }
  ]
}
```

**レスポンス**:
```json
[
  {
    "results": {
      "columns": ["id", "name", "age"],
      "rows": [[1, "Alice", 25]]
    }
  }
]
```

### 3. パラメータの型変換

Turso は自動的に型を判定:
```python
# Python → Turso
None        → null
123         → integer
3.14        → float
"text"      → text
True/False  → integer (1/0)
```

### 4. デバッグのコツ

```python
# リクエスト内容をログ出力
print(f"Payload: {json.dumps(payload, indent=2)}")

# レスポンス内容をログ出力
print(f"Response: {response.text}")

# エラー詳細を確認
if response.status_code != 200:
    try:
        error_detail = response.json()
        print(f"Error detail: {error_detail}")
    except:
        print(f"Response text: {response.text}")
```

---

## 追加情報

### Turso HTTP API の完全な仕様

**エンドポイント**:
```
POST https://[database-name]-[org-name].turso.io/
```

**ヘッダー**:
```python
headers = {
    'Authorization': f'Bearer {auth_token}',
    'Content-Type': 'application/json'
}
```

**複数ステートメントの実行**:
```json
{
  "statements": [
    {
      "q": "INSERT INTO users VALUES (?, ?)",
      "params": [1, "Alice"]
    },
    {
      "q": "INSERT INTO users VALUES (?, ?)",
      "params": [2, "Bob"]
    }
  ]
}
```

### よくある間違い

| 間違い | 正しい形式 |
|--------|------------|
| `{"type": "int", "value": 123}` | `123` |
| `{"type": "text", "value": "hello"}` | `"hello"` |
| `{"type": "null"}` | `null` |
| `[{"value": 123}]` | `[123]` |

### エラーコード一覧

| コード | 意味 | 対処 |
|--------|------|------|
| 400 | パラメータ形式エラー | ペイロード形式を確認 |
| 401 | 認証エラー | トークンを確認 |
| 403 | 権限エラー | API キーの権限を確認 |
| 500 | サーバーエラー | Turso のステータスを確認 |
| 505 | 非対応プロトコル | HTTP/HTTPS を確認 |

---

**🔥 重要**: Turso HTTP API のパラメータは単純な値の配列！型情報は不要！
