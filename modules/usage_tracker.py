"""
API使用量トラッキングモジュール
- トークン数と料金を記録
- 月別集計
"""
import json
from datetime import datetime
from pathlib import Path
from config.settings import logger

# 使用量記録ファイル
USAGE_FILE = Path(__file__).parent.parent / "data" / "api_usage.json"

# 料金表（USD / 1M tokens）- 2025年12月時点
# https://ai.google.dev/gemini-api/docs/pricing
PRICING = {
    "gemini-3-pro-preview": {"input": 1.25, "output": 10.00},   # 2.5 Pro相当
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},        # 修正: 旧$0.075/$0.30
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-embedding-001": {"input": 0.00, "output": 0.00},    # 無料
    "text-embedding-004": {"input": 0.00, "output": 0.00},      # 無料
}

# USD→JPY換算レート（概算）
USD_TO_JPY = 150


def load_usage() -> dict:
    """使用量データを読み込み"""
    if USAGE_FILE.exists():
        try:
            with open(USAGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[Usage] 読み込みエラー: {e}")
    return {"monthly": {}, "total": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}}


def save_usage(data: dict):
    """使用量データを保存"""
    try:
        USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"[Usage] 保存エラー: {e}")


def record_usage(model: str, input_tokens: int, output_tokens: int):
    """
    API使用量を記録

    Args:
        model: モデル名
        input_tokens: 入力トークン数
        output_tokens: 出力トークン数
    """
    data = load_usage()

    # 月キー
    month_key = datetime.now().strftime("%Y-%m")

    # 料金計算
    pricing = PRICING.get(model, {"input": 0.1, "output": 0.4})  # デフォルト
    cost_usd = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

    # 月別記録
    if month_key not in data["monthly"]:
        data["monthly"][month_key] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "calls": 0,
            "by_model": {}
        }

    month_data = data["monthly"][month_key]
    month_data["input_tokens"] += input_tokens
    month_data["output_tokens"] += output_tokens
    month_data["cost_usd"] += cost_usd
    month_data["calls"] += 1

    # モデル別記録
    if model not in month_data["by_model"]:
        month_data["by_model"][model] = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0}
    month_data["by_model"][model]["input_tokens"] += input_tokens
    month_data["by_model"][model]["output_tokens"] += output_tokens
    month_data["by_model"][model]["cost_usd"] += cost_usd
    month_data["by_model"][model]["calls"] += 1

    # 累計
    data["total"]["input_tokens"] += input_tokens
    data["total"]["output_tokens"] += output_tokens
    data["total"]["cost_usd"] += cost_usd

    save_usage(data)
    logger.debug(f"[Usage] 記録: {model} in={input_tokens} out={output_tokens} ${cost_usd:.6f}")


def get_current_month_usage() -> dict:
    """今月の使用量を取得"""
    data = load_usage()
    month_key = datetime.now().strftime("%Y-%m")

    if month_key in data["monthly"]:
        usage = data["monthly"][month_key]
        usage["cost_jpy"] = usage["cost_usd"] * USD_TO_JPY
        return usage

    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "cost_jpy": 0.0,
        "calls": 0,
        "by_model": {}
    }


def get_all_usage() -> dict:
    """全使用量データを取得"""
    data = load_usage()
    data["total"]["cost_jpy"] = data["total"]["cost_usd"] * USD_TO_JPY
    return data


def reset_usage():
    """使用量をリセット"""
    save_usage({"monthly": {}, "total": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}})
    logger.info("[Usage] リセット完了")
