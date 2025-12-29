# Troubleshooting - 問題解決ナレッジベース

> 🚨 **問題を記録する時は、エラー内容をできるだけ詳しく書いてください**
> - エラーメッセージ全文
> - 再現手順
> - 期待動作 vs 実際の動作
> - 原因と対処方法
> - 修正したファイルと行番号
> - 関連するキーワード（Grep検索用）

---

## 📂 ディレクトリ構造

```
Troubleshooting/
├── README.md                    ← このファイル（使い方説明）
├── update_top10.bat             ← TOP 10 更新スクリプト
└── YYYY-MM/                     ← 月別フォルダ
    └── YYYY-MM-DD_problem_description.md
```

**シンプルな構造**:
- すべての問題は**月別フォルダ**に個別ファイルで保存
- ファイル名で問題を識別
- Grep検索で即座に発見

---

## 📝 運用ルール

### 1. 問題発生時の対応

#### ステップ1: 既存の問題を検索
```bash
# キーワードでGrep検索
grep -r "キーワード" Troubleshooting/
```

#### ステップ2: 該当ファイルを読む
```bash
# 見つかったファイルを確認
cat Troubleshooting/YYYY-MM/YYYY-MM-DD_problem.md
```

#### ステップ3: 見つからない場合は新規作成
→ 次のセクション「新規問題の記録方法」へ

---

### 2. 新規問題の記録方法

#### ファイル名の付け方

**形式**: `YYYY-MM-DD_english_problem_description.md`

**良い例**:
```
✅ 2025-11-01_windows_batch_parentheses_error.md
✅ 2025-11-01_google_oauth_credentials_format.md
✅ 2025-11-01_pattern_id_extraction.md
```

**悪い例**:
```
❌ error.md                    （何のエラーか不明）
❌ fix.md                      （何を修正したか不明）
❌ 2025-11-01_bug.md          （具体性がない）
```

**ポイント**:
- 英語で記述（文字化け回避）
- 問題内容が一目でわかる
- アンダースコア `_` で単語を区切る

---

#### ファイル内容のテンプレート

```markdown
# 問題タイトル（日本語でOK）

**日付**: YYYY-MM-DD
**Keywords**: キーワード1, キーワード2, キーワード3
**Error**: "エラーメッセージ全文"
**影響範囲**: 影響を受ける機能
**重要度**: 🔴 Critical / 🟡 Important / 🟢 Minor

---

## 症状

何が起きたか、どう見えたかを詳しく記述。

**期待動作**: 〇〇であるべき
**実際の動作**: ××になった

---

## 原因

なぜ発生したか、根本原因を詳しく記述。

コード例:
\`\`\`python
# 問題のコード
bad_code_example()
\`\`\`

**根本原因**:
- 理由1
- 理由2

---

## 対処

どう修正したかを詳しく記述。

\`\`\`python
# 修正後のコード
fixed_code_example()
\`\`\`

**ポイント**:
- 修正のポイント1
- 修正のポイント2

---

## 修正ファイル

- `path/to/file.py` (行番号)
- `path/to/another_file.py` (行番号)

---

## 予防策

今後同じ問題を起こさないために。

---

## 関連問題

- 関連する問題へのリンク
- `YYYY-MM-DD_related_problem.md`

---

## 学んだこと

この問題から学んだ教訓、ベストプラクティス。
```

---

### 3. キーワードの書き方（重要！）

**ファイルの先頭に必ず記載**:
```markdown
**Keywords**: PyInstaller, sys.frozen, 相対パス, EXE, パス解決
```

**理由**:
- Grep検索で即座に発見できる
- 人間が見ても問題の概要がわかる
- Claude Codeが関連問題を見つけやすい

**良いキーワードの例**:
```
✅ 技術用語: PyInstaller, OAuth 2.0, rsplit
✅ エラー種類: 認証エラー, パス解決, 文字化け
✅ 影響範囲: Google Sheets, アップロード機能
✅ 日本語でOK: 括弧抽出, 相対パス, 自動入力
```

---

## 🔍 検索のコツ

### Grep検索の例

