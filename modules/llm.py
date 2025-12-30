"""
Gemini LLM モジュール
- 検索回答・SVG図解: gemini-3-pro-preview
- 整形・HTML生成: gemini-2.5-flash
- 画像分析: gemini-2.0-flash
"""
import json
import base64
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential
from PIL import Image
import io

from config.settings import GOOGLE_API_KEY, GEMINI_MODELS, logger
from modules.usage_tracker import record_usage

# Gemini API設定
genai.configure(api_key=GOOGLE_API_KEY)


def estimate_tokens(text: str) -> int:
    """
    テキストからトークン数を概算
    日本語: 1文字≒1トークン、英語: 4文字≒1トークン
    混在想定で 1文字≒0.7トークン として計算
    """
    if not text:
        return 0
    # 日本語文字をカウント
    jp_chars = sum(1 for c in text if ord(c) > 127)
    en_chars = len(text) - jp_chars
    # 日本語は1:1、英語は4:1で計算
    return int(jp_chars + en_chars / 4)


def generate_answer_stream(question: str, contexts: list[dict]):
    """
    検索結果を元にAI回答をストリーミング生成（ジェネレータ）

    Args:
        question: ユーザーの質問
        contexts: 検索結果（practices.jsonのエントリリスト）

    Yields:
        テキストチャンク
    """
    logger.debug(f"[LLM] ストリーミング回答開始: {question[:50]}...")
    logger.debug(f"[LLM] コンテキスト数: {len(contexts)}件")

    model = genai.GenerativeModel(GEMINI_MODELS["answer"])

    # コンテキスト整形
    context_text = _format_contexts(contexts)

    prompt = f"""あなたはHTML/CSS/プログラミングの実装エキスパートです。

【絶対禁止】
- 同じ内容を2回書く
- セクションを繰り返す
- コードを2回載せる

【回答構造】
## 原因
### 1-1. なぜ起きるか
簡潔に説明

## 解決策
### 2-1. 対処法
具体的に

### 2-2. コード例
```css
/* 1回だけ */
```

【ルール】
- 各セクションは1回のみ
- 説明は十分に
- 重複は絶対NG

{context_text}

質問: {question}

回答:"""

    logger.debug(f"[LLM] プロンプト長: {len(prompt)}文字")

    try:
        response = model.generate_content(prompt, stream=True)
        total_text = ""
        for chunk in response:
            if chunk.text:
                total_text += chunk.text
                yield chunk.text

        # 使用量記録（日本語対応）
        input_tokens = estimate_tokens(prompt)
        output_tokens = estimate_tokens(total_text)
        record_usage(GEMINI_MODELS["answer"], input_tokens, output_tokens)
        logger.debug("[LLM] ストリーミング完了")

    except Exception as e:
        logger.error(f"[LLM] ストリーミングエラー: {e}")
        yield f"⚠️ エラーが発生しました: {e}"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def generate_answer(question: str, contexts: list[dict]) -> str:
    """
    検索結果を元にAI回答を生成

    Args:
        question: ユーザーの質問
        contexts: 検索結果（practices.jsonのエントリリスト）

    Returns:
        AI生成回答テキスト
    """
    logger.debug(f"[LLM] 回答生成開始: {question[:50]}...")
    logger.debug(f"[LLM] コンテキスト数: {len(contexts)}件")

    model = genai.GenerativeModel(GEMINI_MODELS["answer"])

    # コンテキスト整形
    context_text = _format_contexts(contexts)

    prompt = f"""あなたはHTML/CSS/プログラミングの実装エキスパートです。
以下の参考情報を元に、質問に対して具体的に回答してください。
コードが関係する場合は、具体的なコード例を含めてください。
回答は日本語でお願いします。

{context_text}

質問: {question}

回答:"""

    logger.debug(f"[LLM] プロンプト長: {len(prompt)}文字")

    try:
        response = model.generate_content(prompt)
        answer = response.text

        # 使用量記録（日本語対応）
        input_tokens = estimate_tokens(prompt)
        output_tokens = estimate_tokens(answer)
        record_usage(GEMINI_MODELS["answer"], input_tokens, output_tokens)

        logger.debug(f"[LLM] 回答生成完了: {len(answer)}文字")
        return answer

    except Exception as e:
        logger.error(f"[LLM] 回答生成エラー: {e}")
        raise


