# Flask サーバー起動時の複数問題（依存関係・DB設定・async関数・ポート競合）

**日付**: 2025-11-02
**Keywords**: Flask, APScheduler, SQLAlchemy, PostgreSQL, psycopg2, async, port conflict, 依存関係, データベース設定, ポート5000, ポート競合, Python, pip install, requirements.txt
**Error**: 
- `ModuleNotFoundError: No module named 'apscheduler'`
- `ModuleNotFoundError: No module named 'psycopg2'`
- `RuntimeError: ... async views ... install an async server`
- ポート5000が複数プロセスで占有
**影響範囲**: サーバー起動全体
**重要度**: 🔴 Critical

---

## 症状

Flaskサーバー起動時に複数のエラーが連鎖的に発生し、起動に時間がかかった。

**期待動作**: `python run.py` で即座にサーバーが起動する
**実際の動作**: 以下のエラーが順次発生
1. APScheduler未インストール
2. PostgreSQLドライバ未インストール
3. async関数エラー
4. ポート競合（古いプロセスが残存）

---

## 原因

### 1. 依存関係未インストール
- `requirements.txt` に記載されているが、`pip install` が実行されていなかった
- 特に `APScheduler==3.11.0` が未インストール

### 2. データベース設定の問題
```python
# config/development.py（修正前）
QLALCHEMY_TRACK_MODIFICATIONS = False  # タイポ（先頭のSが欠落）
SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")  # PostgreSQL前提
```

**根本原因**:
- 環境変数 `DATABASE_URL` が未設定
- PostgreSQLドライバ `psycopg2` が未インストール
- ローカル開発ではSQLiteにフォールバックすべき

### 3. async関数の誤用
```python
# backend/routes/__init__.py（修正前）
@main.route('/api/chat', methods=['POST'])
async def chat_api():  # ← Flask標準ではasync非対応
    ...
```

**根本原因**:
- Flask 2.x以降は一部asyncサポートあるが、標準では非推奨
- `asgiref` などの追加ライブラリが必要
- 今回のコードは同期処理で十分

### 4. ポート競合
- 過去の起動失敗でプロセスが残存
- 複数のPythonプロセスがポート5000を占有
- `taskkill` で一部プロセスが「アクセス拒否」で終了不可

---

## 対処

### 1. 依存関係インストール
```bash
python -m pip install -r requirements.txt
```

**結果**: APScheduler含む全パッケージがインストール完了

### 2. データベース設定修正
```python
# config/development.py（修正後）
SQLALCHEMY_TRACK_MODIFICATIONS = False  # タイポ修正
_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(_BASE_DIR, 'app.db')}"  # SQLiteに固定
```

**ポイント**:
- ローカル開発はSQLiteで統一（psycopg2不要）
- 環境変数に依存しない設定

### 3. async関数を同期関数に変更
```python
# backend/routes/__init__.py（修正後）
@main.route('/api/chat', methods=['POST'])
def chat_api():  # async削除
    try:
        data = request.get_json()
        ...
```

**ポイント**:
- `async` キーワードを削除
- 内部処理は同期のまま（問題なし）

### 4. ポート競合解決
```bash
# ポート確認
netstat -ano | findstr :5000

# プロセス強制終了
taskkill /F /PID 40488 /PID 29124 /PID 45732 /PID 45452

# 終了できないプロセスがある場合はポート変更
```

**最終対処**: ポート5001に変更
```python
# run.py
if __name__ == '__main__':
    app.run(debug=app.config["DEBUG"], port=5001)  # 5000 → 5001
```

---

## 修正ファイル

- `requirements.txt` → 変更なし（既に正しい）
- `config/development.py` (行22-24) → タイポ修正 + SQLiteに固定
- `backend/routes/__init__.py` (行85) → `async` 削除
- `run.py` (行8) → ポート5001に変更

---

## 予防策

### 1. 初回セットアップ手順の明確化
```bash
# 新規環境での起動前に必ず実行
python -m pip install -r requirements.txt
```

### 2. データベース設定のベストプラクティス
```python
# 開発環境はSQLite固定、本番のみ環境変数使用
if os.getenv('ENVIRONMENT') == 'production':
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
else:
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(_BASE_DIR, 'app.db')}"
```

### 3. async使用の判断基準
- Flask標準では同期関数を使用
- 本当にasyncが必要な場合は `Quart` や `FastAPI` を検討
- 単純なAPI呼び出しは同期で十分

### 4. ポート競合の予防
```bash
# 起動前にポート確認
netstat -ano | findstr :5000

# 開発用スクリプトに組み込み
if netstat -ano | findstr :5000; then
    echo "ポート5000は使用中です。プロセスを終了してください。"
    exit 1
fi
```

---

## 関連問題

- `2025-10-31_pyinstaller_path_resolution.md` → パス解決問題
- `2025-11-01_windows_batch_parentheses_path_error.md` → バッチファイル問題

---

## 学んだこと

### 1. 依存関係管理の重要性
- `requirements.txt` があっても自動インストールされない
- 新規環境では必ず `pip install -r requirements.txt` を実行

### 2. 開発環境と本番環境の分離
- ローカル開発では軽量なSQLiteを使用
- PostgreSQLは本番環境のみ
- 環境変数への依存を最小化

### 3. Flaskのasync制限
- Flask標準ではasyncサポートが限定的
- 不要なasyncは避ける（複雑化するだけ）
- 必要なら専用フレームワーク（Quart/FastAPI）を検討

### 4. プロセス管理の重要性
- 開発中のプロセス残存は頻繁に発生
- ポート変更は一時的な回避策
- 根本的にはプロセス管理を徹底

### 5. エラーの連鎖
- 1つのエラーが次のエラーを引き起こす
- 最初のエラーから順に解決することが重要
- 焦らず1つずつ対処

---

## チェックリスト（新規環境セットアップ時）

```bash
# 1. 依存関係インストール
python -m pip install -r requirements.txt

# 2. データベース設定確認
# config/development.py の SQLALCHEMY_DATABASE_URI を確認

# 3. ポート確認
netstat -ano | findstr :5000

# 4. 起動テスト
python run.py

# 5. 動作確認
curl http://localhost:5000/ping
```

---

## 所要時間

- 問題発生から解決まで: 約30分
- 主な時間消費:
  - 依存関係インストール: 5分
  - データベース設定修正: 5分
  - async問題解決: 3分
  - ポート競合解決: 10分
  - 動作確認: 7分

**教訓**: 初回セットアップ手順を明確にしておけば5分で起動可能