```bash
# エラーメッセージで検索
grep -r "FileNotFoundError" Troubleshooting/

# 技術キーワードで検索
grep -r "PyInstaller" Troubleshooting/
grep -r "OAuth" Troubleshooting/

# 日本語キーワードでも検索可能
grep -r "パス解決" Troubleshooting/
grep -r "認証エラー" Troubleshooting/

# 複数キーワード（AND検索）
grep -r "Google" Troubleshooting/ | grep "認証"
```

### ファイル名で絞り込み

```bash
# 月別で絞り込み
ls Troubleshooting/2025-11/

# 特定の問題
ls Troubleshooting/2025-11/*batch*
ls Troubleshooting/2025-11/*google*
```

---

## 💡 ベストプラクティス

### 1. 問題発生時は即座に記録

```
問題解決 → すぐ記録
↓
時間が経つと忘れる
↓
同じ問題で再度ハマる
```

### 2. 詳しく書く = 未来の自分を助ける

```
詳しい記録:
✅ エラーメッセージ全文
✅ 再現手順
✅ 試したこと（失敗含む）
✅ 最終的な解決方法
✅ なぜそれで解決したか
```

### 3. キーワードを豊富に

```
少ないキーワード → 検索で見つからない
豊富なキーワード → Grep で即発見
```

### 4. 関連問題をリンク

```
類似問題同士をリンク
↓
芋づる式に解決策が見つかる
```

---

## 📊 このシステムの利点

### トークン削減
- ✅ 必要な問題ファイルだけ読む
- ✅ 全体を読まなくていい
- ✅ Grep検索で的確に絞り込み

### 検索性向上
- ✅ ファイル名で即座に識別
- ✅ キーワードでGrep検索
- ✅ 月別で時系列追跡

### 保守性
- ✅ 問題ごとに独立したファイル
- ✅ 追加・削除が簡単
- ✅ Git管理しやすい

### 知識の蓄積
- ✅ プロジェクト固有のノウハウ
- ✅ 同じ失敗を繰り返さない
- ✅ 新メンバーへの引き継ぎ容易

---

---

## 🔄 TOP 10 自動更新（月次メンテナンス）

### 📅 実行タイミング
**月2回（15日 & 月末）に以下を Claude Code に送信**

### 📝 コピペ用コマンド

```
今月の Troubleshooting フォルダ（Troubleshooting/YYYY-MM/）の全ファイルを読んで、以下を実行してください:

【タスク】
1. 各ファイルの Keywords を集計
2. 頻出キーワード（3回以上出現）を特定
3. 同じ問題と思われるファイルをグループ化
4. README.md の「よくあるエラー TOP 10」を更新:
   - 頻度が高い問題を上位に配置
   - 既存の TOP 10 と比較して追加/削除判断
   - 新規追加する場合は適切なカテゴリに配置
5. 更新内容をレポート（追加/削除/順位変更）

【注意】
- 月別フォルダのパスは現在の年月（YYYY-MM）に変更してください
- Keywords が豊富なファイルを優先してください
- 重要度（🔴🟡🟢）も考慮してください
```

### 💡 使い方

**方法1: 直接コピペ**
```
1. 上記のコマンドをコピー
2. Claude Code に貼り付け
3. YYYY-MM を今月に変更（例: 2025-11）
4. 送信
```

**方法2: バッチファイル使用**
```
1. update_top10.bat をダブルクリック
2. 表示される指示を Claude Code にコピペ
3. 送信
```

### 📊 実行結果の例

```
✅ TOP 10 更新完了

【追加】
- #1 新しい問題（5回出現）

【順位変更】
- #3 → #2 に昇格（頻度増加）

【削除】
なし

【統計】
- 総ファイル数: 15個
- 頻出キーワード: keyword1(5), keyword2(3), keyword3(4)
```

---

## 🔥 よくあるエラー TOP 10（検索用キーワード集）

> 💡 **このセクションは月2回自動更新されます**（上記コマンド使用）

### 🔴 環境・セットアップ系
1. **問題タイトル1**
   - Keywords: `keyword1`, `keyword2`, `keyword3`
   - File: `YYYY-MM-DD_problem1.md`
   - 症状: 症状の要約
   - 対処: 対処の要約

