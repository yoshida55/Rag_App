"""
学習進捗管理モジュール
- 学習リストへの追加/削除
- 進捗状態管理（未学習/覚えた）
"""
import json
from pathlib import Path
from datetime import datetime
from config.settings import logger

LEARNING_FILE = Path(__file__).parent.parent / "data" / "learning_progress.json"


def _load_data() -> dict:
    """JSONファイル読み込み"""
    if not LEARNING_FILE.exists():
        return {"version": "1.0", "entries": []}
    try:
        with open(LEARNING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[LearningManager] 読み込みエラー: {e}")
        return {"version": "1.0", "entries": []}


def _save_data(data: dict):
    """JSONファイル保存"""
    try:
        with open(LEARNING_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"[LearningManager] 保存完了: {len(data.get('entries', []))}件")
    except Exception as e:
        logger.error(f"[LearningManager] 保存エラー: {e}")


def add_to_learning_list(practice_id: str, title: str, description: str, category: str) -> bool:
    """
    学習リストに追加

    Args:
        practice_id: practicesのID
        title: タイトル
        description: 説明文
        category: カテゴリ

    Returns:
        成功したらTrue
    """
    data = _load_data()

    # 重複チェック
    existing_ids = [e["practice_id"] for e in data["entries"]]
    if practice_id in existing_ids:
        logger.debug(f"[LearningManager] 既に登録済み: {practice_id}")
        return False

    entry = {
        "practice_id": practice_id,
        "title": title,
        "description": description[:500],  # 保存は500文字まで
        "category": category,
        "status": "未学習",
        "added_at": datetime.now().isoformat(),
        "learned_at": None
    }

    data["entries"].append(entry)
    _save_data(data)
    logger.info(f"[LearningManager] 追加: {title}")
    return True


def mark_as_learned(practice_id: str) -> bool:
    """覚えた状態に変更"""
    data = _load_data()

    for entry in data["entries"]:
        if entry["practice_id"] == practice_id:
            entry["status"] = "覚えた"
            entry["learned_at"] = datetime.now().isoformat()
            _save_data(data)
            logger.info(f"[LearningManager] 覚えた: {entry['title']}")
            return True

    return False


def mark_as_unlearned(practice_id: str) -> bool:
    """未学習状態に戻す"""
    data = _load_data()

    for entry in data["entries"]:
        if entry["practice_id"] == practice_id:
            entry["status"] = "未学習"
            entry["learned_at"] = None
            _save_data(data)
            logger.info(f"[LearningManager] 未学習に戻す: {entry['title']}")
            return True

    return False


def remove_from_list(practice_id: str) -> bool:
    """リストから削除"""
    data = _load_data()
    original_len = len(data["entries"])

    data["entries"] = [e for e in data["entries"] if e["practice_id"] != practice_id]

    if len(data["entries"]) < original_len:
        _save_data(data)
        logger.info(f"[LearningManager] 削除: {practice_id}")
        return True

    return False


def get_all_entries() -> list[dict]:
    """全エントリ取得"""
    data = _load_data()
    return data.get("entries", [])


def get_unlearned() -> list[dict]:
    """未学習のみ取得"""
    entries = get_all_entries()
    return [e for e in entries if e["status"] == "未学習"]


def get_learned() -> list[dict]:
    """覚えたもののみ取得"""
    entries = get_all_entries()
    return [e for e in entries if e["status"] == "覚えた"]


def get_progress_stats() -> dict:
    """進捗統計"""
    entries = get_all_entries()
    total = len(entries)
    learned = len([e for e in entries if e["status"] == "覚えた"])
    unlearned = total - learned

    return {
        "total": total,
        "learned": learned,
        "unlearned": unlearned,
        "progress_percent": round(learned / total * 100, 1) if total > 0 else 0
    }


def is_in_learning_list(practice_id: str) -> bool:
    """学習リストに含まれているかチェック"""
    entries = get_all_entries()
    return any(e["practice_id"] == practice_id for e in entries)


if __name__ == "__main__":
    # テスト
    print("=== Learning Manager Test ===")

    # テスト追加
    add_to_learning_list(
        "test-001",
        "テストタイトル",
        "テスト説明文です。これはテストです。",
        "html_css"
    )

    print(f"Stats: {get_progress_stats()}")
    print(f"Unlearned: {get_unlearned()}")
