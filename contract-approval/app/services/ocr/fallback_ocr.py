"""降级 OCR:读取与图片同名的 .ocr.json 预识别文本(演示用,免装重型引擎)。"""
import json
from pathlib import Path

from app.services.ocr.base import OCRAdapter, OCRResult
from app.utils.errors import OcrUnavailableError


class FallbackOCRAdapter(OCRAdapter):
    def extract_text(self, file_path: Path) -> OCRResult:
        json_path = file_path.with_suffix(".ocr.json")
        if not json_path.exists():
            raise OcrUnavailableError(
                f"未找到预识别文本 {json_path.name},且未安装 PaddleOCR"
                "(可选安装真实 OCR: uv sync --group ocr,并在 config/settings.yaml 中设 ocr.backend: paddle)"
            )
        data = json.loads(json_path.read_text(encoding="utf-8"))
        text = data.get("text", "")
        if not text:
            raise OcrUnavailableError(f"预识别文本为空: {json_path.name}")
        return OCRResult(text=text, engine=f"fallback(预识别文本 {json_path.name})")