2. **問題タイトル2**
   - Keywords: `keyword1`, `keyword2`
   - 症状: 症状の要約
   - 対処: 対処の要約

### 🟡 認証・API系
3. **問題タイトル3**
   - Keywords: `keyword1`, `keyword2`
   - 症状: 症状の要約
   - 対処: 対処の要約

---

## 📌 カテゴリ別インデックス（超高速検索用）

### 環境エラー（セットアップ関連）
```bash
grep -rE "venv|pip|環境|setup|batch|バッチ" Troubleshooting/
```

### 認証エラー（OAuth/API Key）
```bash
grep -rE "OAuth|API key|token|credentials|認証|authentication" Troubleshooting/
```

### API連携エラー（外部サービス）
```bash
grep -rE "API|rate limit|外部API" Troubleshooting/
```

### データベースエラー（SQLAlchemy/SQL）
```bash
grep -rE "database|SQL|session|DB|データベース" Troubleshooting/
```

### フロントエンドエラー（UI/JavaScript）
```bash
grep -rE "JavaScript|fetch|CORS|async|DOM|フロントエンド" Troubleshooting/
```

### データ処理エラー（文字列/正規表現）
```bash
grep -rE "regex|正規表現|encoding|文字コード|pattern" Troubleshooting/
```

### パス・ファイルエラー（Path/File）
```bash
grep -rE "path|パス|FileNotFoundError|相対パス|絶対パス|file" Troubleshooting/
```

---

## 🔍 高度な検索テクニック

### パターン1: エラーメッセージで検索
```bash
# エラーメッセージをそのままコピペ
grep -r "エラーメッセージ" Troubleshooting/
```

### パターン2: 複数キーワードAND検索
```bash
# キーワード1 かつ キーワード2
grep -r "キーワード1" Troubleshooting/ | grep "キーワード2"
```

### パターン3: 日英混在検索
```bash
# 英語 or 日本語どちらでもOK
grep -rE "english|日本語" Troubleshooting/
```

### パターン4: 時期で絞り込み
```bash
# 2025年11月の問題のみ
grep -r "キーワード" Troubleshooting/2025-11/

# 直近3ヶ月
grep -r "キーワード" Troubleshooting/2025-{09,10,11}/
```

### パターン5: 重要度で絞り込み
```bash
# クリティカルな問題のみ
grep -r "🔴 Critical" Troubleshooting/

# 重要 or クリティカル
grep -rE "🔴|🟡" Troubleshooting/
```

---

## 🎯 まとめ

**重要なのは3つだけ**:

1. **問題発生 → まず TOP 10 確認**
   ```
   README.md の「よくあるエラー TOP 10」を見る
   ↓
   該当しそうなキーワードで grep 検索
   ↓
   該当ファイル読む
   ```

2. **見つからない → カテゴリ別検索**
   ```bash
   # カテゴリ別インデックスから選択
   grep -rE "キーワード群" Troubleshooting/
   ```

3. **それでもない → 詳しく記録**
   ```
   YYYY-MM-DD_english_description.md
   + Keywords 10個以上（日英混在OK）
   + Error 全文コピペ
   + 症状・原因・対処を詳しく
   + TOP 10 に追加（頻発する場合）
   ```

---

**🔥 検索のコツ: キーワードは日本語・英語どちらでもOK！**
**🔥 迷ったら: TOP 10 → カテゴリ別 → 全文検索の順で探す！**

---

**🚨 再度強調: 問題を記録する時は、エラー内容をできるだけ詳しく書いてください！**

---

## 🚀 新PJでの最初の指示

次のPJに移動したら、Claude Code に以下をコピペしてください:

```
このPJのセットアップ確認をしてください:

1. PROJECT_MAP.md を読んで、プロジェクト構造を理解
2. .claudeignore が正しく配置されているか確認
3. Troubleshooting/README.md の内容確認
4. Troubleshooting/ のフォルダ構成確認

※また適宜、PROJECT_MAP.mdは主要ファイルを記載する箇所なので、メインファイルがかわったときなど定期的に更新してください。

完了したら、このPJの概要を簡単に教えてください。
```

### 💡 シンプル版（既存PJの場合）

```
PROJECT_MAP.md を読んで、このPJを理解してください。
```
