"""配置加载:YAML + 环境变量覆盖。"""
import os
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "settings.yaml"

_DEFAULTS = {
    "approval": {"adapter": "mock", "mock": {"fail_write_for": []}},
    "ocr": {"backend": "fallback"},
    "db": {"url": "sqlite:///data/contract_approval.db"},
    "server": {"host": "127.0.0.1", "port": 8000},
    "llm": {"enabled": False},
}


def _merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _merge(result[k], v)
        else:
            result[k] = v
    return result


def load_settings() -> dict:
    settings = _DEFAULTS
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        settings = _merge(_DEFAULTS, loaded)
    # 环境变量覆盖(最高优先级)
    if os.environ.get("APPROVAL_ADAPTER"):
        settings["approval"]["adapter"] = os.environ["APPROVAL_ADAPTER"]
    if os.environ.get("OCR_BACKEND"):
        settings["ocr"]["backend"] = os.environ["OCR_BACKEND"]
    if os.environ.get("DB_URL"):
        settings["db"]["url"] = os.environ["DB_URL"]
    return settings


settings = load_settings()
