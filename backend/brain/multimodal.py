"""
Voice + Vision Multimodal Pipeline
───────────────────────────────────
Gives the Super Agent the ability to understand and process
multiple input modalities: images, documents, screenshots, and audio.

Components:
  📄 DocumentIntelligence — Extract text from PDFs, images, documents
  🖼️ VisionAnalyzer       — Analyze screenshots, photos, diagrams
  🎙️ VoiceProcessor       — Speech-to-text transcription
  🧠 MultimodalBrain      — Unified interface for all modalities

Dependencies (gracefully optional):
  - Pillow (PIL) for image processing
  - PyMuPDF (fitz) for PDF extraction
  - pytesseract / easyocr for OCR (falls back to LLM vision)
"""

import base64
import hashlib
import io
import json
import logging
import mimetypes
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class ExtractionResult:
    """Result from document/image processing."""
    source: str = ""
    content_type: str = ""  # text, image, pdf, audio
    extracted_text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    page_count: int = 0
    confidence: float = 0.0
    processing_ms: float = 0.0
    success: bool = True
    error: str = ""


@dataclass
class VisionResult:
    """Result from image/screenshot analysis."""
    description: str = ""
    objects_detected: List[str] = field(default_factory=list)
    text_in_image: str = ""
    analysis: str = ""
    confidence: float = 0.0


@dataclass
class MultimodalInput:
    """A unified representation of any modality input."""
    modality: str = ""  # text, image, pdf, audio, screenshot
    raw_path: str = ""
    raw_data: bytes = b""
    extracted_text: str = ""
    analysis: str = ""


# ──────────────────────────────────────────────
# Document Intelligence
# ──────────────────────────────────────────────

