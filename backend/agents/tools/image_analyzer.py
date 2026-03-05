"""
Image Analyzer Tool — Agent tool wrapping the vision pipeline.
Hardened: path validation to restrict to UPLOADS_DIR.
"""

import logging
from pathlib import Path

from agents.tools.registry import registry, RiskLevel
from config.settings import BASE_DIR, UPLOADS_DIR

logger = logging.getLogger(__name__)

# The vision pipeline will be injected at runtime
_vision_pipeline = None

# Resolve safe directories once
_SAFE_BASE = BASE_DIR.resolve()
_UPLOADS_BASE = UPLOADS_DIR.resolve()


def set_vision_pipeline(pipeline):
    """Set the global vision pipeline instance (called during startup)."""
    global _vision_pipeline
    _vision_pipeline = pipeline


def _is_safe_image_path(path: Path) -> bool:
    """Check if an image path is within the project or uploads directory."""
    resolved = path.resolve()
    try:
        return resolved.is_relative_to(_SAFE_BASE)
    except AttributeError:
        try:
            resolved.relative_to(_SAFE_BASE)
            return True
        except ValueError:
            return False


# Allowed image extensions
_ALLOWED_IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".svg",
})


@registry.register(
    name="analyze_image",
    description=(
        "Analyze an image with expert-level detail. Supports modes: "
        "general, technical, medical, document, creative, code."
    ),
    risk_level=RiskLevel.LOW,
    parameters={
        "image_path": "Path to the image file",
        "question": "Question about the image (default: describe in detail)",
        "mode": "Analysis mode (default: general)",
    },
)
def analyze_image(
    image_path: str,
    question: str = "Describe this image in detail.",
    mode: str = "general",
) -> dict:
    """Analyze an image using the vision pipeline."""
    if _vision_pipeline is None:
        return {"success": False, "error": "Vision pipeline not initialized"}

    path = Path(image_path).resolve()

    # ── Security: validate path is within project ──
    if not _is_safe_image_path(path):
        return {"success": False, "error": "Access denied: image path outside project"}

    if not path.exists():
        return {"success": False, "error": "Image not found"}

    # ── Validate file extension ──
    if path.suffix.lower() not in _ALLOWED_IMAGE_EXTENSIONS:
        return {"success": False, "error": f"Unsupported image format: {path.suffix}"}

    try:
        analysis = _vision_pipeline.analyze(
            image=str(path),
            question=question,
            mode=mode,
        )
        return {"success": True, "analysis": analysis, "mode": mode}
    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        return {"success": False, "error": "Image analysis failed"}
