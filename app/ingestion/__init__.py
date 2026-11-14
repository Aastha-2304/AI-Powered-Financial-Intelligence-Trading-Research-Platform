# Ingestion package
from .file_parser import FileParser, FileParserError
from .statement_detector import StatementDetector
from .schema_matcher import SchemaMatcher
from .normalizer import FinancialNormalizer
from .alias_dictionary import CANONICAL_ALIASES

__all__ = [
    "FileParser",
    "FileParserError",
    "StatementDetector",
    "SchemaMatcher",
    "FinancialNormalizer",
    "CANONICAL_ALIASES",
]
