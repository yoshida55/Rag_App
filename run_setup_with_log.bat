@echo off
echo ログ付きでsetup_new_project.batを実行します...
echo.
echo ログファイル: setup_log.txt
echo.

call setup_new_project.bat > setup_log.txt 2>&1

echo.
echo ========================================
echo 実行完了 - ログを確認してください
echo ========================================
echo ファイル: setup_log.txt
echo.

type setup_log.txt

echo.
echo.
pause
