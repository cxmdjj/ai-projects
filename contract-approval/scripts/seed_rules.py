"""规则种子灌入脚本(幂等 upsert)。

用法: python -m scripts.seed_rules
"""
import json
from pathlib import Path

from app.config import PROJECT_ROOT
from app.db import SessionLocal
from app.models import ReviewRule

SEED_PATH = PROJECT_ROOT / "samples" / "seeds" / "rules_seed.json"

_UPDATABLE = ("rule_name", "risk_level", "rule_status", "match_mode", "match_text", "suggestion_text", "description")


def seed_rules(seed_path: Path = SEED_PATH) -> tuple[int, int]:
    with open(seed_path, encoding="utf-8") as f:
        rules = json.load(f)
    created = updated = 0
    with SessionLocal() as db:
        for item in rules:
            item = dict(item)
            if isinstance(item.get("match_text"), (dict, list)):
                item["match_text"] = json.dumps(item["match_text"], ensure_ascii=False)
            existing = db.query(ReviewRule).filter_by(rule_code=item["rule_code"]).first()
            if existing:
                for key in _UPDATABLE:
                    if key in item:
                        setattr(existing, key, item[key])
                updated += 1
            else:
                db.add(ReviewRule(**item))
                created += 1
        db.commit()
    return created, updated


if __name__ == "__main__":
    c, u = seed_rules()
    print(f"种子规则灌入完成:新建 {c} 条,更新 {u} 条")
