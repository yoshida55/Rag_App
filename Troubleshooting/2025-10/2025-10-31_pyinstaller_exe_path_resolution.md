# PyInstaller EXE化 - パス解決エラー

**日付**: 2025-10-31
**Keywords**: PyInstaller, sys.frozen, sys.executable, __file__, 相対パス, EXE, os.chdir, BASE_DIR
**Error**: ログファイル空（起動前クラッシュ）
**影響範囲**: EXE配布パッケージ全体
**重要度**: 🔴 Critical

---

## 症状

PyInstallerでEXE作成後、デスクトップ等の別ディレクトリに移動すると起動しない:

**動作環境**:
- ✅ ビルドディレクトリ (`dist/NotionUploader/`): 正常動作
- ❌ デスクトップにコピー: 起動せず、固まる

**ログ**:
- ログファイルは作成される
- **中身は空** → logging初期化前にクラッシュ

---

## 原因

EXE化すると `__file__` が実行ファイルのパスを正しく指さない:

```python
# 問題のコード (main.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# → ビルド時のパス: D:\...\60_Notion Uploader System\
```

**通常のPython実行時**:
```python
__file__ = "D:\Project\main.py"
BASE_DIR = "D:\Project"  # ✅ 正しい
```

**EXE実行時**:
```python
__file__ = ???  # PyInstallerが内部で書き換え
BASE_DIR = "D:\...\build_dir"  # ❌ ビルド時のパスのまま
```

**結果**:
- `config.json`, `.env` などの相対パスが壊れる
- ファイル読み込み失敗 → 即座にクラッシュ
- logging初期化前なのでログに何も残らない

---

## 対処

`sys.frozen` で実行形態を判定し、EXE時は `sys.executable` を使用:

```python
# 修正後のコード (main.py)
import sys
import os

if getattr(sys, 'frozen', False):
    # PyInstallerでEXE化された場合
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 通常のPythonスクリプトとして実行された場合
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# カレントディレクトリを実行ファイルの場所に変更
os.chdir(BASE_DIR)

# プロジェクトルートをパスに追加
sys.path.insert(0, BASE_DIR)
```

**動作**:
```python
# 通常実行
frozen = False
BASE_DIR = os.path.dirname(__file__)  # D:\Project

# EXE実行（ビルドdir）
frozen = True
sys.executable = "D:\Project\dist\NotionUploader\NotionUploader.exe"
BASE_DIR = "D:\Project\dist\NotionUploader"

# EXE実行（デスクトップ）
frozen = True
sys.executable = "C:\Users\user\Desktop\NotionUploader\NotionUploader.exe"
BASE_DIR = "C:\Users\user\Desktop\NotionUploader"  # ✅ 正しい！
```

---

## 修正ファイル

- `main.py` (11-23行目)

---

## os.chdir(BASE_DIR) の重要性

```python
os.chdir(BASE_DIR)
```

**理由**:
- 相対パス (`config.json`, `.env`) を BASE_DIR 基準にする
- カレントディレクトリが変わっても一貫性を保つ

**例**:
```python
# os.chdir() なし
カレントdir: C:\Users\user\
BASE_DIR: C:\Users\user\Desktop\NotionUploader\
open('config.json')  # → C:\Users\user\config.json を探す ❌

# os.chdir(BASE_DIR) あり
カレントdir: C:\Users\user\Desktop\NotionUploader\
BASE_DIR: C:\Users\user\Desktop\NotionUploader\
open('config.json')  # → C:\Users\user\Desktop\NotionUploader\config.json ✅
```

---

## 予防策

**EXE化時のチェックリスト**:

1. **パス解決**:
   ```python
   ✅ sys.frozen 判定
   ✅ sys.executable 使用
   ✅ os.chdir() でカレントディレクトリ変更
   ```

2. **絶対パス vs 相対パス**:
   ```python
   # 推奨: 相対パスを BASE_DIR 基準に変換
   config_path = os.path.join(BASE_DIR, 'config.json')
   ```

3. **デバッグ版作成**:
   ```python
   # notion_uploader.spec
   console=True  # コンソールウィンドウ表示
   ```

4. **異なる場所でテスト**:
   - ビルドディレクトリ
   - デスクトップ
   - Cドライブ直下
   - 日本語パス

---

## デバッグ手順

### ステップ1: コンソール版ビルド
```python
# notion_uploader.spec
exe = EXE(
    ...
    console=True,  # エラーメッセージ表示
    ...
)
```

### ステップ2: エラー確認
```bash
NotionUploader.exe  # コンソールにエラー表示
```

### ステップ3: パス確認ログ追加
```python
print(f"sys.frozen: {getattr(sys, 'frozen', False)}")
print(f"sys.executable: {sys.executable}")
print(f"__file__: {__file__}")
print(f"BASE_DIR: {BASE_DIR}")
print(f"Current dir: {os.getcwd()}")
```

---

## 関連問題

- config/フォルダ未同梱: `2025-10-31_pyinstaller_config_folder.md`
- post-buildスクリプト: `post_build.bat`

---

## 学んだこと

1. **sys.frozen の仕組み**:
   ```python
   # PyInstallerが自動的に設定
   sys.frozen = True  # EXE実行時
   sys.frozen = False (未定義)  # 通常実行時

   # 安全な判定
   if getattr(sys, 'frozen', False):
       # EXE
   ```

2. **sys.executable の違い**:
   ```python
   # 通常実行
   sys.executable = "C:\Python313\python.exe"

   # EXE実行
   sys.executable = "C:\Path\To\App.exe"
   ```

3. **__file__ の罠**:
   - PyInstaller は `__file__` を書き換える
   - EXE 内部の仮想パスになることがある
   - **信頼してはいけない**

4. **ベストプラクティス**:
   ```python
   # 推奨パターン
   if getattr(sys, 'frozen', False):
       app_dir = os.path.dirname(sys.executable)
   else:
       app_dir = os.path.dirname(os.path.abspath(__file__))

   os.chdir(app_dir)
   ```
