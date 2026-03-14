"""LLM module exports.

This package isolates all model interactions from services and domain logic.
"""

from app.llm.client import OllamaClient, OllamaClientSettings
from app.llm.contracts import (
    CoverLetterResponse,
    CvRewriteResponse,
    FactRewriteResponse,
    RequirementExtractionResponse,
    ValidationResponse,
)
from app.llm.cover_letter_helper import CoverLetterHelper
from app.llm.provider import get_ollama_client
from app.llm.extraction_helper import ExtractionHelper, OllamaJobAnalysisAdapter
from app.llm.rewrite_helper import CvRewriteHelper, TailoringRewriteHelper
from app.llm.validation_helper import ValidationHelper

__all__ = [
    "OllamaClient",
    "OllamaClientSettings",
    "RequirementExtractionResponse",
    "CvRewriteResponse",
    "FactRewriteResponse",
    "CoverLetterResponse",
    "ValidationResponse",
    "ExtractionHelper",
    "OllamaJobAnalysisAdapter",
    "CvRewriteHelper",
    "TailoringRewriteHelper",
    "CoverLetterHelper",
    "ValidationHelper",
    "get_ollama_client",
]
