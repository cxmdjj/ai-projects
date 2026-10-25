"""OCR 适配器抽象。"""
from abc import ABC, abstractmethod
from pathlib import Path


class OCRResult:
    def __init__(self, text: str, engine: str, confidence: float | None = None):
        self.text = text
        self.engine = engine
        self.confidence = confidence


class OCRAdapter(ABC):
    @abstractmethod
    def extract_text(self, file_path: Path) -> OCRResult:
        """识别图片文字,返回文本与引擎标识。"""
