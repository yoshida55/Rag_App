# 非同期ライブラリを同期環境で使用した際のRuntimeError

**日付**: 2025-11-02
**Keywords**: RuntimeError, event loop, asyncio, libsql_client, Turso, Streamlit, 非同期, 同期, HTTP API, データベース接続
**Error**: `RuntimeError: no running event loop`
**影響範囲**: データベース保存機能全体（チャンネル・動画の保存が完全に失敗）
**重要度**: 🔴 Critical

---

## 症状

Streamlit アプリで YouTube API から取得したデータをデータベースに保存しようとすると、以下のエラーが発生してデータが一切保存されない。

**エラーメッセージ**:
```
RuntimeError: no running event loop
```

**期待動作**: 
- YouTube API から取得した動画・チャンネルデータが Turso データベースに保存される
- 保存後、DB検索で結果が取得できる

**実際の動作**: 
- `RuntimeError: no running event loop` が発生
- データベースへの保存が完全に失敗
- DB検索で結果が0件

---

## 原因

### 根本原因

`libsql_client` の **非同期クライアント** (`create_client`) を **同期環境** (Streamlit) で使用していたため。

**問題のコード**:
```python
from libsql_client import create_client

class YouTubeDatabase:
    def __init__(self):
        # 非同期クライアントを作成
        self.client = create_client(
            url=TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN
        )
    
    def _execute(self, sql, params=None):
        # 非同期メソッドを同期的に呼び出し → エラー
        return self.client.execute(sql, params)
```

**なぜエラーが発生するか**:
1. `create_client()` は非同期クライアントを返す
2. `client.execute()` は `async def` メソッド（コルーチン）
3. コルーチンを実行するには `asyncio.run()` や `await` が必要
4. Streamlit は同期環境なので、イベントループが存在しない
5. → `RuntimeError: no running event loop`

### 試した対処（失敗）

#### 1. `create_client_sync` への変更（失敗）
```python
from libsql_client import create_client_sync

self.client = create_client_sync(...)
```
→ Turso の HTTP API が 505 エラーを返し、接続失敗

#### 2. 専用スレッドでイベントループを実行（失敗）
```python
import threading

def _start_event_loop(self):
    asyncio.set_event_loop(self.loop)
    self.loop_ready.set()
    self.loop.run_forever()

def _run_coroutine(self, coroutine):
    future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
    return future.result()
```
→ Streamlit の再レンダリングでスレッドが中断され、処理が完了しない

---

## 対処

### 最終的な解決策: HTTP API ベースの同期処理

Turso の **HTTP API** を使用して、完全に同期的な処理に変更。

**修正後のコード**:
```python
import requests

class YouTubeDatabase:
    def __init__(self):
        # WebSocket URL を HTTPS URL に変換
        self.base_url = TURSO_DATABASE_URL.replace('libsql://', 'https://').replace('wss://', 'https://')
        self.auth_token = TURSO_AUTH_TOKEN
        self.headers = {
            'Authorization': f'Bearer {self.auth_token}',
            'Content-Type': 'application/json'
        }
    
    def _execute(self, sql, params=None):
        """Execute SQL statement via HTTP API"""
        # パラメータを配列形式に変換
        formatted_params = []
        if params:
            for param in params:
                formatted_params.append(None if param is None else param)
        
        # Turso HTTP API のペイロード形式
        payload = {
            "statements": [
                {
                    "q": sql,
                    "params": formatted_params
                }
            ]
        }
        
        # 同期的な HTTP POST リクエスト
        response = requests.post(
            f'{self.base_url}',
            headers=self.headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        
        # レスポンスをパース
        class Result:
            def __init__(self, rows):
                self.rows = rows
        
        if result and isinstance(result, list) and len(result) > 0:
            stmt_result = result[0]
            
            if 'error' in stmt_result:
                raise Exception(stmt_result['error'].get('message', str(stmt_result['error'])))
            
            rows = []
            if 'results' in stmt_result:
                results_data = stmt_result['results']
                if 'rows' in results_data and results_data['rows']:
                    columns = results_data.get('columns', [])
                    for row_data in results_data['rows']:
                        row_dict = {}
                        for i, col in enumerate(columns):
                            row_dict[col] = row_data[i] if i < len(row_data) else None
                        rows.append(row_dict)
            
            return Result(rows)
        
        return Result([])
```

