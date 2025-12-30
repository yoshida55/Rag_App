"""
セクションキャッシュモジュール
コード学習ページのセクション分析結果を永続化
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime
from config.settings import logger

# キャッシュファイルのパス
CACHE_FILE = Path(__file__).parent.parent / "data" / "section_cache.json"


def _load_cache() -> dict:
    """キャッシュファイルを読み込む"""
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[SectionCache] 読み込みエラー: {e}")
        return {}


def _save_cache(cache: dict):
    """キャッシュファイルに保存"""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        logger.debug(f"[SectionCache] 保存完了: {len(cache)}件")
    except Exception as e:
        logger.error(f"[SectionCache] 保存エラー: {e}")


def get_code_hash(html: str, css: str) -> str:
    """HTML+CSSのハッシュを計算"""
    return hashlib.md5((html + css).encode('utf-8')).hexdigest()


def get_cached_sections(html: str, css: str) -> list[dict] | None:
    """
    キャッシュからセクションデータを取得
    
    Args:
        html: HTMLコード
        css: CSSコード
        
    Returns:
        キャッシュがあれば list[dict]、なければ None
    """
    code_hash = get_code_hash(html, css)
    cache = _load_cache()
    
    if code_hash in cache:
        entry = cache[code_hash]
        sections = entry.get("sections", [])
        # 形式を検証
        if sections and len(sections) > 0:
            first = sections[0]
            if "html" in first and "css" in first:
                logger.info(f"[SectionCache] キャッシュヒット: {len(sections)}セクション")
                return sections
    
    return None


def save_sections_to_cache(html: str, css: str, sections: list[dict]):
    """
    セクションデータをキャッシュに保存
    
    Args:
        html: HTMLコード
        css: CSSコード
        sections: セクションデータのリスト
    """
    code_hash = get_code_hash(html, css)
    cache = _load_cache()
    
    cache[code_hash] = {
        "sections": sections,
        "created_at": datetime.now().isoformat(),
        "html_length": len(html),
        "css_length": len(css),
    }
    
    _save_cache(cache)
    logger.info(f"[SectionCache] 保存: {len(sections)}セクション (hash={code_hash[:8]}...)")


def clear_cache():
    """キャッシュをすべてクリア"""
    try:
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
            logger.info("[SectionCache] キャッシュをクリアしました")
            return True
    except Exception as e:
        logger.error(f"[SectionCache] クリアエラー: {e}")
    return False


def get_cache_stats() -> dict:
    """キャッシュの統計情報を取得"""
    cache = _load_cache()
    total_sections = sum(len(entry.get("sections", [])) for entry in cache.values())
    return {
        "entry_count": len(cache),
        "total_sections": total_sections,
        "file_exists": CACHE_FILE.exists(),
        "file_size_kb": round(CACHE_FILE.stat().st_size / 1024, 1) if CACHE_FILE.exists() else 0,
    }
