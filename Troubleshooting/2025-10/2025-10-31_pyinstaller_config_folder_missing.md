# PyInstaller EXE化 - config/フォルダ未同梱

**日付**: 2025-10-31
**Keywords**: PyInstaller, spec, datas, _internal, config, post-build, xcopy
**Error**: `[Errno 2] No such file or directory: 'config/credentials.json'`
**影響範囲**: Google Sheets認証、API使用量記録
**重要度**: 🔴 Critical

---

## 症状

EXE実行時にファイル読み込みエラー:

```
[Errno 2] No such file or directory: 'config/credentials.json'
```

**期待動作**: `config/` フォルダと中身がEXEパッケージに含まれる
**実際の動作**: `config/` フォルダが存在しない

---

## 原因

`notion_uploader.spec` の `datas` に `config/` 内ファイルが含まれていない:

```python
# 問題のコード (notion_uploader.spec)
datas=[
    ('config.json', '.'),
    ('README.md', '.'),
    # config/ フォルダの中身が指定されていない
],
```

**PyInstallerの動作**:
- `datas` に明示的に指定したファイルのみパッケージに含める
- フォルダごと指定しても中身は含まれない（フォルダ構造のみ）

---

## 対処

### ステップ1: spec file に config/ 内ファイルを追加

```python
# 修正後のコード (notion_uploader.spec)
datas=[
    ('config.json', '.'),
    ('README.md', '.'),
    ('config/credentials.json', 'config'),  # 追加
    ('config/api_usage.json', 'config'),    # 追加
],
```

**ただし、問題発生**:
- PyInstallerは `_internal/config/` に配置
- コードは実行ディレクトリ直下の `config/` を参照
- `dist/NotionUploader/config/` に存在しない

### ステップ2: post-buildスクリプトで再配置

```batch
# post_build.bat
@echo off
echo Post-build: config folder setup

REM _internal/config/ → config/ にコピー
xcopy /E /I /Y "dist\NotionUploader\_internal\config" "dist\NotionUploader\config"

REM その他の必要ファイルもコピー
copy /Y .env "dist\NotionUploader\.env"
copy /Y config.json "dist\NotionUploader\config.json"

echo Post-build complete!
pause
```

---

## ビルド手順（確定版）

```batch
# 1. PyInstallerでビルド
pyinstaller notion_uploader.spec --clean --noconfirm

# 2. post-buildで自動配置
post_build.bat
```

### 配布パッケージ構成

```
dist/NotionUploader/  ← フォルダごと配布
├── NotionUploader.exe
├── .env
├── config.json
├── config/                  ← post-buildで作成
│   ├── credentials.json
│   └── api_usage.json
├── README.txt
└── _internal/               ← PyInstallerが作成
    ├── config/              ← spec で指定（使わない）
    │   ├── credentials.json
    │   └── api_usage.json
    └── ... (依存ファイル)
```

---

## 修正ファイル

- `notion_uploader.spec` (9-14行目)
- `post_build.bat` (新規作成)

---

## PyInstaller datas の仕組み

### 基本構文
```python
datas=[
    ('source_path', 'destination_folder'),
]
```

### 配置先
```python
# 例1: ルート直下
('config.json', '.')
→ dist/App/_internal/config.json

# 例2: サブフォルダ
('config/api_usage.json', 'config')
→ dist/App/_internal/config/api_usage.json
```

### 注意点
1. **_internal/ に配置される**
   - EXE は _internal/ 内のファイルを参照
   - 実行ディレクトリ直下には配置されない

2. **フォルダごと指定は不可**
   ```python
   # ❌ これではフォルダ構造のみコピー
   ('config/', 'config')

   # ✅ 個別ファイルを指定
   ('config/file1.json', 'config'),
   ('config/file2.json', 'config'),
   ```

3. **ワイルドカード不可**
   ```python
   # ❌ 動かない
   ('config/*.json', 'config')

   # ✅ globで列挙
   from pathlib import Path
   config_files = [(str(f), 'config') for f in Path('config').glob('*.json')]
   datas = config_files + [...]
   ```

---

## 予防策

### post-buildスクリプトの役割明確化

**post_build.bat の責務**:
1. `_internal/` から実行ディレクトリ直下へコピー
2. `.env` などビルド対象外ファイルのコピー
3. `README.txt` の生成
4. 配布パッケージの完成

### 自動化の重要性

```batch
# ビルド + post-build を1コマンドで
build.bat:
@echo off
pyinstaller notion_uploader.spec --clean --noconfirm
if %errorlevel% neq 0 exit /b %errorlevel%
call post_build.bat
```

---

## デバッグ手順

### 問題: ファイルが見つからない

```python
# デバッグコード追加
import os
print("Current dir:", os.getcwd())
print("Files in current dir:", os.listdir('.'))
print("Files in config/:", os.listdir('config/') if os.path.exists('config/') else "No config/")
print("_internal exists?", os.path.exists('_internal/'))
```

### 確認ポイント

1. **spec file 確認**:
   ```bash
   # datas にファイルが含まれているか
   cat notion_uploader.spec | grep "datas"
   ```

2. **_internal/ 確認**:
   ```bash
   ls -la dist/NotionUploader/_internal/config/
   ```

3. **実行dir確認**:
   ```bash
   ls -la dist/NotionUploader/config/
   ```

---

## 関連問題

- パス解決エラー: `2025-10-31_pyinstaller_exe_path_resolution.md`

---

## 学んだこと

1. **PyInstaller のファイル配置ルール**:
   - `datas` → `_internal/` 配下
   - 実行ディレクトリ直下に置くには post-build 必須

2. **2段階ビルドの必要性**:
   - PyInstaller: 依存関係の解決とパッケージング
   - post-build: 配布用の最終調整

3. **xcopy コマンド**:
   ```batch
   xcopy /E /I /Y "source" "dest"
   /E: サブディレクトリ含む（空も）
   /I: 宛先がない場合ディレクトリ作成
   /Y: 上書き確認なし
   ```

4. **配布パッケージの構成**:
   - EXE + _internal/ (必須)
   - 設定ファイル (ルート直下)
   - README (使い方説明)
   - フォルダごとコピーで即使用可能
