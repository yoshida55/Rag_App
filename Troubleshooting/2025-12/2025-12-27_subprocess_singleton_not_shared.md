# 別プロセス間でシングルトンが共有されない問題（HTTPサーバー競合）

**日付**: 2025-12-27
**Keywords**: subprocess, シングルトン, singleton, HTTPServer, ポート競合, port conflict, threading.Event, response_event, タイムアウト, timeout, request_tabs, Chrome拡張, chrome extension, 別プロセス, separate process, get_server, クラス変数, class variable, preset_manager_gui
**Error**: `[REQ_TABS] ❌ タイムアウト` / `response_event=None`
**影響範囲**: Chrome拡張との通信、プリセット保存時のタブ情報取得
**重要度**: 🔴 Critical

---

## 症状

### 期待動作
- ユーザーがトレイから「プリセット管理」を開く
- GUIで「現在の状態を保存」をクリック
- Chromeタブ情報が取得され、プリセットに含まれる

### 実際の動作
- `request_tabs(timeout=5.0)` が5秒待ってタイムアウト
- Chrome拡張からのPOST /tabsは200で成功しているのに、イベントがセットされない
- ログに `[TABS] response_event=None` と表示される

### 観察されたログ
```
[REQ_TABS] ★★★ 10:32:59.239 タブ情報待機開始（5.0秒） ★★★
[REQ_TABS] 新しいイベント作成: 2537979825200
[REQ_TABS] wait(5.0)開始...

[POST_START] ★★★ do_POST開始 ★★★
[TABS] ★★★ 10:33:00.096 受信: 2ウィンドウ ★★★
[TABS] response_event=None  ← ★ここが問題！イベントがNone★
[TABS] イベント待機なし

[REQ_TABS] ★★★ 10:33:04.246 ❌ タイムアウト ★★★
```

### 追加の観察ポイント
サーバーが2回起動されていた：
```
[CHROME_COMM] start() 呼び出し, _running=False  ← main.py
[CHROME_COMM] ✅ HTTPサーバー起動

[CHROME_COMM] start() 呼び出し, _running=False  ← preset_manager_gui.py（別プロセス）
[CHROME_COMM] ✅ HTTPサーバー起動  ← 2つ目のサーバー！
```

---

## 原因

### 根本原因: subprocess.Popenによる別プロセス起動

main.py から preset_manager_gui.py を呼び出す際に `subprocess.Popen()` を使用していた：

```python
# main.py:428-432
import subprocess
script_path = Path(__file__).parent / 'preset_manager_gui.py'
subprocess.Popen([sys.executable, str(script_path)], cwd=str(script_path.parent))
```

### なぜ問題になるか

1. **シングルトンは同一プロセス内でのみ有効**
   - `get_server()` はモジュールレベルのグローバル変数 `_server_instance` を使用
   - 別プロセスでは別のPythonインタプリタが起動するため、グローバル変数は共有されない

2. **HTTPServerの競合**
   - プロセス1（main.py）: port 18080 で HTTPServer 起動
   - プロセス2（preset_manager_gui.py）: 同じ port 18080 で HTTPServer 起動
   - Windowsでは `SO_REUSEADDR` の挙動により、同じポートで複数サーバーが起動できることがある

3. **イベントの不整合**
   - `request_tabs()` はプロセス2のクラス変数 `ChromeCommHandler.response_event` にイベントをセット
   - Chrome拡張からのPOSTはプロセス1のサーバーに到着
   - プロセス1の `do_POST()` では `response_event=None`（プロセス2でセットされたため見えない）

### 問題の図解
```
プロセス1 (main.py)
├── ChromeCommHandler.response_event = None
├── HTTPServer on :18080 ← Chrome拡張からのPOSTはこちらに到着
└── イベントはNoneなのでセットされない

プロセス2 (preset_manager_gui.py) ← subprocess.Popen()で起動
├── ChromeCommHandler.response_event = Event()  ← ここにセット
├── HTTPServer on :18080（2つ目）
└── request_tabs() で待機中...タイムアウト
```

---

## 対処

### 修正1: ポート使用中ならサーバー起動をスキップ

```python
# preset_manager_gui.py:166-185
def _start_chrome_server(self):
    """Chrome通信サーバー起動（main.pyが起動中ならスキップ）"""
    import socket
    port = self.config.get('chrome_extension_port', 18080)

    # ポートが使用中か確認（main.pyが起動中）
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('127.0.0.1', port))
        sock.close()
        # ポート空き → 自分でサーバー起動
        self.chrome_server = get_server(port)
        self.chrome_server.set_tabs_callback(self._on_chrome_tabs_received)
        self.chrome_server.start()
        logger.info(f"[GUI] Chrome通信サーバー起動: port={port}")
    except OSError:
        # ポート使用中 → main.pyが起動中なのでサーバー起動しない
        sock.close()
        self.chrome_server = None
        logger.info(f"[GUI] main.pyが起動中、サーバー起動スキップ")
```

