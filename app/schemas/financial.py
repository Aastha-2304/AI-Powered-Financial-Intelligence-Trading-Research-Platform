"""
Financial schemas: companies, uploads, datasets, facts, and canonical statements.
Preserves raw values alongside normalized values and transformation lineage.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class Company(BaseModel):
    """Company profile model."""
    company_id: str = Field(description="Unique identifier e.g. co_aapl")
    name: str = Field(description="Legal entity name")
    ticker: Optional[str] = Field(default=None, description="Stock ticker symbol")
    reporting_currency: str = Field(default="USD", description="Default reporting currency")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UploadRecord(BaseModel):
    """Raw file upload tracking."""
    upload_id: str
    company_id: str
    filename: str
    file_hash: str
    file_size_bytes: int
    status: str = Field(default="pending", description="pending, parsed, mapped, committed, failed")
    error_message: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class Dataset(BaseModel):
    """Logical dataset identity grouping versions."""
    dataset_id: str
    company_id: str
    statement_type: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DatasetVersion(BaseModel):
    """Immutable version of a dataset."""
    dataset_id: str
    version: int
    upload_id: str
    status: str = Field(default="draft", description="draft, approved, rejected")
    is_active: bool = False
    committed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FinancialFact(BaseModel):
    """
    Atomic financial statement observation.
    Stores original reported label and value next to normalized value with full lineage.
    """
    fact_id: str
    dataset_id: str
    dataset_version: int
    statement_type: str
    canonical_item: str
    period: str  # e.g. '2023', '2023-Q1'
    period_type: str = "annual"  # annual or quarterly
    
    # Original reported data
    original_label: str
    original_value: float
    original_unit: str = "ones"
    original_currency: str = "USD"
    
    # Normalized canonical data
    normalized_value: float  # base scale (e.g. ones or scaled standard)
    normalized_currency: str = "USD"
    scaling_factor: float = 1.0
    
    # Audit provenance
    source_file: str
    source_sheet: Optional[str] = None
    source_row: Optional[int] = None
    mapping_method: str = "fuzzy"  # alias, fuzzy, llm, manual
    mapping_confidence: float = 1.0


class LineItemAlias(BaseModel):
    """Alias dictionary entry for mapping raw headers to canonical items."""
    alias_id: str
    alias: str
    canonical_item: str
    statement_type: str
    provenance: str = "curated"  # curated, user_approved, llm_suggested
    is_approved: bool = True
