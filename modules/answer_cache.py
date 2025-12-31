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
from modules.drive_manager import DriveManager

# キャッシュファイルパス
CACHE_FILE = DATA_DIR / "answer_cache.json"

# 類似度閾値（85%）
SIMILARITY_THRESHOLD = 0.85


class AnswerCache:
    """回答キャッシュマネージャー"""

    def __init__(self):
        """キャッシュ初期化"""
        self.drive_manager = DriveManager()
        
        # 起動時にDriveから最新キャッシュを取得
        if not self.drive_manager.download_cache():
             logger.info("[Cache] Driveにキャッシュなし（または失敗）、ローカル優先")

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
            
            # Drive同期（アップロード）
            self.drive_manager.upload_cache()
        except Exception as e:
            logger.error(f"[Cache] 保存エラー: {e}")

    def _cosine_similarity(self, vec1: list, vec2: list) -> float:
        """コサイン類似度計算"""
        a = np.array(vec1)
        b = np.array(vec2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def find_similar(self, query: str, category: str = None, threshold: float = None) -> dict | None:
        """
        類似クエリを検索

        Args:
            query: 検索クエリ
            category: カテゴリ（オプション）
            threshold: 類似度閾値（Noneの場合はデフォルト使用）

        Returns:
            類似度閾値以上の既存回答があれば返す、なければNone
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

        # 閾値判定
        target_threshold = threshold if threshold is not None else SIMILARITY_THRESHOLD
        
        if best_match and best_score >= target_threshold:
            logger.info(f"[Cache] ヒット！類似度: {best_score:.1%} (閾値: {target_threshold}) - '{best_match['query'][:30]}...'")
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

    def invalidate_related(self, text: str, category: str = None, threshold: float = 0.60) -> int:
        """
        指定テキストと関連性の高いキャッシュを無効化

        Args:
            text: 新規登録データのテキスト（タイトル+説明+タグ）
            category: カテゴリ（指定あれば同カテゴリのみ対象）
            threshold: 無効化の類似度閾値（デフォルト60%）

        Returns:
            削除したエントリ数
        """
        if not self.cache.get("entries") or not text.strip():
            return 0

        # 新規データのテキストをembedding
        try:
            text_embedding = get_embedding(text[:2000])  # 最大2000文字
        except Exception as e:
            logger.error(f"[Cache] Embedding生成エラー: {e}")
            return 0

        # 削除対象を収集
        entries_to_keep = []
        deleted_count = 0

        for entry in self.cache["entries"]:
            # カテゴリフィルタ（指定あれば）
            if category and entry.get("category") and entry.get("category") != category:
                entries_to_keep.append(entry)
                continue

            # 類似度計算
            try:
                score = self._cosine_similarity(text_embedding, entry["embedding"])
                
                if score >= threshold:
                    # 閾値以上 → 削除対象
                    deleted_count += 1
                    logger.debug(f"[Cache] 無効化: '{entry['query'][:30]}...' (類似度: {score:.1%})")
                else:
                    entries_to_keep.append(entry)
            except Exception as e:
                # エラー時は保持
                entries_to_keep.append(entry)
                logger.warning(f"[Cache] 類似度計算エラー: {e}")

        # 更新
        if deleted_count > 0:
            self.cache["entries"] = entries_to_keep
            self._save_cache()
            logger.info(f"[Cache] 関連キャッシュ {deleted_count}件を無効化（閾値: {threshold:.0%}）")

        return deleted_count