### 修正2: HTTPでタブ情報を取得するエンドポイント追加

```python
# chrome_comm.py:82-89 (do_GET内)
elif path == '/get-chrome-tabs':
    # キャッシュされたChromeタブ情報を返す（preset_manager_gui.py用）
    if ChromeCommHandler.cached_tabs_data:
        logger.info(f"[HTTP] Chromeタブキャッシュ返却")
        self._send_json_response(ChromeCommHandler.cached_tabs_data)
    else:
        logger.warning(f"[HTTP] Chromeタブキャッシュなし")
        self._send_json_response({'windows': []})
```

### 修正3: キャッシュ更新

```python
# chrome_comm.py:127-128 (do_POST内、/tabs処理)
# キャッシュ更新（/get-chrome-tabsで利用）
ChromeCommHandler.cached_tabs_data = data
```

### 修正4: HTTPでタブ情報取得

```python
# preset_manager_gui.py:192-205
def _get_chrome_tabs_via_http(self):
    """main.pyのサーバーからHTTPでChromeタブ情報を取得"""
    try:
        port = self.config.get('chrome_extension_port', 18080)
        url = f"http://127.0.0.1:{port}/get-chrome-tabs"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8'))
                logger.info(f"[GUI] HTTPでChromeタブ取得: {len(data.get('windows', []))}ウィンドウ")
                return data
    except Exception as e:
        logger.warning(f"[GUI] HTTPタブ取得失敗: {e}")
    return None
```

---

## 修正ファイル

- `python/chrome_comm.py` (行25, 82-89, 127-128)
  - クラス変数 `cached_tabs_data` 追加
  - `/get-chrome-tabs` エンドポイント追加
  - POST /tabs でキャッシュ更新

- `python/preset_manager_gui.py` (行166-185, 192-205, 354-364)
  - `_start_chrome_server()` にポート確認追加
  - `_get_chrome_tabs_via_http()` 追加
  - 保存時のタブ取得ロジック変更

---

## デバッグに時間がかかった理由

### 1. print()の出力遅延
```python
# 悪い例（出力がバッファされて遅延）
print(f"[DEBUG] 処理開始")

# 良い例（即座に出力）
print(f"[DEBUG] 処理開始", flush=True)
```

### 2. 別プロセス問題の発見が困難
- シングルトンパターンを使っているから「同じインスタンス」と思い込んでいた
- `_running=False` が2回出力されていることに気づくまで時間がかかった
- subprocess.Popen()が別プロセスを起動することを見落としていた

### 3. HTTPServerの競合が見えにくい
- Windowsでは同じポートで複数サーバーが起動できてしまう
- エラーにならないため問題に気づきにくい

---

## 予防策

### 1. subprocess.Popen()を使う場合の注意
- **グローバル変数・シングルトンは共有されない**ことを意識
- プロセス間通信が必要なら、HTTP/ソケット/ファイルを使用

### 2. ポート使用前の確認
```python
import socket
def is_port_in_use(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('127.0.0.1', port))
        sock.close()
        return False
    except OSError:
        return True
```

### 3. デバッグ時は flush=True
```python
print(f"[DEBUG] メッセージ", flush=True)
```

### 4. サーバー起動時のログにプロセスID追加
```python
import os
print(f"[SERVER] PID={os.getpid()} サーバー起動")
```

---

## 関連問題

- ポート競合全般
- シングルトンパターンの落とし穴
- プロセス間通信

---

## 学んだこと

1. **Pythonのシングルトンは同一プロセス内でのみ有効**
   - subprocess.Popen()で起動した別プロセスでは別のインスタンスになる

2. **Windowsのポート挙動は緩い**
   - 同じポートで複数サーバーが起動できてしまうことがある
   - 起動前にポート確認が必須

3. **デバッグログは即座に出力**
   - `print(flush=True)` または `sys.stdout.flush()` を使用
   - バッファリングで出力が遅延すると原因特定が困難

4. **「動いているはず」を疑う**
   - HTTP 200が返っても、期待通りに動いているとは限らない
   - 内部状態（response_event など）を詳細にログ出力

5. **プロセス間通信はHTTPで行う**
   - 別プロセスとデータをやり取りするなら、HTTPエンドポイントを用意
   - クラス変数やグローバル変数に頼らない
