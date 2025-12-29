@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM 現在の年月を取得
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do (
    set CURRENT_YEAR=%%c
    set CURRENT_MONTH=%%b
)

REM 月をゼロ埋め（例: 9 → 09）
if "!CURRENT_MONTH:~0,1!"==" " set CURRENT_MONTH=0!CURRENT_MONTH:~1,1!
if "!CURRENT_MONTH:~1,1!"=="" set CURRENT_MONTH=0!CURRENT_MONTH!

set "YEAR_MONTH=!CURRENT_YEAR!-!CURRENT_MONTH!"

echo ========================================
echo    TOP 10 自動更新（月次メンテナンス）
echo ========================================
echo.
echo 📅 現在の年月: !YEAR_MONTH!
echo 📂 対象フォルダ: Troubleshooting\!YEAR_MONTH!\
echo.
echo ========================================
echo    以下を Claude Code にコピペしてください
echo ========================================
echo.
echo ---コピー開始---
echo.
echo 今月の Troubleshooting フォルダ（Troubleshooting/!YEAR_MONTH!/）の全ファイルを読んで、以下を実行してください:
echo.
echo 【タスク】
echo 1. 各ファイルの Keywords を集計
echo 2. 頻出キーワード（3回以上出現）を特定
echo 3. 同じ問題と思われるファイルをグループ化
echo 4. README.md の「よくあるエラー TOP 10」を更新:
echo    - 頻度が高い問題を上位に配置
echo    - 既存の TOP 10 と比較して追加/削除判断
echo    - 新規追加する場合は適切なカテゴリに配置
echo 5. 更新内容をレポート（追加/削除/順位変更）
echo.
echo 【注意】
echo - Keywords が豊富なファイルを優先してください
echo - 重要度（🔴🟡🟢）も考慮してください
echo - 同じ問題のファイルが複数ある場合はグループ化してください
echo.
echo ---コピー終了---
echo.
echo ========================================
echo    💡 使い方
echo ========================================
echo.
echo 1. 上記の「---コピー開始---」から「---コピー終了---」までを選択
echo 2. Ctrl+C でコピー
echo 3. Claude Code に貼り付けて送信
echo 4. 完了を待つ（約1-2分）
echo.
echo ========================================
echo    📊 実行頻度
echo ========================================
echo.
echo 推奨: 月2回（15日 & 月末）
echo.
echo ========================================
pause
