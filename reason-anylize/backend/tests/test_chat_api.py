"""会话/消息接口: 增删改查、级联删除(DB + 磁盘三目录)。"""

from pathlib import Path

from app.core import paths
from app.models import AnalysisResult, AnalysisTask, Attachment, Conversation, Message, User


def test_conversation_crud(auth_client, db, user):
    r = auth_client.post("/api/chat/create", json={"title": "我的会话"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "active"
    cid = body["conversation_id"]

    # 列表
    r = auth_client.get("/api/chat/ls")
    titles = [c["title"] for c in r.json()["conversations"]]
    assert "我的会话" in titles

    # 重命名
    r = auth_client.post("/api/chat/update", json={"conversation_id": cid, "title": "改名"})
    assert r.json()["title"] == "改名"

    # 归档
    r = auth_client.post("/api/chat/update", json={"conversation_id": cid, "status": "archived"})
    assert r.json()["status"] == "archived"
    assert any(c["conversation_id"] == cid for c in auth_client.get("/api/chat/ls").json()["conversations"])

    # 删除
    r = auth_client.post("/api/chat/delete", json={"conversation_ids": [cid]})
    assert r.json()["deleted"] == 1
    assert db.get(Conversation, cid).status == "deleted"
    # 已删除的不再出现在列表
    assert all(c["conversation_id"] != cid for c in auth_client.get("/api/chat/ls").json()["conversations"])


def test_cascade_delete_cleans_db_and_dirs(auth_client, db, user, make_conversation):
    conv = make_conversation("级联删除")
    cid = conv.id
    paths.ensure_conversation_dirs(user.id, cid)

    # 造出消息/附件/任务/结果/摘要记录与磁盘文件
    msg = Message(conversation_id=cid, role="user", message_type="text", content="hi", seq_no=1)
    db.add(msg)
    db.commit()
    att = Attachment(conversation_id=cid, message_id=msg.id, file_name="a.csv", file_path="uploads/1/1/a.csv", file_type="csv", file_size=3, parse_status="parsed")
    db.add(att)
    task = AnalysisTask(conversation_id=cid, user_id=user.id, input_text="hi", task_status="success")
    db.add(task)
    db.commit()
    db.add(AnalysisResult(task_id=task.id, conversation_id=cid, problem_definition="p"))
    db.commit()
    # 先取出 id,删除后再访问这些对象会因属性过期抛 ObjectDeletedError
    msg_id, att_id, task_id = msg.id, att.id, task.id

    uploads = paths.uploads_dir(user.id, cid)
    exports = paths.exports_dir(user.id, cid)
    workspace = paths.workspace_dir(user.id, cid)
    (uploads / "a.csv").write_text("x", encoding="utf-8")
    (exports / "r.md").write_text("x", encoding="utf-8")
    (workspace / "tmp.txt").write_text("x", encoding="utf-8")

    r = auth_client.post("/api/chat/delete", json={"conversation_ids": [cid]})
    assert r.json()["deleted"] == 1

    # DB 级联(expire_all 清空身份映射缓存,避免读到会话缓存的旧对象)
    db.expire_all()
    assert db.get(Message, msg_id) is None
    assert db.get(Attachment, att_id) is None
    assert db.get(AnalysisTask, task_id) is None
    assert db.query(AnalysisResult).filter(AnalysisResult.conversation_id == cid).count() == 0
    # 磁盘三目录
    assert not uploads.exists() and not exports.exists() and not workspace.exists()


def test_cannot_touch_others_conversation(auth_client, db, user):
    from app.services.conversation_service import ConversationService

    other = db.query(User).filter(User.username == "other1").first()
    if other is None:
        other = User(external_user_id="ext-other1", username="other1", display_name="o", role="analyst", status="active")
        db.add(other)
        db.commit()
        db.refresh(other)
    conv = ConversationService(db).create(other, "别人的会话")
    r = auth_client.get(f"/api/chat/ls/{conv.id}")
    assert r.status_code == 404
    r = auth_client.post("/api/chat/delete", json={"conversation_ids": [conv.id]})
    assert r.json()["deleted"] == 0


def test_ws_token_endpoint(auth_client, db):
    r = auth_client.post("/api/chat/ws-token")
    assert r.status_code == 200
    body = r.json()
    assert body["websocket_token"]
    assert body["expires_in"] == 60