def _format_contexts(contexts: list[dict]) -> str:
    """コンテキストをプロンプト用にフォーマット"""
    if not contexts:
        return "（参考情報なし）"

    parts = []
    for i, ctx in enumerate(contexts, 1):
        # practiceデータまたは検索結果メタデータに対応
        if "metadata" in ctx:
            # 検索結果形式
            meta = ctx["metadata"]
            title = meta.get("title", "不明")
            content_type = meta.get("content_type", "code")
            document = ctx.get("document", "")
        else:
            # practiceデータ形式
            title = ctx.get("title", "不明")
            content_type = ctx.get("content_type", "code")
            document = ctx.get("description", "")

        part = f"""【参考{i}】{title}
タイプ: {content_type}
内容: {document}
"""
        # コード情報があれば追加
        if content_type == "code":
            if ctx.get("code_html"):
                part += f"HTML: {ctx['code_html']}\n"
            if ctx.get("code_css"):
                part += f"CSS: {ctx['code_css']}\n"
            if ctx.get("code_js"):
                part += f"JavaScript: {ctx['code_js']}\n"

        parts.append(part)

    return "\n".join(parts)


def generate_simple_response(prompt: str, use_pro: bool = False) -> str:
    """
    シンプルなプロンプトに対する応答（整形・生成用）

    Args:
        prompt: プロンプト
        use_pro: Trueならgemini-3-pro-preview、Falseならgemini-2.5-flash

    Returns:
        応答テキスト
    """
    model_key = "answer" if use_pro else "format"
    logger.debug(f"[LLM] シンプル応答開始 (model: {GEMINI_MODELS[model_key]})")

    model = genai.GenerativeModel(GEMINI_MODELS[model_key])

    try:
        response = model.generate_content(prompt)
        result = response.text

        # 使用量記録（日本語対応）
        input_tokens = estimate_tokens(prompt)
        output_tokens = estimate_tokens(result)
        record_usage(GEMINI_MODELS[model_key], input_tokens, output_tokens)

        return result
    except Exception as e:
        logger.error(f"[LLM] シンプル応答エラー: {e}")
        raise


def analyze_image(image_data: bytes, title: str = "") -> dict:
    """
    画像をAI分析して説明・タグを生成

    Args:
        image_data: 画像のバイトデータ
        title: ユーザー入力のタイトル（ヒントとして使用）

    Returns:
        {"description": "説明文", "tags": ["タグ1", ...], "keywords": "検索用キーワード"}
    """
    logger.debug(f"[LLM] 画像分析開始 (title: {title})")

    model = genai.GenerativeModel(GEMINI_MODELS["format"])  # gemini-2.5-flash

    # 画像をPILで読み込み
    try:
        image = Image.open(io.BytesIO(image_data))
    except Exception as e:
        logger.error(f"[LLM] 画像読み込みエラー: {e}")
        return {"description": "", "tags": [], "keywords": ""}

    title_hint = f"（ユーザー入力タイトル: {title}）" if title else ""

    prompt = f"""この画像を分析して、以下の情報をJSON形式で出力してください。{title_hint}

{{
    "description": "画像の内容をMarkdown形式で詳しく説明（何が写っているか、レイアウト、色、技術的な特徴など）",
    "tags": ["関連タグ1", "関連タグ2", "関連タグ3", "関連タグ4", "関連タグ5"],
    "keywords": "検索でヒットしやすいキーワードをスペース区切りで"
}}

注意:
- プログラミング・デザイン関連の画像の場合は技術的な説明を含める
- スクリーンショットの場合はUI要素やレイアウトを説明
- タグは具体的で検索しやすいものを5つ程度
- 日本語で回答
"""

    try:
        response = model.generate_content([prompt, image])
        result_text = response.text.strip()

        # JSON抽出
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]

        result = json.loads(result_text.strip())

        # 使用量記録（画像は概算で1000トークン）
        input_tokens = 1000 + estimate_tokens(prompt)
        output_tokens = estimate_tokens(result_text)
        record_usage(GEMINI_MODELS["format"], input_tokens, output_tokens)

        logger.debug(f"[LLM] 画像分析完了: {len(result.get('description', ''))}文字")
        return result

    except Exception as e:
        logger.error(f"[LLM] 画像分析エラー: {e}")
        return {"description": "", "tags": [], "keywords": ""}