**ポイント**:
1. `requests` ライブラリで同期的な HTTP POST
2. Turso の HTTP API エンドポイントを使用
3. パラメータは単純な配列形式（`[value1, value2, ...]`）
4. レスポンスは `[{results: {columns: [...], rows: [...]}}]` 形式

---

## 修正ファイル

- `database.py` (全体的に書き換え)
  - 1-5行目: インポート文を変更
  - 16-28行目: `__init__` メソッドを HTTP API 用に変更
  - 30-96行目: `_execute` メソッドを同期処理に変更
  - 357-360行目: `close` メソッドを簡略化

---

## 予防策

### 1. 非同期ライブラリを使う前に確認

```python
# ❌ 悪い例: 非同期クライアントを同期環境で使用
from some_lib import create_async_client
client = create_async_client()
result = client.query()  # RuntimeError!

# ✅ 良い例: 同期クライアントを使用
from some_lib import create_sync_client
client = create_sync_client()
result = client.query()  # OK

# ✅ 良い例: HTTP API を使用
import requests
response = requests.post(api_url, json=payload)
```

### 2. ライブラリのドキュメントを確認

- `async def` や `await` が必要なメソッドは非同期
- `create_client` と `create_client_sync` の違いを確認
- HTTP API が提供されている場合はそちらを優先

### 3. Streamlit での非同期処理

Streamlit で非同期処理が必要な場合:
```python
import asyncio

# 方法1: asyncio.run() を使用
result = asyncio.run(async_function())

# 方法2: 専用スレッドで実行（複雑なので非推奨）
loop = asyncio.new_event_loop()
threading.Thread(target=loop.run_forever, daemon=True).start()
```

---

## 関連問題

- `2025-11-02_turso_http_api_400_bad_request.md` - HTTP API のパラメータ形式エラー
- `2025-11-02_streamlit_rerendering_interruption.md` - Streamlit の再レンダリング問題

---

## 学んだこと

### 1. 非同期と同期の違いを理解する

| 項目 | 非同期 | 同期 |
|------|--------|------|
| 実行方法 | `await` または `asyncio.run()` | 直接呼び出し |
| イベントループ | 必要 | 不要 |
| Streamlit | 使いにくい | 使いやすい |
| パフォーマンス | 高速（並列処理） | 低速（逐次処理） |

### 2. ライブラリ選択の重要性

- 環境に合ったライブラリを選ぶ
- 同期版と非同期版がある場合は、環境に応じて選択
- HTTP API が提供されている場合は、最もシンプルで確実

### 3. エラーメッセージの読み方

```
RuntimeError: no running event loop
```
→ 「イベントループがない」= 非同期処理を同期環境で実行しようとしている

### 4. Turso の接続方法

| 方法 | メリット | デメリット |
|------|----------|------------|
| WebSocket (非同期) | 高速、リアルタイム | イベントループ必要 |
| HTTP API (同期) | シンプル、確実 | 若干遅い |
| `create_client_sync` | 同期的に使える | 不安定（505エラー） |

→ **Streamlit では HTTP API が最適**

---

## 追加情報

### Turso HTTP API の仕様

**エンドポイント**:
```
POST https://[database-name]-[org-name].turso.io/
```

**リクエスト形式**:
```json
{
  "statements": [
    {
      "q": "SELECT * FROM table WHERE id = ?",
      "params": [123]
    }
  ]
}
```

**レスポンス形式**:
```json
[
  {
    "results": {
      "columns": ["id", "name"],
      "rows": [[1, "Alice"], [2, "Bob"]]
    }
  }
]
```

### デバッグのコツ

1. **エラーメッセージを Google 検索**
   - `RuntimeError: no running event loop` → 非同期/同期の問題

2. **ライブラリのドキュメントを確認**
   - 同期版 API の有無
   - HTTP API の提供状況

3. **シンプルな方法を優先**
   - 複雑な非同期処理より、シンプルな HTTP リクエスト

---

**🔥 重要**: 非同期ライブラリを同期環境で使う場合は、必ず同期版 API または HTTP API を使用すること！
