"""附件接口: 上传、解析管线、列表、下载、删除。"""

import time

from app.core import paths
from app.models import Attachment


def test_upload_parse_list_download_delete(auth_client, db, user, make_conversation):
    conv = make_conversation()
    csv_content = "商品,价格\n破壁机,299\n电饭煲,259\n"

    # 上传
    r = auth_client.post(
        "/api/attachment/upload",
        data={"conversation_id": conv.id},
        files={"file": ("测试数据.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["file_name"] == "测试数据.csv"
    aid = body["attachment_id"]

    # 等待后台解析完成
    for _ in range(50):
        att = db.get(Attachment, aid)
        db.refresh(att)
        if att.parse_status in ("parsed", "failed"):
            break
        time.sleep(0.1)
    assert att.parse_status == "parsed", "CSV 应解析成功"

    # 解析文本落盘 .parsed/
    stored = paths.STORAGE_ROOT / att.file_path
    assert stored.exists()
    parsed = stored.parent / ".parsed" / f"{aid}.txt"
    assert parsed.exists()
    assert "破壁机" in parsed.read_text(encoding="utf-8")

    # 列表
    r = auth_client.get("/api/attachment/ls", params={"conversation_id": conv.id})
    items = r.json()["attachments"]
    assert len(items) == 1
    assert items[0]["parse_status"] == "parsed"
    assert items[0]["file_size"] == len(csv_content.encode("utf-8"))

    # 下载
    r = auth_client.get("/api/attachment/get", params={"attachment_id": aid})
    assert r.status_code == 200
    assert r.content.decode("utf-8") == csv_content

    # 删除
    r = auth_client.post("/api/attachment/delete", json={"attachment_id": aid})
    assert r.status_code == 200
    db.expire_all()
    assert db.get(Attachment, aid) is None
    assert not stored.exists() and not parsed.exists()


def test_upload_rejects_unknown_conversation(auth_client):
    r = auth_client.post(
        "/api/attachment/upload",
        data={"conversation_id": 99999},
        files={"file": ("a.txt", b"x", "text/plain")},
    )
    assert r.status_code == 404


def test_cannot_access_others_attachment(auth_client, db, user):
    from app.services.attachment_service import AttachmentService

    att = AttachmentService(db).save_upload(user, _make_conv(db, user).id, "a.txt", b"x")
    # 换成另一个用户
    from app.core.auth import create_access_token
    from app.models import User

    other = db.query(User).filter(User.username == "other1").first()
    if other is None:
        other = User(external_user_id="e2", username="other1", display_name="o", role="analyst", status="active")
        db.add(other)
        db.commit()
        db.refresh(other)
    token = create_access_token(other.id, other.external_user_id, other.username, other.role)
    auth_client.cookies.set("session_token", token)
    r = auth_client.get("/api/attachment/get", params={"attachment_id": att.id})
    assert r.status_code == 404


def _make_conv(db, user):
    from app.services.conversation_service import ConversationService

    return ConversationService(db).create(user, "t")
