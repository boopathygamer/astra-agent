"""
Document Reader Tool
──────────────────────
A utility to extract raw text seamlessly from .txt, .pdf, and .docx files.
Used heavily by the Universal Domain personas (Advocate, Hunter, Archivist).
"""

import os
import logging
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import docx
except ImportError:
    docx = None

logger = logging.getLogger(__name__)

class DocumentReader:
    @staticmethod
    def read(file_path: str) -> str:
        """Read a file and return its textual contents."""
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            logger.error(f"Cannot read document: {file_path} does not exist.")
            return ""

        ext = path.suffix.lower()
        if ext == ".txt":
            return DocumentReader._read_txt(path)
        elif ext == ".pdf":
            return DocumentReader._read_pdf(path)
        elif ext == ".docx":
            return DocumentReader._read_docx(path)
        else:
            logger.error(f"Unsupported document type: {ext}")
            return ""

    @staticmethod
    def _read_txt(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read TXT: {e}")
            return ""

    @staticmethod
    def _read_pdf(path: Path) -> str:
        if fitz is None:
            logger.error("PyMuPDF (fitz) is not installed. Run `pip install PyMuPDF`.")
            return ""
        try:
            text = []
            with fitz.open(str(path)) as doc:
                for page in doc:
                    text.append(page.get_text())
            return "\n".join(text)
        except Exception as e:
            logger.error(f"Failed to read PDF: {e}")
            return ""

    @staticmethod
    def _read_docx(path: Path) -> str:
        if docx is None:
            logger.error("python-docx is not installed. Run `pip install python-docx`.")
            return ""
        try:
            doc = docx.Document(str(path))
            return "\n".join(paragraph.text for paragraph in doc.paragraphs)
        except Exception as e:
            logger.error(f"Failed to read DOCX: {e}")
            return ""
