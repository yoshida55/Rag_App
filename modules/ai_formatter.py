"""
AI整形モジュール
箇条書きメモをMarkdownに整形（Gemini 2.0 Flash）
"""
import json
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import GOOGLE_API_KEY, GEMINI_MODELS, logger

# Gemini API設定
genai.configure(api_key=GOOGLE_API_KEY)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def format_to_markdown(raw_text: str) -> str:
    """
    箇条書きメモをMarkdown形式に整形

    Args:
        raw_text: 整形前のテキスト（箇条書き等）

    Returns:
        整形後のMarkdownテキスト
    """
    logger.debug(f"[AI Formatter] 整形開始: {len(raw_text)}文字")

    model = genai.GenerativeModel(GEMINI_MODELS["format"])

    prompt = f"""以下のメモを、読みやすいMarkdown形式に整形してください。
- 見出し（##）を適切に使用
- 箇条書きや番号リストを活用
- 重要な部分は**太字**に
- 元の情報を省略せず、すべて含める
- 余計な説明は追加しない

メモ:
{raw_text}

整形後:"""

    try:
        response = model.generate_content(prompt)
        formatted = response.text.strip()

        # Markdownコードブロックで囲まれている場合は除去
        if formatted.startswith("```markdown"):
            formatted = formatted[11:]
        if formatted.startswith("```"):
            formatted = formatted[3:]
        if formatted.endswith("```"):
            formatted = formatted[:-3]

        logger.debug(f"[AI Formatter] 整形完了: {len(formatted)}文字")
        return formatted.strip()

    except Exception as e:
        logger.error(f"[AI Formatter] 整形エラー: {e}")
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def check_content(title: str, description: str, code: str = None) -> dict:
    """
    誤字脱字・内容確認チェック

    Args:
        title: タイトル
        description: 説明文
        code: コード（オプション）

    Returns:
        チェック結果dict
    """
    logger.debug(f"[AI Checker] チェック開始: {title[:30]}")

    model = genai.GenerativeModel(GEMINI_MODELS["check"])

    content = f"""タイトル: {title}
説明文: {description}
"""
    if code:
        content += f"コード: {code}"

    prompt = f"""以下の内容をチェックしてください。

{content}

以下の形式でJSON形式で回答してください:
{{
  "typos": [
    {{"original": "誤った文字列", "corrected": "正しい文字列"}}
  ],
  "suggestions": [
    "改善提案があれば記載"
  ],
  "code_issues": [
    "コードに問題があれば記載"
  ],
  "is_valid": true
}}

チェック結果:"""

    try:
        response = model.generate_content(prompt)
        result_text = response.text.strip()

        # JSONを抽出
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]

        result = json.loads(result_text)
        logger.debug(f"[AI Checker] チェック完了: is_valid={result.get('is_valid')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[AI Checker] JSON解析エラー: {e}")
        return {
            "typos": [],
            "suggestions": [],
            "code_issues": [],
            "is_valid": True,
            "error": "チェック結果の解析に失敗しました"
        }
    except Exception as e:
        logger.error(f"[AI Checker] チェックエラー: {e}")
        raise


if __name__ == "__main__":
    # テスト実行
    print("=== AI Formatter テスト ===")

    test_text = """・横並びにする
・gapを使う
・レスポンシブ対応
・IEは非対応"""

    formatted = format_to_markdown(test_text)
    print(f"整形結果:\n{formatted}")

    print("\n=== AI Checker テスト ===")
    check_result = check_content(
        title="Flecboxレイアウト",
        description="カードをよこならびにする",
        code=".cards { display: flex; }"
    )
    print(f"チェック結果: {json.dumps(check_result, ensure_ascii=False, indent=2)}")
