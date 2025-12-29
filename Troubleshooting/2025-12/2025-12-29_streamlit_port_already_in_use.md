# Streamlit 起動時にポートが既に使用中エラー

**日付**: 2025-12-29
**Keywords**: Streamlit, ポート, port, already in use, 8501, 8503, 競合, プロセス, taskkill
**Error**: "Port 8501 is already in use"
**影響範囲**: アプリケーション起動
**重要度**: 🟡 Important

---

## 症状

Streamlitアプリを再起動しようとすると、ポートが使用中でエラーになる。

**期待動作**: アプリが正常に起動する
**実際の動作**: `Port 8501 is already in use` エラー

---

## 原因

前回のStreamlitプロセスが終了せずに残っている。

```bash
# 確認コマンド
netstat -ano | grep 8501
# 出力例:
# TCP 0.0.0.0:8501 LISTENING 229840
```

**根本原因**:
- Ctrl+Cでプロセスを停止したが、完全に終了していない
- バックグラウンドで実行中のプロセスがある
- 前のセッションのプロセスが残っている

---

## 対処

### 方法1: 別のポートで起動（推奨）

```bash
streamlit run app.py --server.port 8503
```

### 方法2: プロセスを強制終了（Windows）

```bash
# ポートを使用しているプロセスIDを確認
netstat -ano | findstr 8501
# 出力例: TCP 0.0.0.0:8501 LISTENING 229840

# プロセスを強制終了
taskkill /F /PID 229840
```

### 方法3: streamlit.exeを全て終了

```bash
taskkill /F /IM streamlit.exe
```

### 方法4: Pythonプロセスを全て終了（最終手段）

```bash
taskkill /F /IM python.exe
```

---

## 修正ファイル

なし（運用対応）

---

## 予防策

1. 開発時は固定ポートではなく、別ポートを指定する
2. アプリ終了時は確実にプロセスを停止する
3. 起動スクリプトで既存プロセスを終了する

### 起動スクリプト例（start_app.bat）

```batch
@echo off
REM 既存のStreamlitプロセスを終了
taskkill /F /IM streamlit.exe 2>nul

REM 少し待機
timeout /t 2 /nobreak >nul

REM アプリ起動
cd /d %~dp0
call venv\Scripts\activate
streamlit run app.py --server.port 8503
```

---

## 学んだこと

- 開発中は複数回の起動/停止が発生する
- ポート競合は頻繁に起きる問題
- 別ポートで起動するのが最も簡単な解決策
- 起動スクリプトで既存プロセスを終了するのがベスト