def ask_code_question(question: str, code_context: str, history_text: str) -> str:
    """
    HTMLとCSSのコードに関する質問に回答する
    """
    prompt = f"""
    あなたはプロフェッショナルな「Webエンジニア兼プログラミング講師」です。
    ユーザーから提供されたHTML/CSSのコードに関する質問に、分かりやすく、かつ技術的に正確に答えてください。

    【コンテキスト（対象コード）】
    {code_context}

    【チャット履歴】
    {history_text}

    【質問】
    {question}

    【回答のルール】
    1. **専門用語を平易な言葉で**噛み砕いて解説してください（例: Flexboxは「横並びボックス」など）。
    2. HTMLの構造（親要素・子要素の関係）と、CSSによる見た目の変化（row-reverseでの順序逆転など）の違いを**明確に区別**して説明してください。「HTMLではこう書いてあるが、CSSでこう見える」という対比が重要です。
    3. 重要な部分は**太字**で強調し、箇条書きを使って読みやすくしてください。
    4. コード修正が必要な場合は、修正前後の比較や、具体的な修正コードを提示してください。
    5. 「なんとなく」ではなく「なぜそうなるのか（理屈）」を教えてあげてください。
    
    もし画像が添付されている場合は、その画像のデザイン意図も汲み取って回答してください。
    """
    try:
        model = genai.GenerativeModel(GEMINI_MODELS["answer"])
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"[LLM] コード質問応答エラー: {e}")
        return f"コードに関する質問への回答中にエラーが発生しました: {e}"


def analyze_html_css_relations(html_code: str, css_code: str) -> tuple[str, str]:
    """
    HTMLとCSSの対応関係を分析し、コメント付きのコードを返す
    """
    prompt = f"""
    あなたはWeb制作の講師です。以下のHTMLとCSSを見て、
    「どのHTML要素にどのCSSが効いているか」が初心者にも分かるように、
    コードに直接コメント（注釈）を追加してください。

    【絶対的なルール】
    1. HTMLには `<!-- .class名: ここは〇〇をする要素です -->` のように、必ずコメントを追記すること。
    2. CSSには `/* .class名: 幅を指定しています */` のように、必ずコメントを追記すること。
    3. **何もコメントを追加しないことは禁止**です。必ず何かしらの解説を入れてください。
    4. コードの構造（インデントなど）は極力変えないこと。
    5. 出力は以下のJSON形式のみ。マークダウンは不要。

    {{
        "html": "<!-- 解説コメント付きのHTML -->...",
        "css": "/* 解説コメント付きのCSS */..."
    }}

    HTML:
    {html_code}

    CSS:
    {css_code}
    """
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        result = json.loads(response.text)
        return result.get("html", html_code), result.get("css", css_code)
    except Exception as e:
        logger.error(f"[分析] エラー: {e}")
        return html_code, css_code

