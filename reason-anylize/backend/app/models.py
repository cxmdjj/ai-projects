"""数据模型: 10 张系统表(需求文档第 7 节)+ 9 张演示业务表(第 12 节)。"""

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text

from app.database import Base


def now() -> datetime:
    return datetime.now()


# ============================== 系统表 ==============================


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_user_id = Column(String(128), unique=True, nullable=False)
    username = Column(String(64), unique=True, nullable=False)
    display_name = Column(String(128), nullable=False, default="")
    role = Column(String(32), nullable=False, default="analyst")  # admin / analyst
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=now)
    updated_at = Column(DateTime, nullable=False, default=now, onupdate=now)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(256), nullable=False, default="新会话")
    status = Column(String(32), nullable=False, default="active", index=True)  # active / archived / deleted
    last_message_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=now)
    updated_at = Column(DateTime, nullable=False, default=now, onupdate=now)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conv_seq", "conversation_id", "seq_no"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(32), nullable=False)  # user / assistant / tool / system
    message_type = Column(String(32), nullable=False, default="text")  # text / tool_call / tool_result
    content = Column(Text, nullable=False, default="")
    tool_name = Column(String(64), nullable=True)
    tool_status = Column(String(32), nullable=True)  # success / error(工具消息)
    seq_no = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=now)


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    file_name = Column(String(256), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(64), nullable=False, default="")
    file_size = Column(Integer, nullable=False, default=0)
    parse_status = Column(String(32), nullable=False, default="pending")  # pending / parsing / parsed / failed
    created_at = Column(DateTime, nullable=False, default=now)


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    input_text = Column(Text, nullable=False, default="")
    task_status = Column(String(32), nullable=False, default="queued")  # queued / running / success / failed / cancelled
    current_step = Column(String(128), nullable=False, default="pending")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("analysis_tasks.id"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    problem_definition = Column(Text, nullable=False, default="")
    key_metrics_json = Column(Text, nullable=False, default="[]")
    evidence_list_json = Column(Text, nullable=False, default="[]")
    conclusion_text = Column(Text, nullable=False, default="")
    missing_data_text = Column(Text, nullable=False, default="")
    next_action_text = Column(Text, nullable=False, default="[]")
    result_markdown = Column(Text, nullable=False, default="")
    result_file_path = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=now)


class ContextSummary(Base):
    __tablename__ = "context_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    start_seq_no = Column(Integer, nullable=False)
    end_seq_no = Column(Integer, nullable=False)
    summary_text = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=now)


class WebsocketToken(Base):
    __tablename__ = "websocket_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)  # 签发时未知,连接校验后回填
    token = Column(String(128), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=now)


class SystemConfig(Base):
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(128), unique=True, nullable=False)
    config_value = Column(Text, nullable=False, default="")
    config_group = Column(String(64), nullable=False, default="misc")
    updated_at = Column(DateTime, nullable=False, default=now, onupdate=now)


class TaskLog(Base):
    __tablename__ = "task_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("analysis_tasks.id"), nullable=True, index=True)  # 附件解析等系统日志无 task_id
    log_level = Column(String(16), nullable=False, default="info")  # info / warn / error
    log_type = Column(String(32), nullable=False, default="task")  # task / tool / attachment / system
    log_content = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=now)


# ============================== 演示业务表: 场景一 商品目录优化 ==============================


class Scn1Category(Base):
    __tablename__ = "scn1_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, unique=True, nullable=False)
    category_name = Column(String(128), nullable=False)
    parent_id = Column(Integer, nullable=True)
    level = Column(Integer, nullable=False)  # 1/2/3 级类目
    sort_order = Column(Integer, nullable=False, default=0)


class Scn1Product(Base):
    __tablename__ = "scn1_products"
    __table_args__ = (Index("ix_scn1_products_category", "category_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, unique=True, nullable=False)
    sku_code = Column(String(64), nullable=False)
    product_name = Column(String(256), nullable=False)
    category_id = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    cost_price = Column(Float, nullable=False)
    brand = Column(String(64), nullable=False, default="")
    shelf_status = Column(String(32), nullable=False, default="on")  # on / off
    on_shelf_date = Column(Date, nullable=True)


class Scn1SearchExposure(Base):
    __tablename__ = "scn1_search_exposures"
    __table_args__ = (Index("ix_scn1_expo_date_product", "stat_date", "product_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    stat_date = Column(Date, nullable=False)
    product_id = Column(Integer, nullable=False)
    search_keyword = Column(String(128), nullable=False, default="")
    exposure_cnt = Column(Integer, nullable=False, default=0)
    exposure_uv = Column(Integer, nullable=False, default=0)


class Scn1Click(Base):
    __tablename__ = "scn1_clicks"
    __table_args__ = (Index("ix_scn1_click_date_product", "stat_date", "product_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    stat_date = Column(Date, nullable=False)
    product_id = Column(Integer, nullable=False)
    search_keyword = Column(String(128), nullable=False, default="")
    click_cnt = Column(Integer, nullable=False, default=0)
    click_uv = Column(Integer, nullable=False, default=0)


class Scn1Conversion(Base):
    __tablename__ = "scn1_conversions"
    __table_args__ = (Index("ix_scn1_conv_date_product", "stat_date", "product_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    stat_date = Column(Date, nullable=False)
    product_id = Column(Integer, nullable=False)
    order_cnt = Column(Integer, nullable=False, default=0)
    order_uv = Column(Integer, nullable=False, default=0)
    gmv = Column(Float, nullable=False, default=0)
    refund_cnt = Column(Integer, nullable=False, default=0)


# ============================== 演示业务表: 场景二 客户行为分析 ==============================


class Scn2Customer(Base):
    __tablename__ = "scn2_customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, unique=True, nullable=False)
    city = Column(String(64), nullable=False, default="")
    age_band = Column(String(32), nullable=False, default="")  # 18-25 / 26-35 / 36-45 / 46+
    gender = Column(String(16), nullable=False, default="")
    member_level = Column(String(16), nullable=False, default="L1")  # L1 / L2 / L3 / L4
    register_date = Column(Date, nullable=True)
    channel = Column(String(32), nullable=False, default="")  # A / B / C


class Scn2VisitEvent(Base):
    __tablename__ = "scn2_visit_events"
    __table_args__ = (Index("ix_scn2_visit_time", "event_time"), Index("ix_scn2_visit_customer", "customer_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, nullable=False)
    event_time = Column(DateTime, nullable=False)
    page_type = Column(String(64), nullable=False, default="")  # home / category / product / cart / order
    channel = Column(String(32), nullable=False, default="")
    device_type = Column(String(32), nullable=False, default="")  # app / h5 / pc
    session_id = Column(String(64), nullable=False, default="")


class Scn2CartEvent(Base):
    __tablename__ = "scn2_cart_events"
    __table_args__ = (Index("ix_scn2_cart_time", "event_time"), Index("ix_scn2_cart_customer", "customer_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, nullable=False)
    event_time = Column(DateTime, nullable=False)
    product_id = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False, default=0)


class Scn2OrderEvent(Base):
    __tablename__ = "scn2_order_events"
    __table_args__ = (Index("ix_scn2_order_time", "order_time"), Index("ix_scn2_order_customer", "customer_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), unique=True, nullable=False)
    customer_id = Column(Integer, nullable=False)
    order_time = Column(DateTime, nullable=False)
    order_amount = Column(Float, nullable=False, default=0)
    order_status = Column(String(32), nullable=False, default="paid")  # paid / refunded / cancelled
    channel = Column(String(32), nullable=False, default="")
