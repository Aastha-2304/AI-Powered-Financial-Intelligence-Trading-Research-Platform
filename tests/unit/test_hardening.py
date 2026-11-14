"""
Unit Tests for Phase 10: Platform Hardening & Security Controls.
Verifies identifier isolation, tenant authorization boundaries, and secret redaction.
"""

import logging
import pytest
from app.core.security import AuthContext
from app.core.logging import SecretRedactingFormatter, get_logger


def test_auth_context_distinct_identifiers():
    """Verifies that all context IDs (user, company, dataset, workflow, thread) remain distinct."""
    ctx = AuthContext.create_default(company_id="co_apple", dataset_id="ds_10k", dataset_version=1)
    
    assert ctx.user_id == "usr_local_analyst"
    assert ctx.company_id == "co_apple"
    assert ctx.dataset_id == "ds_10k"
    assert ctx.dataset_version == 1
    assert ctx.workflow_id != ctx.thread_id
    assert ctx.workflow_id.startswith("wf_")
    assert ctx.thread_id.startswith("th_")


def test_auth_context_company_boundary_enforcement():
    """Verifies that attempting cross-tenant access triggers PermissionError."""
    ctx = AuthContext.create_default(company_id="co_microsoft")
    
    # Authorized access to self
    ctx.authorize_company_access("co_microsoft")
    
    # Prohibited access to other company
    with pytest.raises(PermissionError) as exc_info:
        ctx.authorize_company_access("co_apple")
    assert "Unauthorized company access" in str(exc_info.value)
    
    # Invalid ID
    with pytest.raises(ValueError):
        ctx.authorize_company_access("")


def test_auth_context_dataset_immutability_enforcement():
    """Verifies that locked dataset versions prevent cross-version modifications."""
    ctx = AuthContext.create_default(dataset_id="ds_annual_01", dataset_version=1)
    
    # Authorized access to matching version
    ctx.authorize_dataset_access("ds_annual_01", target_version=1)
    
    # Prohibited modification of different version
    with pytest.raises(PermissionError) as exc_info:
        ctx.authorize_dataset_access("ds_annual_01", target_version=2)
    assert "Unauthorized version access" in str(exc_info.value)
    
    # Prohibited cross-dataset access
    with pytest.raises(PermissionError):
        ctx.authorize_dataset_access("ds_quarterly_02", target_version=1)


def test_secret_redacting_formatter_scrubs_keys():
    """Verifies that sensitive Groq API keys and bearer tokens are scrubbed from log strings."""
    formatter = SecretRedactingFormatter()
    
    record1 = logging.LogRecord(
        name="test", level=logging.INFO, pathname="test.py", lineno=10,
        msg="Connecting to Groq endpoint with gsk_999aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpP12345",
        args=(), exc_info=None
    )
    formatted1 = formatter.format(record1)
    assert "gsk_999" not in formatted1
    assert "[REDACTED_SECRET]" in formatted1
    
    record2 = logging.LogRecord(
        name="test", level=logging.INFO, pathname="test.py", lineno=12,
        msg="Request authorized with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz",
        args=(), exc_info=None
    )
    formatted2 = formatter.format(record2)
    assert "Bearer eyJhb" not in formatted2
    assert "[REDACTED_SECRET]" in formatted2