def extract_code_sections(html_code: str, css_code: str) -> list[dict]:
    """
    HTMLとCSSを解析し、機能ごとのセクション（ヘッダー、メイン、フッターなど）に分割して返す
    Method: Raw Text + マーカー挿入方式（JSONパースエラー回避のため確実性を重視）
    Improvement: 名前寄せロジックを追加し、HTMLとCSSの乖離を防ぐ
    """
    import re
    
    # マーカー定義
    MARKER_PREFIX = "SECTION_MARKER"
    SEPARATOR = "<<<<CSS_START>>>>"
    
    prompt = f"""
    あなたは「コード構造解析エンジン」です。
    Providing HTML and CSS, insert "marker comments" to split them into functional sections.

    【Task】
    1. Insert `<!-- {MARKER_PREFIX}: SectionName -->` at section starts in HTML.
    2. Insert `/* {MARKER_PREFIX}: SectionName */` at section starts in CSS.
    3. Output the FULL text with markers (Do not omit any code). Use `{SEPARATOR}` to separate HTML and CSS.

    【CRITICAL RULE: Consistent Naming】
    - **Use EXACTLY the same SectionName for the same feature in HTML and CSS.**
    - If you use "News" in HTML, you MUST use "News" in CSS (not "News Section").
    - Group generic setup code (html, head, body tags, resets) into "**Base**".
    - Group meaningful blocks (Header, Hero, Services, Contact, Footer).
    - **Avoid too many small sections.** Combine logic parts into main features.

    HTML:
    {html_code}

    CSS:
    {css_code}
    """
    
    try:
        model = genai.GenerativeModel(GEMINI_MODELS["answer"]) 
        response = model.generate_content(prompt)
        # logger.info(f"[セクション分割] Raw Response: {response.text[:200]}...") 
        
        text_resp = response.text.replace("```html", "").replace("```css", "").replace("```", "").strip()
        
        if SEPARATOR in text_resp:
            parts = text_resp.split(SEPARATOR)
            marked_html = parts[0].strip()
            marked_css = parts[1].strip()
        else:
            logger.warning("[セクション分割] セパレータが見つかりません。HTMLのみ処理します。")
            marked_html = text_resp
            marked_css = css_code 

        # Helper to parse sections
        def parse_marked_text(text, is_html=True):
            sections = {}
            pattern = f'<!-- {MARKER_PREFIX}: (.*?) -->' if is_html else f'/\* {MARKER_PREFIX}: (.*?) \*/'
            parts = re.split(pattern, text)
            
            if len(parts) > 1:
                # Pre-marker content
                if parts[0].strip():
                    sections["Base"] = parts[0] # Default to Base for top content
                
                for i in range(1, len(parts), 2):
                    name = parts[i].strip()
                    content = parts[i+1]
                    # Merge "General", "Document Start" etc into "Base"
                    if name.lower() in ["general", "document start", "html start", "head", "body"]:
                        name = "Base"
                    sections[name] = sections.get(name, "") + content
            else:
                sections["Base"] = text
            return sections

        html_secs = parse_marked_text(marked_html, is_html=True)
        css_secs = parse_marked_text(marked_css, is_html=False)
        
        # --- Name Normalization & Merging Logic ---
        # AI might still output "News" vs "News Section". We try to match them.
        
        final_sections_map = {} # {normalized_key: {name: display_name, html: ..., css: ...}}
        
        def normalize_key(name):
            # "Products1 Section" -> "products1"
            s = name.lower().replace(" section", "").replace(" area", "").replace(" part", "").strip()
            return s
            
        # 1. Register all HTML sections
        for name, content in html_secs.items():
            key = normalize_key(name)
            if key not in final_sections_map:
                final_sections_map[key] = {"name": name, "html": "", "css": ""}
            final_sections_map[key]["html"] += content
            # Update display name priority (Keep "News" over "base")
            if name != "Base": 
                 final_sections_map[key]["name"] = name
        
        # 2. Register/Merge CSS sections
        for name, content in css_secs.items():
            key = normalize_key(name)
            if key not in final_sections_map:
                final_sections_map[key] = {"name": name, "html": "", "css": ""}
            final_sections_map[key]["css"] += content
            # Be careful not to overwrite a good HTML name with a generic CSS name unless necessary
        
        # 3. Convert to list
        sections_list = []
        
        # Priority sort order
        priority_order = ["base", "header", "hero", "main", "footer"]
        
        sorted_keys = sorted(final_sections_map.keys(), key=lambda k: priority_order.index(k) if k in priority_order else 99)
        
        for key in sorted_keys:
            data = final_sections_map[key]
            if data["html"].strip() or data["css"].strip():
                sections_list.append(data)

        logger.info(f"[セクション分割] 解析完了: {len(sections_list)}セクション (Merged)")
        return sections_list
        
    except Exception as e:
        logger.error(f"[セクション分割] エラー: {e}")
        return [{"name": "Full Code (Fallback)", "html": html_code, "css": css_code}]