class DocumentIntelligence:
    """
    Extract text and structure from PDFs, documents, and text files.
    
    Supports:
      - PDF extraction (via PyMuPDF if available, else basic fallback)
      - Plain text files
      - Markdown / code files
      - CSV / JSON structured data
    """

    def __init__(self):
        # Check for optional dependencies
        self._has_pymupdf = False
        try:
            import fitz  # noqa: F401 — PyMuPDF
            self._has_pymupdf = True
        except ImportError:
            logger.info("PyMuPDF not installed — PDF extraction limited")

        self._supported_extensions = {
            ".pdf", ".txt", ".md", ".py", ".js", ".ts", ".java", ".cpp",
            ".c", ".h", ".rs", ".go", ".rb", ".css", ".html", ".xml",
            ".json", ".yaml", ".yml", ".toml", ".csv", ".log", ".sh",
            ".bat", ".ps1", ".sql", ".r", ".swift", ".kt",
        }
        logger.info("📄 DocumentIntelligence initialized")

    def extract(self, file_path: str) -> ExtractionResult:
        """Extract text content from a file."""
        start = time.time()
        path = Path(file_path)

        if not path.exists():
            return ExtractionResult(
                source=file_path, success=False,
                error=f"File not found: {file_path}"
            )

        ext = path.suffix.lower()
        result = ExtractionResult(
            source=file_path,
            content_type=ext.lstrip("."),
            metadata={"filename": path.name, "size_bytes": path.stat().st_size},
        )

        try:
            if ext == ".pdf":
                result = self._extract_pdf(path, result)
            elif ext == ".csv":
                result = self._extract_csv(path, result)
            elif ext == ".json":
                result = self._extract_json(path, result)
            elif ext in self._supported_extensions:
                result = self._extract_text(path, result)
            else:
                result.success = False
                result.error = f"Unsupported file type: {ext}"

        except Exception as e:
            result.success = False
            result.error = str(e)
            logger.error(f"Extraction failed for {file_path}: {e}")

        result.processing_ms = (time.time() - start) * 1000
        return result

    def _extract_pdf(self, path: Path, result: ExtractionResult) -> ExtractionResult:
        """Extract text from PDF."""
        if self._has_pymupdf:
            import fitz
            doc = fitz.open(str(path))
            pages = []
            for page_num, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    pages.append(f"--- Page {page_num + 1} ---\n{text}")
            doc.close()
            result.extracted_text = "\n\n".join(pages)
            result.page_count = len(pages)
            result.confidence = 0.9
        else:
            # Basic fallback — try reading as text
            try:
                with open(path, "rb") as f:
                    raw = f.read()
                # Extract printable text from PDF binary
                text_parts = []
                for chunk in raw.split(b"stream"):
                    try:
                        decoded = chunk.decode("utf-8", errors="ignore")
                        printable = "".join(
                            c for c in decoded
                            if c.isprintable() or c in "\n\t "
                        )
                        if len(printable) > 20:
                            text_parts.append(printable[:1000])
                    except Exception:
                        pass
                result.extracted_text = "\n".join(text_parts[:50])
                result.confidence = 0.4
                result.metadata["note"] = "Basic extraction — install PyMuPDF for better results"
            except Exception as e:
                result.success = False
                result.error = f"PDF extraction failed: {e}"

        return result

    def _extract_text(self, path: Path, result: ExtractionResult) -> ExtractionResult:
        """Extract text from plain text files."""
        encodings = ["utf-8", "utf-16", "latin-1", "cp1252"]
        for enc in encodings:
            try:
                with open(path, "r", encoding=enc) as f:
                    result.extracted_text = f.read()
                result.confidence = 1.0
                result.metadata["encoding"] = enc
                result.page_count = 1
                return result
            except (UnicodeDecodeError, UnicodeError):
                continue

        result.success = False
        result.error = "Could not decode file with any known encoding"
        return result

    def _extract_csv(self, path: Path, result: ExtractionResult) -> ExtractionResult:
        """Extract and summarize CSV data."""
        import csv
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            result.extracted_text = "Empty CSV file"
            return result

        headers = rows[0]
        data_rows = rows[1:]

        parts = [
            f"CSV: {len(data_rows)} rows × {len(headers)} columns",
            f"Headers: {', '.join(headers)}",
            "\nFirst 10 rows:",
        ]
        for row in data_rows[:10]:
            parts.append("  | ".join(row[:10]))

        result.extracted_text = "\n".join(parts)
        result.confidence = 1.0
        result.metadata["rows"] = len(data_rows)
        result.metadata["columns"] = len(headers)
        return result

    def _extract_json(self, path: Path, result: ExtractionResult) -> ExtractionResult:
        """Extract and summarize JSON data."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Pretty print with depth limit
        formatted = json.dumps(data, indent=2, default=str)
        if len(formatted) > 10000:
            formatted = formatted[:10000] + "\n... (truncated)"

        result.extracted_text = formatted
        result.confidence = 1.0
        result.metadata["type"] = type(data).__name__
        if isinstance(data, list):
            result.metadata["items"] = len(data)
        return result


# ──────────────────────────────────────────────
# Vision Analyzer
# ──────────────────────────────────────────────

class VisionAnalyzer:
    """
    Analyze images and screenshots using LLM vision capabilities.
    
    Supports:
      - Image description and object detection
      - Screenshot UI analysis
      - Text extraction from images (OCR via LLM)
      - Diagram and chart interpretation
    """

    def __init__(self, generate_fn: Callable):
        self.generate_fn = generate_fn
        # Check for PIL
        self._has_pil = False
        try:
            from PIL import Image  # noqa: F401
            self._has_pil = True
        except ImportError:
            logger.info("Pillow not installed — image metadata limited")

        logger.info("🖼️ VisionAnalyzer initialized")

    def analyze_image(
        self, image_path: str, analysis_type: str = "general"
    ) -> VisionResult:
        """
        Analyze an image using LLM vision.
        
        Args:
            image_path: Path to the image file
            analysis_type: 'general', 'screenshot', 'diagram', 'text', 'code'
        """
        path = Path(image_path)
        if not path.exists():
            return VisionResult(description=f"File not found: {image_path}")

        # Get image metadata
        metadata = self._get_image_metadata(path)

        # Build analysis prompt based on type
        prompt = self._build_vision_prompt(analysis_type, metadata)

        # Encode image for LLM
        image_data = self._encode_image(path)

        # Call LLM with vision
        try:
            result = self.generate_fn(
                prompt=prompt,
                system_prompt=(
                    "You are an expert image analyst. Provide detailed, "
                    "structured analysis of the image. Be specific about "
                    "what you see, including text, layout, colors, and objects."
                ),
                temperature=0.3,
                image_data=image_data,
            )
            analysis_text = getattr(result, 'answer', str(result))
        except TypeError:
            # LLM doesn't support image_data parameter
            analysis_text = self._analyze_without_vision(path, metadata, analysis_type)
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            analysis_text = f"Analysis error: {e}"

        return VisionResult(
            description=analysis_text[:500],
            analysis=analysis_text,
            confidence=0.7 if analysis_text else 0.0,
            text_in_image=self._extract_text_section(analysis_text),
        )

    def _get_image_metadata(self, path: Path) -> Dict[str, Any]:
        """Get image metadata."""
        metadata = {
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "format": path.suffix.lstrip(".").upper(),
        }

        if self._has_pil:
            try:
                from PIL import Image
                with Image.open(path) as img:
                    metadata["width"] = img.width
                    metadata["height"] = img.height
                    metadata["mode"] = img.mode
                    metadata["format"] = img.format or metadata["format"]
            except Exception:
                pass

        return metadata

    def _build_vision_prompt(
        self, analysis_type: str, metadata: Dict
    ) -> str:
        """Build analysis prompt based on type."""
        base = f"Image: {metadata.get('filename', 'unknown')} "
        dims = f"({metadata.get('width', '?')}x{metadata.get('height', '?')})"

        prompts = {
            "general": (
                f"Analyze this image ({base}{dims}):\n"
                "1. What is the main subject/content?\n"
                "2. Describe key visual elements\n"
                "3. Note any text visible in the image\n"
                "4. Overall assessment"
            ),
            "screenshot": (
                f"Analyze this screenshot ({base}{dims}):\n"
                "1. What application/website is shown?\n"
                "2. What UI elements are visible (buttons, menus, forms)?\n"
                "3. What is the user currently doing?\n"
                "4. Any errors or important status indicators?\n"
                "5. Extract ALL visible text"
            ),
            "diagram": (
                f"Analyze this diagram ({base}{dims}):\n"
                "1. What type of diagram is this?\n"
                "2. What are the main components/nodes?\n"
                "3. What are the relationships/connections?\n"
                "4. What is the overall structure/flow?\n"
                "5. Reproduce the diagram's content in text form"
            ),
            "text": (
                f"Extract ALL text from this image ({base}{dims}):\n"
                "Carefully transcribe every piece of text visible in the image. "
                "Maintain the original layout and formatting as much as possible."
            ),
            "code": (
                f"Extract code from this image ({base}{dims}):\n"
                "1. Transcribe all code visible in the image\n"
                "2. Identify the programming language\n"
                "3. Note any syntax errors or issues\n"
                "4. Format as a proper code block"
            ),
        }

        return prompts.get(analysis_type, prompts["general"])

    def _encode_image(self, path: Path) -> Optional[str]:
        """Encode image as base64 for LLM vision APIs."""
        try:
            with open(path, "rb") as f:
                data = f.read()
            mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
            encoded = base64.b64encode(data).decode("utf-8")
            return f"data:{mime};base64,{encoded}"
        except Exception as e:
            logger.error(f"Image encoding failed: {e}")
            return None

    def _analyze_without_vision(
        self, path: Path, metadata: Dict, analysis_type: str
    ) -> str:
        """Fallback analysis when LLM doesn't support vision."""
        info_parts = [
            "Image analysis (no vision API available):",
            f"  File: {metadata.get('filename', 'unknown')}",
            f"  Size: {metadata.get('size_bytes', 0)} bytes",
        ]
        if "width" in metadata:
            info_parts.append(
                f"  Dimensions: {metadata['width']}x{metadata['height']}"
            )
        info_parts.append(
            "\nNote: Install a provider with vision support (Gemini, GPT-4) "
            "for full image analysis."
        )
        return "\n".join(info_parts)

    def _extract_text_section(self, analysis: str) -> str:
        """Extract the text extraction portion from analysis."""
        # Look for text-related sections in the analysis
        text_markers = ["text:", "text visible:", "reads:", "says:",
                        "transcription:", "extracted text:"]
        for marker in text_markers:
            idx = analysis.lower().find(marker)
            if idx >= 0:
                return analysis[idx:idx + 500]
        return ""


