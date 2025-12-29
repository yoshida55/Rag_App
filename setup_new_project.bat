@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM エラーが起きても継続
verify >nul
goto :main

:error_handler
echo.
echo ========================================
echo ❌ エラーが発生しました
echo ========================================
echo エラーコード: %ERRORLEVEL%
echo.
pause
exit /b %ERRORLEVEL%

:main

echo ========================================
echo    新規PJ / 既存PJ セットアップ
echo ========================================
echo.
echo 📂 現在のPJ: %CD%
echo.

REM 次のPJのパスを入力
echo.
set /p "TARGET_DIR=次のPJのパスを入力してください: "

REM 入力チェック
if "!TARGET_DIR!"=="" (
    echo ❌ エラー: パスが入力されていません
    pause
    exit /b 1
)

REM パスの存在確認
if not exist "!TARGET_DIR!" (
    echo ⚠️  警告: 指定されたパスが存在しません
    echo    パス: !TARGET_DIR!
    echo.
    set /p "CREATE_DIR=フォルダを作成しますか? (Y/N): "
    if /i "!CREATE_DIR!"=="Y" (
        mkdir "!TARGET_DIR!"
        echo ✅ フォルダを作成しました
    ) else (
        echo ❌ セットアップを中止しました
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo    対象PJ: !TARGET_DIR!
echo ========================================
echo.

REM テンプレートディレクトリ
set "TEMPLATE_DIR=%USERPROFILE%\.claude"
set "CURRENT_DIR=%CD%"
set "CURRENT_MONTH=2025-11"

echo ========================================
echo    1. .claudeignore のコピー
echo ========================================

REM .claudeignore は常に上書き
if exist "%TEMPLATE_DIR%\TEMPLATE_claudeignore" (
    echo コピー中: TEMPLATE_claudeignore → .claudeignore
    copy /Y "%TEMPLATE_DIR%\TEMPLATE_claudeignore" "!TARGET_DIR!\.claudeignore"
    if errorlevel 1 (
        echo ❌ コピー失敗
        pause
        exit /b 1
    )
    echo ✅ .claudeignore をコピーしました（上書き）
) else (
    echo ❌ エラー: テンプレートファイルが見つかりません
    echo    場所: %TEMPLATE_DIR%\TEMPLATE_claudeignore
    pause
    exit /b 1
)

echo.
echo ========================================
echo    2. PROJECT_MAP.md の作成
echo ========================================

REM PROJECT_MAP.md は既存があればスキップ
if exist "!TARGET_DIR!\PROJECT_MAP.md" (
    echo ⏭️  PROJECT_MAP.md は既に存在します（スキップ）
) else (
    if exist "%TEMPLATE_DIR%\TEMPLATE_PROJECT_MAP.md" (
        echo コピー中: PROJECT_MAP.md
        copy /Y "%TEMPLATE_DIR%\TEMPLATE_PROJECT_MAP.md" "!TARGET_DIR!\PROJECT_MAP.md"
        echo ✅ PROJECT_MAP.md をコピーしました（新規作成）
    ) else (
        echo ❌ エラー: テンプレートファイルが見つかりません
        echo    場所: %TEMPLATE_DIR%\TEMPLATE_PROJECT_MAP.md
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo    3. Troubleshooting/ フォルダ作成
echo ========================================

REM Troubleshooting フォルダ作成
if not exist "!TARGET_DIR!\Troubleshooting" (
    mkdir "!TARGET_DIR!\Troubleshooting"
    echo ✅ Troubleshooting フォルダを作成しました
) else (
    echo ⏭️  Troubleshooting フォルダは既に存在します
)

echo.
echo ========================================
echo    4. Troubleshooting/README.md の作成
echo ========================================

REM Troubleshooting/README.md は既存があればスキップ
if exist "!TARGET_DIR!\Troubleshooting\README.md" (
    echo ⏭️  Troubleshooting\README.md は既に存在します（スキップ）
) else (
    if exist "%TEMPLATE_DIR%\TEMPLATE_Troubleshooting_README.md" (
        echo コピー中: Troubleshooting\README.md
        copy /Y "%TEMPLATE_DIR%\TEMPLATE_Troubleshooting_README.md" "!TARGET_DIR!\Troubleshooting\README.md"
        echo ✅ Troubleshooting\README.md をコピーしました（新規作成）
    ) else (
        echo ❌ エラー: テンプレートファイルが見つかりません
        echo    場所: %TEMPLATE_DIR%\TEMPLATE_Troubleshooting_README.md
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo    5. Troubleshooting/月別フォルダ 同期
echo ========================================

REM Troubleshootingフォルダ全体を同期
set "SOURCE_TROUBLESHOOTING_ROOT=%CURRENT_DIR%\Troubleshooting"

echo 📁 ソース: %SOURCE_TROUBLESHOOTING_ROOT%
echo 📁 ターゲット: !TARGET_DIR!\Troubleshooting
echo.

REM ソースフォルダ存在チェック
if not exist "%SOURCE_TROUBLESHOOTING_ROOT%" goto NO_SOURCE_ROOT

REM 月別フォルダをカウント
set "FOLDER_COUNT=0"
set "TOTAL_FILE_COUNT=0"
for /d %%D in ("%SOURCE_TROUBLESHOOTING_ROOT%\*") do (
    set /a FOLDER_COUNT+=1
    for /f %%A in ('dir "%%D" /B /A-D 2^>nul ^| find /c /v ""') do set /a TOTAL_FILE_COUNT+=%%A
)

echo 📊 月別フォルダ数: !FOLDER_COUNT! 個
echo 📊 総ファイル数: !TOTAL_FILE_COUNT! 個
echo.

REM robocopy で全月フォルダを同期（不要ファイルは除外）
echo コピー実行中...
robocopy "%SOURCE_TROUBLESHOOTING_ROOT%" "!TARGET_DIR!\Troubleshooting" *.* /E /R:0 /W:0 /XF README.md SETUP.bat *.ps1 _TEMPLATE_* /NFL /NDL /NJH /NJS
echo.

if "!TOTAL_FILE_COUNT!" GTR "0" (
    echo ✅ Troubleshooting\ 全体を同期しました（!FOLDER_COUNT! フォルダ、!TOTAL_FILE_COUNT! ファイル）
) else (
    echo ⚠️  月別フォルダは空です
    echo    📝 問題が発生したら Troubleshooting\%CURRENT_MONTH%\ に記録してください
)
goto SYNC_DONE

:NO_SOURCE_ROOT
echo 📊 月別フォルダ数: 0 個
echo.
echo ⚠️  Troubleshootingフォルダが見つかりません: %SOURCE_TROUBLESHOOTING_ROOT%
echo    新規に空フォルダを作成します...

if not exist "!TARGET_DIR!\Troubleshooting\%CURRENT_MONTH%" mkdir "!TARGET_DIR!\Troubleshooting\%CURRENT_MONTH%"
echo ✅ Troubleshooting\%CURRENT_MONTH% を作成しました（空）

:SYNC_DONE

echo.
echo ========================================
echo    ✅ セットアップ完了！
echo ========================================
echo.
echo 📋 作成・更新されたファイル:
echo    📂 対象PJ: !TARGET_DIR!
echo.
echo    ✅ .claudeignore （上書き）
if not exist "!TARGET_DIR!\PROJECT_MAP.md.bak" (
    echo    ✅ PROJECT_MAP.md （新規作成 or スキップ）
)
if not exist "!TARGET_DIR!\Troubleshooting\README.md.bak" (
    echo    ✅ Troubleshooting\README.md （新規作成 or スキップ）
)
echo    ✅ Troubleshooting\ 全月フォルダ （同期完了）
echo.
echo 次のステップ:
echo    1. cd "!TARGET_DIR!" でPJに移動
echo    2. PROJECT_MAP.md を開いてプロジェクト構造を記入
echo    3. 問題が発生したら Troubleshooting/%CURRENT_MONTH%/ に記録
echo.
REM run_setup_with_log.bat もコピー
if exist "%CURRENT_DIR%\run_setup_with_log.bat" (
    copy /Y "%CURRENT_DIR%\run_setup_with_log.bat" "!TARGET_DIR!\run_setup_with_log.bat" >nul
    echo    ✅ run_setup_with_log.bat （コピー完了）
)

REM setup_new_project.bat 自身もコピー
if exist "%CURRENT_DIR%\setup_new_project.bat" (
    copy /Y "%CURRENT_DIR%\setup_new_project.bat" "!TARGET_DIR!\setup_new_project.bat" >nul
    echo    ✅ setup_new_project.bat （コピー完了）
)

REM update_top10.bat もコピー（Troubleshootingフォルダ内）
if exist "%CURRENT_DIR%\Troubleshooting\update_top10.bat" (
    copy /Y "%CURRENT_DIR%\Troubleshooting\update_top10.bat" "!TARGET_DIR!\Troubleshooting\update_top10.bat" >nul
    echo    ✅ update_top10.bat （コピー完了）
)

echo.
echo ========================================
echo    処理完了 - Enterキーで終了
echo ========================================
pause >nul