def generate_preview_svg(description: str, title: str = "") -> str:
    """
    説明文からSVG図解を生成

    Args:
        description: 説明文
        title: タイトル（ヒント用）

    Returns:
        SVGコード
    """
    logger.debug(f"[LLM] SVG生成開始: {title[:30]}...")

    # SVG生成は高品質モデル（gemini-3-pro-preview）を使用
    model = genai.GenerativeModel(GEMINI_MODELS["answer"])

    prompt = f"""説明文の内容を、わかりやすいSVG図解で表現してください。

タイトル: {title}
説明文:
{description[:1800]}

## まず内容を判断：
- 問題と解決策 → Before/After形式（左:問題、右:解決）
- 構造の説明 → 構造図形式（入れ子ボックスで構造を表現）
- 比較・違い → 左右比較形式
- 手順・流れ → 上から下へのフロー

## SVG基本設定（必須）
- viewBox="0 0 900 550"
- width="100%" （重要：スケーリング用）
- 背景: rect x="0" y="0" width="900" height="550" fill="#ffffff"
- タイトル: 上部中央、font-size="20", font-weight="bold"

## 文字サイズ（大きく読みやすく）
- タイトル: font-size="20"
- ラベル: font-size="16"
- 内容: font-size="14"
- コード: font-size="12"

## 色とスタイル
- 外枠: stroke="#2196f3" fill="none" stroke-width="3"
- ボックス: fill="#f5f5f5" stroke="#9e9e9e" stroke-width="1"
- 問題箇所: fill="#ffebee" stroke="#f44336"
- 解決箇所: fill="#e8f5e9" stroke="#4caf50"
- ハイライト: fill="#fff3e0" stroke="#ff9800"

## テキストルール
- 全テキストが重ならないように配置
- 十分な余白（最低20px間隔）
- fill="#333" font-family="sans-serif"

## 構造図の例（質問が構造を聞いている場合）:
```
┌───────────────────────────────────────────┐
│             タイトル                       │
├───────────────────────────────────────────┤
│ ┌─────────────────────────────────────┐   │
│ │ 親要素 .container                   │   │
│ │  ┌──────────┐  ┌──────────────┐    │   │
│ │  │ 子要素A  │  │ 子要素B      │    │   │
│ │  │ .item    │  │ .content     │    │   │
│ │  └──────────┘  └──────────────┘    │   │
│ └─────────────────────────────────────┘   │
│                                           │
│ CSS: display: flex; gap: 20px;           │
└───────────────────────────────────────────┘
```

SVGコードのみ出力:
"""

    try:
        response = model.generate_content(prompt)
        result = response.text.strip()

        # SVGタグを抽出
        if "<svg" in result and "</svg>" in result:
            start = result.find("<svg")
            end = result.find("</svg>") + 6
            result = result[start:end]

        # 使用量記録（日本語対応）
        input_tokens = estimate_tokens(prompt)
        output_tokens = estimate_tokens(result)
        record_usage(GEMINI_MODELS["answer"], input_tokens, output_tokens)

        logger.debug(f"[LLM] SVG生成完了: {len(result)}文字")
        return result

    except Exception as e:
        logger.error(f"[LLM] SVG生成エラー: {e}")
        return ""


def generate_preview_html(description: str, title: str = "") -> str:
    """
    説明文からHTMLプレビューを生成

    Args:
        description: 説明文
        title: タイトル（ヒント用）

    Returns:
        HTML+CSSコード
    """
    logger.debug(f"[LLM] HTML生成開始: {title[:30]}...")

    model = genai.GenerativeModel(GEMINI_MODELS["format"])

    prompt = f"""以下の説明文の内容を、実際に動くHTML+CSSで実装してください。

タイトル: {title}
説明文:
{description[:1500]}

要件:
- 完全なHTML（<!DOCTYPE html>から</html>まで）
- インラインCSSまたは<style>タグ内にCSS
- 日本語テキストを含める
- シンプルでわかりやすいデザイン
- レスポンシブ対応
- 色は見やすい配色

出力形式（コードのみ、説明不要）:
<!DOCTYPE html>
<html>
<head>
  <style>...</style>
</head>
<body>
  ...
</body>
</html>
"""

    try:
        response = model.generate_content(prompt)
        result = response.text.strip()

        # HTMLを抽出
        if "```html" in result:
            result = result.split("```html")[1].split("```")[0]
        elif "```" in result:
            result = result.split("```")[1].split("```")[0]

        # 使用量記録（日本語対応）
        input_tokens = estimate_tokens(prompt)
        output_tokens = estimate_tokens(result)
        record_usage(GEMINI_MODELS["format"], input_tokens, output_tokens)

        logger.debug(f"[LLM] HTML生成完了: {len(result)}文字")
        return result.strip()

    except Exception as e:
        logger.error(f"[LLM] HTML生成エラー: {e}")
        return ""


if __name__ == "__main__":
    # テスト実行
    print("=== LLM テスト ===")

    test_contexts = [
        {
            "title": "Flexboxカードレイアウト",
            "content_type": "code",
            "description": "カードを横並びで均等に配置する方法",
            "code_css": ".cards { display: flex; gap: 20px; }"
        }
    ]

    answer = generate_answer("カードを横に並べたい", test_contexts)
    print(f"回答:\n{answer}")
