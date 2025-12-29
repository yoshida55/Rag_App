# Anthropic Claude API 接続エラーの解決

**日付**: 2025-11-02
**Keywords**: Anthropic, Claude API, API key, 500 Internal Server Error, anthropic version, httpx, system role, venv, 環境変数, モデル名
**Error**: "Client.__init__() got an unexpected keyword argument 'proxies'" / "messages: Unexpected role 'system'"
**影響範囲**: チャットAPI機能全体
**重要度**: 🔴 Critical

---

## 症状

チャットAPIで「明日の天気は？」などの質問を送信すると、500 Internal Server Error が発生。

**期待動作**: AIが適切に応答し、最新情報が必要な場合はWeb検索を案内
**実際の動作**: 500エラーが返り、サーバーログにAPI関連エラーが表示

---

## 原因

複数の要因が複合的に絡んでいた:

1. **APIキーの不一致**: .envファイルのキーが古かった
2. **モデル名の間違い**: anthropic 0.72.0ではサポートされていないモデル名を使用
3. **venv環境の問題**: newVenvが正しくアクティベートされていなかった
4. **httpxバージョン問題**: 新しいhttpxがproxies引数の仕様を変更
5. **systemロールの使い方**: anthropic 0.34.0ではmessages内ではなくsystemパラメータを使用

**根本原因**:
- anthropicライブラリのバージョンとAPI仕様の不一致
- 環境設定の不備（venv、環境変数、依存関係）

---

## 対処

1. **APIキーの更新**:
   ```powershell
   $env:ANTHROPIC_API_KEY = "新しいキー"
   ```

2. **anthropicバージョンを参考システムに合わせる**:
   ```powershell
   pip uninstall anthropic -y
   pip install anthropic==0.34.0
   ```

3. **httpxバージョンを固定**:
   ```powershell
   pip install httpx==0.27.2
   ```

4. **venvの正しいアクティベート**:
   ```powershell
   .\newVenv\Scripts\Activate
   ```

5. **システムロールの修正**:
   ```python
   # 修正前
   messages=[{
       "role": "system",
       "content": "システムプロンプト"
   }, {
       "role": "user", 
       "content": "ユーザー入力"
   }]
   
   # 修正後
   system="システムプロンプト",
   messages=[{
       "role": "user",
       "content": "ユーザー入力"
   }]
   ```

6. **モデル名の統一**:
   - `claude-sonnet-4-20250514` に統一

**ポイント**:
- 参考システムと完全に同じ環境を構築
- requirements.txtにhttpx==0.27.2を明記
- 全ファイルでモデル名とsystemロールを統一

---

## 修正ファイル

- `backend/services/chat_service.py` (58-67行)
- `backend/routes/__init__.py` (22-29行, 125-132行)
- `requirements.txt` (httpx==0.27.2追加)
- `.env` (APIキー更新)

---

## 予防策

1. **依存関係のバージョン固定**: requirements.txtでバージョンを明確に指定
2. **参考システムとの同期**: API仕様変更時は参考システムを確認
3. **venv環境の明確化**: アクティベート状態を常に確認
4. **エラーメッセージの詳細記録**: 500エラー時はスタックトレースを保存

---

## 関連問題

- `2025-11-01_windows_batch_parentheses_path_error.md`（環境設定系）
- `YYYY-MM-DD_google_oauth_credentials_format.md`（認証系、今後追加予定）

---

## 学んだこと

1. **httpxバージョンがanthropicに影響**: ライブラリ間の依存関係は重要
2. **API仕様はバージョンで異なる**: systemパラメータ vs messages内systemロール
3. **環境問題は複合的**: APIキー、venv、依存関係、モデル名など複数要因
4. **参考システムの価値**: 既存の動作するシステムは最良の参考資料
5. **段階的デバッグ**: 直接APIテスト → サーバー統合テストの順で確認