# ──────────────────────────────────────────────
# Voice Processor
# ──────────────────────────────────────────────

class VoiceProcessor:
    """
    Speech-to-text processing using available backends.
    
    Supports:
      - Whisper API (OpenAI) for transcription
      - Google Speech-to-Text (if configured)
      - Fallback: file info only
    """

    def __init__(self):
        self._has_whisper = False
        try:
            import whisper  # noqa: F401
            self._has_whisper = True
        except ImportError:
            pass

        logger.info(f"🎙️ VoiceProcessor initialized (whisper={'yes' if self._has_whisper else 'no'})")

    def transcribe(self, audio_path: str) -> ExtractionResult:
        """Transcribe audio file to text."""
        path = Path(audio_path)
        if not path.exists():
            return ExtractionResult(
                source=audio_path, success=False,
                error=f"Audio file not found: {audio_path}",
            )

        start = time.time()
        result = ExtractionResult(
            source=audio_path,
            content_type="audio",
            metadata={
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "format": path.suffix.lstrip("."),
            },
        )

        if self._has_whisper:
            result = self._transcribe_whisper(path, result)
        else:
            result.success = False
            result.error = (
                "No speech-to-text backend available. "
                "Install 'openai-whisper' for transcription support."
            )

        result.processing_ms = (time.time() - start) * 1000
        return result

    def _transcribe_whisper(
        self, path: Path, result: ExtractionResult
    ) -> ExtractionResult:
        """Transcribe using local Whisper model."""
        try:
            import whisper
            model = whisper.load_model("base")
            output = model.transcribe(str(path))
            result.extracted_text = output.get("text", "")
            result.confidence = 0.85
            result.metadata["language"] = output.get("language", "unknown")
        except Exception as e:
            result.success = False
            result.error = f"Whisper transcription failed: {e}"
        return result


