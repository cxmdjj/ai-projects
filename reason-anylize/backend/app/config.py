from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置,env 优先级: 环境变量 > .env 文件 > 默认值。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 数据库
    database_url: str = "sqlite:///./data/app.db"
    # 文件存储根目录(其下为 uploads/ exports/ workspace/)
    storage_root: str = "./storage"

    # 认证中心(mock OAuth2 授权码服务)
    auth_service_base_url: str = "http://localhost:8001"
    oauth_client_id: str = "analysis-client"
    oauth_client_secret: str = "analysis-client-secret"

    # 会话 JWT(演示默认值;生产必须通过环境变量 JWT_SECRET 覆盖)
    jwt_secret: str = "dev-secret-change-me-0123456789abcdef0123456789abcdef"
    jwt_ttl_hours: int = 24

    # 对外地址
    frontend_url: str = "http://localhost:5173"
    backend_public_url: str = "http://localhost:8000"

    # 日志
    log_dir: str = "./logs"
    log_level: str = "INFO"

    # LLM api_key 环境兜底(system_configs 中 llm.api_key 为空时使用)
    llm_api_key: str = ""


settings = Settings()
