"""
Gemini Embedding モジュール
テキストをベクトル化（gemini-embedding-001使用）
"""
import google.generativeai as genai
from config.settings import GOOGLE_API_KEY, GEMINI_MODELS, EMBEDDING_DIMENSIONS, logger
from modules.usage_tracker import record_usage

# Gemini API設定
genai.configure(api_key=GOOGLE_API_KEY)


def estimate_tokens(text: str) -> int:
    """テキストからトークン数を概算（日本語対応）"""
    if not text:
        return 0
    jp_chars = sum(1 for c in text if ord(c) > 127)
    en_chars = len(text) - jp_chars
    return int(jp_chars + en_chars / 4)


def get_embedding(text: str) -> list[float]:
    """
    テキストをベクトルに変換

    Args:
        text: 変換対象テキスト

    Returns:
        EMBEDDING_DIMENSIONS次元の浮動小数点リスト
    """
    logger.debug(f"[Embedding] 開始: {text[:50]}...")

    try:
        result = genai.embed_content(
            model=GEMINI_MODELS["embedding"],
            content=text,
            output_dimensionality=EMBEDDING_DIMENSIONS  # 次元数指定
        )
        embedding = result['embedding']

        # 使用量記録（Embeddingは無料だが呼び出し回数を記録）
        input_tokens = estimate_tokens(text)
        record_usage(GEMINI_MODELS["embedding"], input_tokens, 0)

        logger.debug(f"[Embedding] 完了: {len(embedding)}次元")
        return embedding

    except Exception as e:
        logger.error(f"[Embedding] エラー: {e}")
        raise


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    複数テキストを一括でベクトル化（Gemini APIのバッチ処理対応）

    Args:
        texts: テキストのリスト

    Returns:
        ベクトルのリスト
    """
    if not texts:
        return []
    
    logger.debug(f"[Embedding Batch] 開始: {len(texts)}件")

    try:
        # Gemini APIの一括embed（1回のAPI呼び出しで複数テキスト処理）
        result = genai.embed_content(
            model=GEMINI_MODELS["embedding"],
            content=texts,  # リストを直接渡す
            output_dimensionality=EMBEDDING_DIMENSIONS
        )
        
        embeddings = result['embedding']  # バッチの場合はリストが返る
        
        # 使用量記録
        total_tokens = sum(estimate_tokens(t) for t in texts)
        record_usage(GEMINI_MODELS["embedding"], total_tokens, 0)
        
        logger.debug(f"[Embedding Batch] 完了: {len(embeddings)}件（1回のAPI呼び出し）")
        return embeddings

    except Exception as e:
        logger.error(f"[Embedding Batch] エラー: {e}")
        # フォールバック: 1件ずつ処理
        logger.warning("[Embedding Batch] フォールバック: 1件ずつ処理に切り替え")
        embeddings = []
        for i, text in enumerate(texts):
            embedding = get_embedding(text)
            embeddings.append(embedding)
        return embeddings


if __name__ == "__main__":
    # テスト実行
    test_text = "Flexboxでカードを横並びに配置する方法"
    print(f"テストテキスト: {test_text}")

    embedding = get_embedding(test_text)
    print(f"ベクトル次元: {len(embedding)}")
    print(f"先頭5要素: {embedding[:5]}")
