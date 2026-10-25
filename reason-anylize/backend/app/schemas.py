"""请求/响应模型(字段与需求文档第 9 节接口说明对应)。"""

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str = "新会话"


class ConversationUpdate(BaseModel):
    conversation_id: int
    title: str | None = None
    status: str | None = None  # active / archived


class ConversationDelete(BaseModel):
    conversation_ids: list[int]


class AttachmentDelete(BaseModel):
    attachment_id: int


class ChatMessageIn(BaseModel):
    """WS chat_message 负载。"""

    content: str
    attachment_ids: list[int] = Field(default_factory=list)


class CancelTaskIn(BaseModel):
    task_id: int


class ConfigUpdateIn(BaseModel):
    key: str
    value: str


class DataSourceTestIn(BaseModel):
    db_type: str = "sqlite"  # sqlite / mysql
    conn: str = ""
