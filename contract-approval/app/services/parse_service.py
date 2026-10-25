"""解析模块:文本提取(PDF/图片OCR)、字段与条款抽取、解析结果落库。"""
import json
from pathlib import Path

from app.enums import ParseStatus
from app.models import ContractParse
from app.services import extractors
from app.services.ocr import get_ocr_backend
from app.utils.errors import EmptyDocumentError, OcrUnavailableError, ParseError

MIN_TEXT_LENGTH = 10  # 全文低于该长度视为内容为空


def extract_text(attachment) -> tuple[str, list[tuple[int, str]], str]:
    """按文件类型提取全文。返回 (全文, [(页码, 页文本)], 引擎说明)。"""
    path = Path(attachment.file_path)
    if not path.exists():
        raise ParseError(f"附件文件不存在: {path},请重新下载")
    file_type = (attachment.file_type or path.suffix.lstrip(".")).lower()
    if file_type == "pdf":
        return _extract_pdf(path)
    if file_type in ("jpg", "jpeg", "png", "bmp", "tif", "tiff"):
        return _extract_image(path)
    raise ParseError(f"暂不支持的文件类型: {file_type}")


def _extract_pdf(path: Path) -> tuple[str, list[tuple[int, str]], str]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as e:
            raise ParseError(f"PDF 第 {i} 页文本提取失败: {e}") from e
        pages.append((i, text))
    full = "\n".join(t for _, t in pages)
    return full, pages, "pypdf 文本提取"


def _extract_image(path: Path) -> tuple[str, list[tuple[int, str]], str]:
    backend = get_ocr_backend()
    try:
        result = backend.extract_text(path)
    except OcrUnavailableError:
        raise
    except Exception as e:
        raise OcrUnavailableError(f"图片识别失败: {e}") from e
    text = (result.text or "").strip()
    if not text:
        raise OcrUnavailableError("图片识别结果为空")
    return text, [(1, text)], f"OCR({result.engine})"


def parse_attachment(db, task, attachment) -> tuple[ContractParse, str]:
    """解析附件并落库,返回 (解析记录, 引擎说明)。

    失败时:落 parse_status=failed/empty + parse_error 记录,再抛出异常(由工具层转 blocked)。
    """
    record = db.query(ContractParse).filter_by(task_id=task.id).first()
    if record is None:
        record = ContractParse(task_id=task.id)
        db.add(record)
    record.parse_status = ParseStatus.PENDING.value
    record.parse_error = None
    db.flush()
    try:
        full_text, pages, engine = extract_text(attachment)
        if len(full_text.strip()) < MIN_TEXT_LENGTH:
            raise EmptyDocumentError("文档内容为空或过短,无法解析")
        text = extractors.normalize_text(full_text)
        basic_info = extractors.extract_basic_info(text, pages)
        clauses = extractors.extract_clauses(text, pages)
        record.basic_info_json = json.dumps(basic_info, ensure_ascii=False)
        record.clause_info_json = json.dumps(clauses, ensure_ascii=False)
        record.source_text = text
        record.pages_json = json.dumps([{"page": p, "text": t} for p, t in pages], ensure_ascii=False)
        record.parse_status = ParseStatus.SUCCESS.value
        record.parse_error = None
        db.flush()
        return record, engine
    except EmptyDocumentError as e:
        record.parse_status = ParseStatus.EMPTY.value
        record.parse_error = str(e)
        db.flush()
        raise
    except Exception as e:
        record.parse_status = ParseStatus.FAILED.value
        record.parse_error = str(e)[:500]
        db.flush()
        if isinstance(e, (ParseError, OcrUnavailableError)):
            raise
        raise ParseError(f"解析异常: {e}") from e
