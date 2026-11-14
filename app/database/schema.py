"""
DuckDB DDL schema definitions for the AI Financial Intelligence Platform.
Defines 13 auditable, relational tables ensuring data provenance and reproducibility.
"""

DDL_STATEMENTS = [
    # 1. Companies profile
    """
    CREATE TABLE IF NOT EXISTS companies (
        company_id VARCHAR PRIMARY KEY,
        name VARCHAR NOT NULL,
        ticker VARCHAR,
        reporting_currency VARCHAR DEFAULT 'USD',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # 2. Upload records (raw file tracking)
    """
    CREATE TABLE IF NOT EXISTS uploads (
        upload_id VARCHAR PRIMARY KEY,
        company_id VARCHAR NOT NULL REFERENCES companies(company_id),
        filename VARCHAR NOT NULL,
        file_hash VARCHAR NOT NULL,
        file_size_bytes BIGINT NOT NULL,
        status VARCHAR NOT NULL DEFAULT 'pending',
        error_message VARCHAR,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # 3. Datasets logical grouping
    """
    CREATE TABLE IF NOT EXISTS datasets (
        dataset_id VARCHAR PRIMARY KEY,
        company_id VARCHAR NOT NULL REFERENCES companies(company_id),
        statement_type VARCHAR NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # 4. Dataset versions (immutable iterations)
    """
    CREATE TABLE IF NOT EXISTS dataset_versions (
        dataset_id VARCHAR NOT NULL REFERENCES datasets(dataset_id),
        version INTEGER NOT NULL,
        upload_id VARCHAR NOT NULL REFERENCES uploads(upload_id),
        status VARCHAR NOT NULL DEFAULT 'draft',
        is_active BOOLEAN DEFAULT FALSE,
        committed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (dataset_id, version)
    );
    """,

    # 5. Financial facts (atomic, normalized values alongside original reported figures & lineage)
    """
    CREATE TABLE IF NOT EXISTS financial_facts (
        fact_id VARCHAR PRIMARY KEY,
        dataset_id VARCHAR NOT NULL,
        dataset_version INTEGER NOT NULL,
        statement_type VARCHAR NOT NULL,
        canonical_item VARCHAR NOT NULL,
        period VARCHAR NOT NULL,
        period_type VARCHAR DEFAULT 'annual',
        original_label VARCHAR NOT NULL,
        original_value DOUBLE NOT NULL,
        original_unit VARCHAR DEFAULT 'ones',
        original_currency VARCHAR DEFAULT 'USD',
        normalized_value DOUBLE NOT NULL,
        normalized_currency VARCHAR DEFAULT 'USD',
        scaling_factor DOUBLE DEFAULT 1.0,
        source_file VARCHAR NOT NULL,
        source_sheet VARCHAR,
        source_row INTEGER,
        mapping_method VARCHAR DEFAULT 'fuzzy',
        mapping_confidence DOUBLE DEFAULT 1.0,
        FOREIGN KEY (dataset_id, dataset_version) REFERENCES dataset_versions(dataset_id, version),
        UNIQUE (dataset_id, dataset_version, canonical_item, period)
    );
    """,

    # 6. Line item aliases (alias dictionary for schema matching)
    """
    CREATE TABLE IF NOT EXISTS line_item_aliases (
        alias_id VARCHAR PRIMARY KEY,
        alias VARCHAR NOT NULL UNIQUE,
        canonical_item VARCHAR NOT NULL,
        statement_type VARCHAR NOT NULL,
        provenance VARCHAR DEFAULT 'curated',
        is_approved BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # 7. Mapping reviews (audit trail of human and model decisions)
    """
    CREATE TABLE IF NOT EXISTS mapping_reviews (
        review_id VARCHAR PRIMARY KEY,
        upload_id VARCHAR NOT NULL REFERENCES uploads(upload_id),
        raw_label VARCHAR NOT NULL,
        canonical_item VARCHAR,
        statement_type VARCHAR NOT NULL,
        decision VARCHAR NOT NULL, -- approve, correct, reject, unknown
        reviewer_id VARCHAR DEFAULT 'usr_local_analyst',
        reason VARCHAR,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # 8. Validation runs & findings
    """
    CREATE TABLE IF NOT EXISTS validation_runs (
        run_id VARCHAR PRIMARY KEY,
        dataset_id VARCHAR NOT NULL,
        dataset_version INTEGER NOT NULL,
        completeness_score DOUBLE NOT NULL,
        mapping_quality_score DOUBLE NOT NULL,
        accounting_consistency_score DOUBLE NOT NULL,
        anomaly_severity_score DOUBLE NOT NULL,
        overall_quality_score DOUBLE NOT NULL,
        has_hard_failures BOOLEAN DEFAULT FALSE,
        total_findings INTEGER DEFAULT 0,
        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (dataset_id, dataset_version) REFERENCES dataset_versions(dataset_id, version)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS validation_findings (
        finding_id VARCHAR PRIMARY KEY,
        run_id VARCHAR NOT NULL REFERENCES validation_runs(run_id),
        dataset_id VARCHAR NOT NULL,
        dataset_version INTEGER NOT NULL,
        rule_name VARCHAR NOT NULL,
        dimension VARCHAR NOT NULL,
        severity VARCHAR NOT NULL, -- warning, hard_failure
        line_item VARCHAR,
        period VARCHAR,
        observed_value DOUBLE,
        expected_value DOUBLE,
        tolerance DOUBLE,
        message VARCHAR NOT NULL,
        source_row INTEGER
    );
    """,

    # 9. Assumption sets (forecast & DCF parameters)
    """
    CREATE TABLE IF NOT EXISTS assumption_sets (
        assumption_set_id VARCHAR PRIMARY KEY,
        company_id VARCHAR NOT NULL REFERENCES companies(company_id),
        version INTEGER NOT NULL,
        source VARCHAR DEFAULT 'user_input',
        is_approved BOOLEAN DEFAULT TRUE,
        assumptions_json VARCHAR NOT NULL, -- JSON string
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # 10. Forecast runs
    """
    CREATE TABLE IF NOT EXISTS forecast_runs (
        forecast_id VARCHAR PRIMARY KEY,
        dataset_id VARCHAR NOT NULL,
        dataset_version INTEGER NOT NULL,
        assumption_set_id VARCHAR NOT NULL REFERENCES assumption_sets(assumption_set_id),
        model_name VARCHAR NOT NULL,
        horizon_periods INTEGER NOT NULL,
        results_json VARCHAR NOT NULL,
        backtest_metrics_json VARCHAR,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (dataset_id, dataset_version) REFERENCES dataset_versions(dataset_id, version)
    );
    """,

    # 11. Valuation & scenario runs
    """
    CREATE TABLE IF NOT EXISTS valuation_runs (
        valuation_id VARCHAR PRIMARY KEY,
        dataset_id VARCHAR NOT NULL,
        dataset_version INTEGER NOT NULL,
        forecast_id VARCHAR NOT NULL REFERENCES forecast_runs(forecast_id),
        assumption_set_id VARCHAR NOT NULL REFERENCES assumption_sets(assumption_set_id),
        wacc DOUBLE NOT NULL,
        terminal_growth_rate DOUBLE NOT NULL,
        enterprise_value DOUBLE NOT NULL,
        equity_value DOUBLE NOT NULL,
        implied_share_price DOUBLE,
        sensitivity_grid_json VARCHAR NOT NULL,
        scenarios_json VARCHAR NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (dataset_id, dataset_version) REFERENCES dataset_versions(dataset_id, version)
    );
    """,

    # 12. Workflow runs & Audit events
    """
    CREATE TABLE IF NOT EXISTS workflow_runs (
        workflow_id VARCHAR PRIMARY KEY,
        thread_id VARCHAR NOT NULL,
        operation VARCHAR NOT NULL,
        status VARCHAR NOT NULL DEFAULT 'queued',
        current_stage VARCHAR NOT NULL DEFAULT 'initial',
        warnings VARCHAR DEFAULT '[]',
        error_message VARCHAR,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_events (
        event_id VARCHAR PRIMARY KEY,
        actor_id VARCHAR NOT NULL,
        action VARCHAR NOT NULL,
        target_type VARCHAR NOT NULL,
        target_id VARCHAR NOT NULL,
        details VARCHAR DEFAULT '{}',
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # 13. Reports metadata
    """
    CREATE TABLE IF NOT EXISTS reports (
        report_id VARCHAR PRIMARY KEY,
        company_id VARCHAR NOT NULL REFERENCES companies(company_id),
        dataset_id VARCHAR NOT NULL,
        dataset_version INTEGER NOT NULL,
        forecast_id VARCHAR REFERENCES forecast_runs(forecast_id),
        valuation_id VARCHAR REFERENCES valuation_runs(valuation_id),
        report_type VARCHAR NOT NULL, -- docx, pdf
        file_path VARCHAR NOT NULL,
        generation_time_seconds DOUBLE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (dataset_id, dataset_version) REFERENCES dataset_versions(dataset_id, version)
    );
    """
]
