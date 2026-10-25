from app.config import settings
from app.services.ocr.base import OCRAdapter, OCRResult
from app.services.ocr.fallback_ocr import FallbackOCRAdapter

_instance: OCRAdapter | None = None


def get_ocr_backend() -> OCRAdapter:
    """按配置返回 OCR 适配器单例。"""
    global _instance
    if _instance is None:
        backend = settings["ocr"]["backend"]
        if backend == "paddle":
            from app.services.ocr.paddle_ocr import PaddleOCRAdapter

            _instance = PaddleOCRAdapter()
        else:
            _instance = FallbackOCRAdapter()
    return _instance


__all__ = ["OCRAdapter", "OCRResult", "FallbackOCRAdapter", "get_ocr_backend"]
