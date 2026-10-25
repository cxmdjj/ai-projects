"""管理端接口: /api/admin/*(配置热更新、运行日志、数据源、功能开关)。"""

from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.config_manager import config_manager
from app.database import get_db
from app.deps import require_admin
from app.models import User
from app.schemas import ConfigUpdateIn, DataSourceTestIn

router = APIRouter(prefix="/api/admin")


@router.post("/reload")
def reload_config(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    config_manager.reload(db)
    return {"status": "ok", "message": f"配置已重载,共 {len(config_manager.all())} 项生效"}


@router.get("/configs")
def list_configs(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    from app.models import SystemConfig

    rows = db.query(SystemConfig).order_by(SystemConfig.config_group, SystemConfig.config_key).all()
    return {
        "configs": [
            {
                "config_key": r.config_key,
                "config_value": r.config_value,
                "config_group": r.config_group,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]
    }


@router.put("/configs")
def update_config(body: ConfigUpdateIn, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    config_manager.set(db, body.key, body.value)
    return {"config_key": body.key, "config_value": config_manager.get(body.key), "status": "updated"}


@router.get("/logs")
def tail_logs(lines: int = 200, user: User = Depends(require_admin)):
    log_file = Path(settings.log_dir) / "app.log"
    if not log_file.exists():
        return {"logs": "(日志文件尚未生成)", "lines": 0}
    content = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    tail = content[-max(1, min(lines, 1000)) :]
    return {"logs": "\n".join(tail), "lines": len(tail)}


@router.get("/datasources")
def get_datasources(user: User = Depends(require_admin)):
    return {
        "current": {
            "type": config_manager.get("datasource.main.type", "sqlite"),
            "conn": config_manager.get("datasource.main.conn", "") or settings.database_url,
        },
        "database_url": settings.database_url,
    }


@router.post("/datasources/test")
def test_datasource(body: DataSourceTestIn, user: User = Depends(require_admin)):
    if body.db_type == "sqlite":
        url = body.conn if body.conn.startswith("sqlite:///") else f"sqlite:///{body.conn}"
    elif body.db_type == "mysql":
        url = body.conn
    else:
        return {"ok": False, "message": f"不支持的类型 {body.db_type}(支持 sqlite / mysql)"}
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 5} if body.db_type == "mysql" else {})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return {"ok": True, "message": "连接成功"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"连接失败: {e}"}


@router.get("/features")
def list_features(user: User = Depends(require_admin)):
    features = {k: v for k, v in config_manager.all().items() if k.startswith("feature.")}
    return {"features": features}


@router.put("/features")
def update_feature(body: ConfigUpdateIn, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not body.key.startswith("feature."):
        return {"status": "rejected", "message": "仅允许更新 feature.* 配置项"}
    if body.value.strip().lower() not in ("on", "off"):
        return {"status": "rejected", "message": "取值仅支持 on / off"}
    config_manager.set(db, body.key, body.value.strip().lower())
    return {"config_key": body.key, "config_value": config_manager.get(body.key), "status": "updated"}
