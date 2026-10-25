"""可选真实 OCR:PaddleOCR(懒加载,体积较大,演示默认不用)。"""
from pathlib import Path

from app.services.ocr.base import OCRAdapter, OCRResult
from app.utils.errors import OcrUnavailableError


class PaddleOCRAdapter(OCRAdapter):
    _instance = None

    def _get_ocr(self):
        if PaddleOCRAdapter._instance is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as e:
                raise OcrUnavailableError(
                    "未安装 PaddleOCR,请执行: uv sync --group ocr,"
                    "或改用降级 OCR(ocr.backend: fallback + 同名 .ocr.json 预识别文本)"
                ) from e
            PaddleOCRAdapter._instance = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        return PaddleOCRAdapter._instance

    def extract_text(self, file_path: Path) -> OCRResult:
        ocr = self._get_ocr()
        result = ocr.ocr(str(file_path), cls=True)
        lines = []
        for page in result or []:
            for line in page or []:
                lines.append(line[1][0])
        text = "\n".join(lines)
        if not text.strip():
            raise OcrUnavailableError("图片识别结果为空")
        return OCRResult(text=text, engine="PaddleOCR")
