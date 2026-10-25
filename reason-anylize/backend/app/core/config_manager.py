"""系统配置管理: 从 system_configs 表加载到内存,支持热更新(每次 LLM 请求实时读取)。"""

import threading
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import SystemConfig

DEFAULT_CONFIGS: dict[str, str] = {
    "llm.provider": ("llm", "openai-compatible"),  # openai-compatible / mock
    "llm.base_url": ("llm", "https://api.deepseek.com/v1"),
    "llm.api_key": ("llm", ""),
    "llm.model": ("llm", "deepseek-chat"),
    "llm.temperature": ("llm", "0.2"),
    "llm.max_tokens": ("llm", "4096"),
    "llm.timeout": ("llm", "120"),
    "feature.db_query": ("feature", "on"),
    "feature.file_ops": ("feature", "on"),
    "feature.text_search": ("feature", "on"),
    "feature.command_exec": ("feature", "off"),
    "feature.result_file": ("feature", "on"),
    "analysis.max_tool_rounds": ("analysis", "8"),
    "analysis.history_window": ("analysis", "20"),
    "analysis.summary_trigger_msgs": ("analysis", "30"),
    "analysis.summary_keep_recent": ("analysis", "12"),
    "analysis.attachment_excerpt_chars": ("analysis", "2000"),
    "analysis.task_timeout": ("analysis", "600"),
    "datasource.main.type": ("datasource", "sqlite"),
    "datasource.main.conn": ("datasource", ""),
    "sandbox.type": ("sandbox", "process"),  # process / docker
}


class ConfigManager:
    def __init__(self) -> None:
        self._cache: dict[str, str] = {}
        self._lock = threading.Lock()

    def ensure_defaults(self, db: Session) -> None:
        """启动时补齐默认配置(缺失才插入),然后加载到内存。"""
        existing = set(db.scalars(select(SystemConfig.config_key)).all())
        for key, (group, value) in DEFAULT_CONFIGS.items():
            if key not in existing:
                db.add(SystemConfig(config_key=key, config_value=value, config_group=group))
        db.commit()
        self.reload(db)

    def reload(self, db: Session) -> None:
        rows = db.scalars(select(SystemConfig)).all()
        with self._lock:
            self._cache = {r.config_key: r.config_value for r in rows}

    def get(self, key: str, default: str = "") -> str:
        with self._lock:
            return self._cache.get(key, default)

    def get_int(self, key: str, default: int) -> int:
        try:
            return int(self.get(key, str(default)))
        except ValueError:
            return default

    def is_on(self, key: str, default: bool = True) -> bool:
        return self.get(key, "on" if default else "off").strip().lower() in ("on", "true", "1", "yes")

    def all(self) -> dict[str, str]:
        with self._lock:
            return dict(self._cache)

    def set(self, db: Session, key: str, value: str) -> None:
        row = db.scalar(select(SystemConfig).where(SystemConfig.config_key == key))
        if row is None:
            group = key.split(".")[0] if "." in key else "misc"
            db.add(SystemConfig(config_key=key, config_value=value, config_group=group))
        else:
            row.config_value = value
            row.updated_at = datetime.now()
        db.commit()
        self.reload(db)

    def llm_api_key(self) -> str:
        """llm.api_key 为空时回退到环境变量 LLM_API_KEY。"""
        return self.get("llm.api_key", "") or settings.llm_api_key


config_manager = ConfigManager()
