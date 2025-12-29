"""
回答キャッシュモジュール
- 永続キャッシュ（JSONファイル保存）
- 類似クエリマッチング（90%以上で既存回答を返す）
"""
import json
import numpy as np
from datetime import datetime
from pathlib import Path

from config.settings import DATA_DIR, logger
from .embedding import get_embedding

# キャッシュファイルパス
CACHE_FILE = DATA_DIR / "answer_cache.json"

# 類似度閾値（85%）
SIMILARITY_THRESHOLD = 0.85


class AnswerCache:
    """回答キャッシュマネージャー"""

    def __init__(self):
        """キャッシュ初期化"""
        self.cache = self._load_cache()
        logger.info(f"[Cache] 初期化完了: {len(self.cache.get('entries', []))}件のキャッシュ")

    def _load_cache(self) -> dict:
        """キャッシュファイル読み込み"""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[Cache] 読み込みエラー: {e}")
        return {"entries": []}

    def _save_cache(self):
        """キャッシュファイル保存"""
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
            logger.debug("[Cache] 保存完了")
        except Exception as e:
            logger.error(f"[Cache] 保存エラー: {e}")

    def _cosine_similarity(self, vec1: list, vec2: list) -> float:
        """コサイン類似度計算"""
        a = np.array(vec1)
        b = np.array(vec2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def find_similar(self, query: str, category: str = None) -> dict | None:
        """
        類似クエリを検索

        Args:
            query: 検索クエリ
            category: カテゴリ（オプション）

        Returns:
            類似度90%以上の既存回答があれば返す、なければNone
        """
        if not self.cache.get("entries"):
            logger.debug("[Cache] キャッシュ空")
            return None

        # クエリをembedding
        query_embedding = get_embedding(query)

        best_match = None
        best_score = 0

        for entry in self.cache["entries"]:
            # カテゴリフィルタ（指定あれば）
            if category and entry.get("category") != category:
                continue

            # 類似度計算
            score = self._cosine_similarity(query_embedding, entry["embedding"])

            if score > best_score:
                best_score = score
                best_match = entry

        if best_match and best_score >= SIMILARITY_THRESHOLD:
            logger.info(f"[Cache] ヒット！類似度: {best_score:.1%} - '{best_match['query'][:30]}...'")
            return {
                "answer": best_match["answer"],
                "original_query": best_match["query"],
                "similarity": best_score,
                "created_at": best_match.get("created_at", "")
            }

        logger.debug(f"[Cache] ミス（最高類似度: {best_score:.1%}）")
        return None

    def add(self, query: str, answer: str, category: str = None):
        """
        回答をキャッシュに追加

        Args:
            query: 検索クエリ
            answer: AI回答
            category: カテゴリ（オプション）
        """
        # 既に同じクエリがあれば更新
        query_embedding = get_embedding(query)

        for entry in self.cache["entries"]:
            score = self._cosine_similarity(query_embedding, entry["embedding"])
            if score >= 0.98:  # ほぼ同一クエリ
                entry["answer"] = answer
                entry["updated_at"] = datetime.now().isoformat()
                logger.debug(f"[Cache] 更新: '{query[:30]}...'")
                self._save_cache()
                return

        # 新規追加
        new_entry = {
            "query": query,
            "embedding": query_embedding,
            "answer": answer,
            "category": category,
            "created_at": datetime.now().isoformat()
        }
        self.cache["entries"].append(new_entry)
        self._save_cache()
        logger.info(f"[Cache] 追加: '{query[:30]}...' (総数: {len(self.cache['entries'])})")

    def clear(self):
        """キャッシュクリア"""
        self.cache = {"entries": []}
        self._save_cache()
        logger.info("[Cache] クリア完了")

    def get_stats(self) -> dict:
        """キャッシュ統計"""
        entries = self.cache.get("entries", [])
        return {
            "count": len(entries),
            "categories": list(set(e.get("category") for e in entries if e.get("category")))
        }