# ──────────────────────────────────────────────
# Multimodal Brain
# ──────────────────────────────────────────────

class MultimodalBrain:
    """
    Unified interface for all modality processing.
    
    Automatically detects input type and routes to the appropriate
    processor, then provides the extracted information to the LLM.
    """

    def __init__(self, generate_fn: Callable):
        self.generate_fn = generate_fn
        self.documents = DocumentIntelligence()
        self.vision = VisionAnalyzer(generate_fn)
        self.voice = VoiceProcessor()
        logger.info("🧠 MultimodalBrain initialized with all modalities")

    def process(self, file_path: str, analysis_hint: str = "") -> MultimodalInput:
        """
        Process any file through the appropriate modality pipeline.
        Auto-detects file type and extracts maximum information.
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        modality_input = MultimodalInput(raw_path=file_path)

        # Route by file type
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"):
            modality_input.modality = "image"
            analysis_type = analysis_hint or "general"
            vision_result = self.vision.analyze_image(file_path, analysis_type)
            modality_input.extracted_text = vision_result.text_in_image
            modality_input.analysis = vision_result.analysis

        elif ext == ".pdf":
            modality_input.modality = "pdf"
            doc_result = self.documents.extract(file_path)
            modality_input.extracted_text = doc_result.extracted_text
            modality_input.analysis = (
                f"PDF Document: {doc_result.page_count} pages\n"
                f"{doc_result.extracted_text[:2000]}"
            )

        elif ext in (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"):
            modality_input.modality = "audio"
            voice_result = self.voice.transcribe(file_path)
            modality_input.extracted_text = voice_result.extracted_text
            modality_input.analysis = (
                f"Audio transcription ({voice_result.metadata.get('language', 'unknown')}):\n"
                f"{voice_result.extracted_text}"
            )

        else:
            modality_input.modality = "document"
            doc_result = self.documents.extract(file_path)
            modality_input.extracted_text = doc_result.extracted_text
            modality_input.analysis = doc_result.extracted_text

        return modality_input

    def process_and_answer(
        self, file_path: str, question: str, analysis_hint: str = ""
    ) -> str:
        """
        Process a file and answer a question about it.
        Combines file understanding with LLM reasoning.
        """
        multimodal = self.process(file_path, analysis_hint)

        prompt = (
            f"I have processed a {multimodal.modality} file: {Path(file_path).name}\n\n"
            f"EXTRACTED CONTENT:\n{multimodal.analysis[:5000]}\n\n"
            f"USER QUESTION: {question}\n\n"
            f"Answer the question based on the extracted content above. "
            f"Be specific and reference details from the document."
        )

        try:
            result = self.generate_fn(
                prompt=prompt,
                system_prompt=(
                    "You are an expert document analyst. Answer questions "
                    "about documents, images, and media files based on the "
                    "extracted content provided. Be precise and thorough."
                ),
                temperature=0.4,
            )
            return getattr(result, 'answer', str(result))
        except Exception as e:
            return f"Analysis error: {e}"

    def get_stats(self) -> Dict[str, Any]:
        return {
            "document_formats": list(self.documents._supported_extensions),
            "has_pymupdf": self.documents._has_pymupdf,
            "has_pil": self.vision._has_pil,
            "has_whisper": self.voice._has_whisper,
        }
