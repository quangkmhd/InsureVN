import os
import sys
from functools import wraps

from mcp.server.fastmcp import FastMCP

from core.config import settings
from core.database import get_db_connection
from core.logger import get_logger

os.environ.setdefault("LANGFUSE_HOST", settings.LANGFUSE_HOST)

# Initialize logger for MCP (logs to stderr to avoid breaking stdio protocol)
logger = get_logger(
    "mcp-insurevn-db", stream=sys.stderr, log_file="log/mcp_database.log"
)

try:
    from langfuse import get_client, observe
except ImportError:
    get_client = None

    def observe(*args, **kwargs):
        def decorator(func):
            return func

        return decorator


# Initialize FastMCP server
mcp = FastMCP("insurevn-db")


def _rows_to_dicts(cursor) -> list[dict]:
    if not cursor.description:
        return []
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _limit(value: int, default: int = 50, maximum: int = 200) -> int:
    if value is None:
        return default
    return max(1, min(int(value), maximum))


def _like(value: str) -> str:
    return f"%{value.strip()}%"


def _placeholders(values: list[str]) -> str:
    return ", ".join("?" for _ in values)


def _truncate(value: object, maximum: int = 500) -> str:
    text = repr(value)
    if len(text) > maximum:
        return f"{text[:maximum]}..."
    return text


def _result_size(result: object) -> int | None:
    if isinstance(result, (list, tuple, set, dict, str)):
        return len(result)
    return None


def _is_empty_result(result: object) -> bool:
    return isinstance(result, (list, tuple, set, dict, str)) and len(result) == 0


def _update_current_span(
    level: str, status_message: str, metadata: dict | None = None
) -> None:
    if get_client is None:
        return

    try:
        get_client().update_current_span(
            level=level,
            status_message=status_message,
            metadata=metadata,
        )
    except Exception:
        logger.debug("Failed to update Langfuse span", exc_info=True)


def mcp_observe(name: str):
    """Trace MCP tools and return structured JSON on failure so the agent has full context."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            metadata = {
                "tool_name": name,
                "tool_args": _truncate(args),
                "tool_kwargs": _truncate(kwargs),
            }
            logger.info(f"MCP tool started: {name}", extra=metadata)

            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                # Create a detailed error object
                error_payload = {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "tool": name,
                    "suggestion": "Check your SQL syntax or arguments and try again.",
                }
                log_payload = {
                    **metadata,
                    **error_payload,
                    "error_message": error_payload["message"],
                }
                log_payload.pop("message", None)

                # Log the error for production monitoring
                logger.error(
                    f"MCP tool failed: {name}",
                    extra=log_payload,
                    exc_info=True,
                )

                # Update Langfuse span
                _update_current_span(
                    level="ERROR",
                    status_message=f"{type(exc).__name__}: {exc}",
                    metadata={**metadata, **error_payload},
                )

                # IMPORTANT: Return JSON string instead of raising.
                import json

                return json.dumps(error_payload, ensure_ascii=False)

            size = _result_size(result)
            completion_data = {**metadata, "result_size": size}

            if _is_empty_result(result):
                logger.warning(
                    f"MCP tool returned no results: {name}", extra=completion_data
                )
                _update_current_span(
                    level="WARNING",
                    status_message="MCP tool returned no results",
                    metadata={**completion_data, "result_empty": True},
                )
                return []
            logger.info(f"MCP tool completed: {name}", extra=completion_data)

            return result

        return observe(name=name)(wrapper)

    return decorator


@mcp.tool()
@mcp_observe(name="list-tables")
def list_tables() -> list[str]:
    """Return a list of all tables in the insurevn.db database."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        rows = cursor.fetchall()
        return [row["name"] for row in rows]


@mcp.tool()
@mcp_observe(name="get-schema")
def get_schema(table_names: list[str]) -> list[str]:
    """Return the DDL CREATE TABLE statements for the requested tables."""
    schemas = []
    with get_db_connection() as conn:
        for table in table_names:
            cursor = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (table,)
            )
            row = cursor.fetchone()
            if row and row["sql"]:
                schemas.append(row["sql"])
            else:
                schemas.append(f"-- Schema not found for table: {table}")
    return schemas


@mcp.tool()
@mcp_observe(name="execute-query")
def execute_query(query: str) -> list[dict]:
    """Execute a read-only SQL query against the database and return results as a list of dictionaries."""
    query_upper = query.strip().upper()
    # Basic security check for read-only operations
    if not any(
        query_upper.startswith(prefix)
        for prefix in ["SELECT", "WITH", "EXPLAIN QUERY PLAN"]
    ):
        raise ValueError("Security Error: Only SELECT queries are allowed.")

    with get_db_connection(read_only=True) as conn:
        cursor = conn.execute(query)
        rows = cursor.fetchall()

        if cursor.description:
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        return []


@mcp.tool()
@mcp_observe(name="database-summary")
def database_summary() -> list[dict]:
    """Return row counts for the main insurance-domain tables."""
    query = """
    SELECT 'companies' AS table_name, COUNT(*) AS row_count FROM companies
    UNION ALL SELECT 'documents', COUNT(*) FROM documents
    UNION ALL SELECT 'plan_types', COUNT(*) FROM plan_types
    UNION ALL SELECT 'benefit_items', COUNT(*) FROM benefit_items
    UNION ALL SELECT 'benefit_values', COUNT(*) FROM benefit_values
    UNION ALL SELECT 'premium_entries', COUNT(*) FROM premium_entries
    UNION ALL SELECT 'hospitals', COUNT(*) FROM hospitals
    UNION ALL SELECT 'glossary_terms', COUNT(*) FROM glossary_terms
    UNION ALL SELECT 'waiting_periods', COUNT(*) FROM waiting_periods
    UNION ALL SELECT 'claim_payouts', COUNT(*) FROM claim_payouts
    UNION ALL SELECT 'short_term_premiums', COUNT(*) FROM short_term_premiums
    """
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query))


@mcp.tool()
@mcp_observe(name="list-companies")
def list_companies() -> list[dict]:
    """Return insurers available in the database with document and plan counts."""
    query = """
    SELECT
        c.code,
        c.name,
        c.website,
        COUNT(DISTINCT d.id) AS document_count,
        COUNT(DISTINCT pt.id) AS plan_count
    FROM companies c
    LEFT JOIN documents d ON d.company_id = c.id
    LEFT JOIN plan_types pt ON pt.company_id = c.id
    GROUP BY c.id
    ORDER BY c.code
    """
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query))


@mcp.tool()
@mcp_observe(name="list-documents")
def list_documents(
    company_code: str | None = None,
    document_type: str | None = None,
    keyword: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Return source PDF documents with optional insurer, document type, and keyword filters."""
    params = []
    where = []
    if company_code:
        where.append("c.code = ?")
        params.append(company_code)
    if document_type:
        where.append("d.document_type = ?")
        params.append(document_type)
    if keyword:
        where.append(
            "(d.document_name LIKE ? OR d.source_path LIKE ? OR d.description LIKE ?)"
        )
        params.extend([_like(keyword), _like(keyword), _like(keyword)])

    query = f"""
    SELECT
        d.id AS document_id,
        c.code AS company_code,
        c.name AS company_name,
        d.source_path,
        d.document_name,
        d.document_type,
        d.language,
        d.description,
        d.effective_date,
        d.version,
        COUNT(DISTINCT st.id) AS source_table_count,
        COUNT(DISTINCT pt.id) AS plan_count
    FROM documents d
    JOIN companies c ON c.id = d.company_id
    LEFT JOIN source_tables st ON st.document_id = d.id
    LEFT JOIN plan_types pt ON pt.document_id = d.id
    {"WHERE " + " AND ".join(where) if where else ""}
    GROUP BY d.id
    ORDER BY c.code, d.document_name
    LIMIT ?
    """
    params.append(_limit(limit, default=100))
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query, params))


@mcp.tool()
@mcp_observe(name="list-source-tables")
def list_source_tables(
    company_code: str | None = None,
    document_id: int | None = None,
    table_type: str | None = None,
    processed: bool | None = None,
    limit: int = 100,
) -> list[dict]:
    """Return extracted JSON table metadata without raw_json payload."""
    params = []
    where = []
    if company_code:
        where.append("c.code = ?")
        params.append(company_code)
    if document_id is not None:
        where.append("d.id = ?")
        params.append(document_id)
    if table_type:
        where.append("st.table_type = ?")
        params.append(table_type)
    if processed is not None:
        where.append("st.processed = ?")
        params.append(1 if processed else 0)

    query = f"""
    SELECT
        st.id AS source_table_id,
        d.id AS document_id,
        c.code AS company_code,
        c.name AS company_name,
        d.document_name,
        st.file_path,
        st.table_type,
        st.classification_reason,
        st.classification_confidence,
        st.page_number,
        st.table_index,
        st.keys,
        st.content_type,
        st.processed,
        st.error_reason
    FROM source_tables st
    JOIN documents d ON d.id = st.document_id
    JOIN companies c ON c.id = d.company_id
    {"WHERE " + " AND ".join(where) if where else ""}
    ORDER BY c.code, d.document_name, st.page_number, st.table_index
    LIMIT ?
    """
    params.append(_limit(limit, default=100))
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query, params))


@mcp.tool()
@mcp_observe(name="list-benefit-categories")
def list_benefit_categories() -> list[dict]:
    """Return benefit category taxonomy."""
    query = """
    SELECT
        bc.id AS category_id,
        bc.code,
        bc.name_vi,
        bc.name_en,
        parent.code AS parent_code,
        parent.name_vi AS parent_name_vi
    FROM benefit_categories bc
    LEFT JOIN benefit_categories parent ON parent.id = bc.parent_id
    ORDER BY COALESCE(parent.code, bc.code), bc.code
    """
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query))


@mcp.tool()
@mcp_observe(name="search-plans")
def search_plans(
    keyword: str | None = None,
    company_code: str | None = None,
    normalized_code: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Search plan aliases/raw names and normalized plan codes."""
    params = []
    where = []
    if keyword:
        where.append(
            "(pt.raw_name LIKE ? OR pt.normalized_code LIKE ? OR pt.product_line LIKE ?)"
        )
        params.extend([_like(keyword), _like(keyword), _like(keyword)])
    if company_code:
        where.append("c.code = ?")
        params.append(company_code)
    if normalized_code:
        where.append("pt.normalized_code = ?")
        params.append(normalized_code)

    query = f"""
    SELECT
        pt.id AS plan_type_id,
        c.code AS company_code,
        c.name AS company_name,
        d.id AS document_id,
        d.document_name,
        pt.raw_name AS plan_name,
        pt.normalized_code AS plan_code,
        pt.plan_level,
        pt.product_line
    FROM plan_types pt
    LEFT JOIN companies c ON c.id = pt.company_id
    LEFT JOIN documents d ON d.id = pt.document_id
    {"WHERE " + " AND ".join(where) if where else ""}
    ORDER BY c.code, pt.product_line, pt.plan_level, pt.raw_name
    LIMIT ?
    """
    params.append(_limit(limit, default=100))
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query, params))


@mcp.tool()
@mcp_observe(name="list-plans")
def list_plans(company_code: str | None = None, limit: int = 100) -> list[dict]:
    """Return plan types, optionally filtered by insurer code."""
    params = []
    where = []
    if company_code:
        where.append("c.code = ?")
        params.append(company_code)

    query = f"""
    SELECT
        c.code AS company_code,
        c.name AS company_name,
        d.id AS document_id,
        d.document_name,
        pt.raw_name AS plan_name,
        pt.normalized_code AS plan_code,
        pt.plan_level,
        pt.product_line
    FROM plan_types pt
    LEFT JOIN companies c ON c.id = pt.company_id
    LEFT JOIN documents d ON d.id = pt.document_id
    {"WHERE " + " AND ".join(where) if where else ""}
    ORDER BY c.code, pt.product_line, pt.plan_level, pt.raw_name
    LIMIT ?
    """
    params.append(_limit(limit, default=100))
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query, params))


@mcp.tool()
@mcp_observe(name="get-premium-quotes")
def get_premium_quotes(
    age: int | None = None,
    company_code: str | None = None,
    plan_code: str | None = None,
    max_premium: float | None = None,
    limit: int = 50,
) -> list[dict]:
    """Find annual premium rows by age, insurer, plan code, and optional maximum premium."""
    params = []
    where = []
    if age is not None:
        where.append("? BETWEEN pe.age_min AND pe.age_max")
        params.append(age)
    if company_code:
        where.append("c.code = ?")
        params.append(company_code)
    if plan_code:
        where.append("pt.normalized_code = ?")
        params.append(plan_code)
    if max_premium is not None:
        where.append("pe.premium_amount <= ?")
        params.append(max_premium)

    query = f"""
    SELECT
        pe.source_table_id,
        d.id AS document_id,
        st.file_path AS source_file_path,
        c.code AS company_code,
        c.name AS company_name,
        d.document_name,
        pt.raw_name AS plan_name,
        pt.normalized_code AS plan_code,
        pe.age_label,
        pe.age_min,
        pe.age_max,
        pe.premium_amount,
        pe.currency,
        pe.period,
        pe.year_label
    FROM premium_entries pe
    JOIN documents d ON d.id = pe.document_id
    JOIN companies c ON c.id = d.company_id
    JOIN source_tables st ON st.id = pe.source_table_id
    LEFT JOIN plan_types pt ON pt.id = pe.plan_type_id
    {"WHERE " + " AND ".join(where) if where else ""}
    ORDER BY pe.premium_amount, c.code, pt.plan_level
    LIMIT ?
    """
    params.append(_limit(limit))
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query, params))


@mcp.tool()
@mcp_observe(name="search-benefits")
def search_benefits(
    keyword: str,
    company_code: str | None = None,
    plan_code: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Search benefit names, notes, and values by keyword, with optional insurer and plan filters."""
    params = [_like(keyword), _like(keyword), _like(keyword)]
    where = ["(bi.raw_name LIKE ? OR bi.note LIKE ? OR bv.value LIKE ?)"]
    if company_code:
        where.append("c.code = ?")
        params.append(company_code)
    if plan_code:
        where.append("pt.normalized_code = ?")
        params.append(plan_code)

    query = f"""
    SELECT
        bi.source_table_id,
        d.id AS document_id,
        st.file_path AS source_file_path,
        c.code AS company_code,
        c.name AS company_name,
        d.document_name,
        bi.raw_name AS benefit_name,
        bi.applicable_to,
        bi.note AS benefit_note,
        pt.raw_name AS plan_name,
        pt.normalized_code AS plan_code,
        bv.value,
        bv.value_numeric,
        bv.value_context,
        bv.unit,
        bv.limit_type,
        bv.is_covered,
        bv.note AS value_note
    FROM benefit_items bi
    JOIN documents d ON d.id = bi.document_id
    JOIN companies c ON c.id = d.company_id
    JOIN source_tables st ON st.id = bi.source_table_id
    LEFT JOIN benefit_values bv ON bv.benefit_item_id = bi.id
    LEFT JOIN plan_types pt ON pt.id = bv.plan_type_id
    WHERE {" AND ".join(where)}
    ORDER BY c.code, d.document_name, bi.display_order, pt.plan_level
    LIMIT ?
    """
    params.append(_limit(limit))
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query, params))


@mcp.tool()
@mcp_observe(name="search-hospitals")
def search_hospitals(
    keyword: str | None = None,
    city: str | None = None,
    country: str | None = None,
    company_code: str | None = None,
    gop_supported: bool | None = None,
    limit: int = 50,
) -> list[dict]:
    """Search hospital/network entries by name, address, city, country, insurer, and GOP support."""
    params = []
    where = []
    if keyword:
        where.append(
            "(h.name_vi LIKE ? OR h.name_en LIKE ? OR h.address LIKE ? OR h.note LIKE ?)"
        )
        params.extend([_like(keyword), _like(keyword), _like(keyword), _like(keyword)])
    if city:
        where.append("h.city LIKE ?")
        params.append(_like(city))
    if country:
        where.append("h.country LIKE ?")
        params.append(_like(country))
    if company_code:
        where.append("c.code = ?")
        params.append(company_code)
    if gop_supported is not None:
        where.append("h.gop_supported = ?")
        params.append(1 if gop_supported else 0)

    query = f"""
    SELECT
        h.source_table_id,
        d.id AS document_id,
        st.file_path AS source_file_path,
        c.code AS company_code,
        c.name AS company_name,
        d.document_name,
        h.name_vi,
        h.name_en,
        h.address,
        h.city,
        h.country,
        h.phone,
        h.hospital_type,
        h.gop_supported,
        h.gop_time,
        h.working_hours,
        h.external_id,
        h.note
    FROM hospitals h
    JOIN documents d ON d.id = h.document_id
    JOIN companies c ON c.id = d.company_id
    JOIN source_tables st ON st.id = h.source_table_id
    {"WHERE " + " AND ".join(where) if where else ""}
    ORDER BY c.code, h.country, h.city, h.name_vi
    LIMIT ?
    """
    params.append(_limit(limit))
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query, params))


@mcp.tool()
@mcp_observe(name="search-waiting-periods")
def search_waiting_periods(
    keyword: str | None = None,
    company_code: str | None = None,
    max_waiting_days: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """Search waiting-period rules by condition text, insurer, and optional maximum waiting days."""
    params = []
    where = []
    if keyword:
        where.append(
            "(wp.condition_group LIKE ? OR wp.condition_detail LIKE ? OR wp.waiting_text LIKE ?)"
        )
        params.extend([_like(keyword), _like(keyword), _like(keyword)])
    if company_code:
        where.append("c.code = ?")
        params.append(company_code)
    if max_waiting_days is not None:
        where.append("(wp.waiting_days IS NULL OR wp.waiting_days <= ?)")
        params.append(max_waiting_days)

    query = f"""
    SELECT
        wp.source_table_id,
        d.id AS document_id,
        st.file_path AS source_file_path,
        c.code AS company_code,
        c.name AS company_name,
        d.document_name,
        wp.condition_group,
        wp.condition_detail,
        wp.waiting_days,
        wp.waiting_text
    FROM waiting_periods wp
    JOIN documents d ON d.id = wp.document_id
    JOIN companies c ON c.id = d.company_id
    JOIN source_tables st ON st.id = wp.source_table_id
    {"WHERE " + " AND ".join(where) if where else ""}
    ORDER BY c.code, wp.waiting_days, wp.condition_detail
    LIMIT ?
    """
    params.append(_limit(limit))
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query, params))


@mcp.tool()
@mcp_observe(name="search-claim-payouts")
def search_claim_payouts(
    keyword: str | None = None,
    company_code: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Search claim payout rules by event text and optional insurer."""
    params = []
    where = []
    if keyword:
        where.append("(cp.event LIKE ? OR cp.payout_text LIKE ?)")
        params.extend([_like(keyword), _like(keyword)])
    if company_code:
        where.append("c.code = ?")
        params.append(company_code)

    query = f"""
    SELECT
        cp.source_table_id,
        d.id AS document_id,
        st.file_path AS source_file_path,
        c.code AS company_code,
        c.name AS company_name,
        d.document_name,
        cp.event,
        cp.payout_rate,
        cp.payout_text
    FROM claim_payouts cp
    JOIN documents d ON d.id = cp.document_id
    JOIN companies c ON c.id = d.company_id
    JOIN source_tables st ON st.id = cp.source_table_id
    {"WHERE " + " AND ".join(where) if where else ""}
    ORDER BY c.code, cp.event
    LIMIT ?
    """
    params.append(_limit(limit))
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query, params))


@mcp.tool()
@mcp_observe(name="search-glossary-terms")
def search_glossary_terms(
    keyword: str,
    company_code: str | None = None,
    limit: int = 30,
) -> list[dict]:
    """Search insurance glossary terms and definitions by keyword."""
    params = [_like(keyword), _like(keyword)]
    where = ["(gt.term LIKE ? OR gt.definition LIKE ?)"]
    if company_code:
        where.append("c.code = ?")
        params.append(company_code)

    query = f"""
    SELECT
        gt.source_table_id,
        d.id AS document_id,
        st.file_path AS source_file_path,
        c.code AS company_code,
        c.name AS company_name,
        d.document_name,
        gt.term,
        gt.definition,
        gt.language
    FROM glossary_terms gt
    JOIN documents d ON d.id = gt.document_id
    JOIN companies c ON c.id = d.company_id
    JOIN source_tables st ON st.id = gt.source_table_id
    WHERE {" AND ".join(where)}
    ORDER BY c.code, gt.term
    LIMIT ?
    """
    params.append(_limit(limit, default=30))
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query, params))


@mcp.tool()
@mcp_observe(name="get-benefit-matrix")
def get_benefit_matrix(
    document_id: int | None = None,
    company_code: str | None = None,
    keyword: str | None = None,
    category_code: str | None = None,
    plan_code: str | None = None,
    limit: int = 150,
) -> list[dict]:
    """Return benefit items and plan-specific values for a document/company/category filter."""
    params = []
    where = []
    if document_id is not None:
        where.append("d.id = ?")
        params.append(document_id)
    if company_code:
        where.append("c.code = ?")
        params.append(company_code)
    if keyword:
        where.append(
            "(bi.raw_name LIKE ? OR bi.normalized_name LIKE ? OR bi.note LIKE ? OR bv.value LIKE ?)"
        )
        params.extend([_like(keyword), _like(keyword), _like(keyword), _like(keyword)])
    if category_code:
        where.append("bc.code = ?")
        params.append(category_code)
    if plan_code:
        where.append("pt.normalized_code = ?")
        params.append(plan_code)

    query = f"""
    SELECT
        bi.source_table_id,
        d.id AS document_id,
        st.file_path AS source_file_path,
        c.code AS company_code,
        c.name AS company_name,
        d.document_name,
        bc.code AS category_code,
        bc.name_vi AS category_name_vi,
        bi.raw_name AS benefit_name,
        bi.normalized_name,
        bi.applicable_to,
        bi.note AS benefit_note,
        pt.raw_name AS plan_name,
        pt.normalized_code AS plan_code,
        pt.plan_level,
        bv.value,
        bv.value_numeric,
        bv.value_context,
        bv.limit_type,
        bv.unit,
        bv.is_covered,
        bv.note AS value_note
    FROM benefit_items bi
    JOIN documents d ON d.id = bi.document_id
    JOIN companies c ON c.id = d.company_id
    JOIN source_tables st ON st.id = bi.source_table_id
    LEFT JOIN benefit_categories bc ON bc.id = bi.category_id
    LEFT JOIN benefit_values bv ON bv.benefit_item_id = bi.id
    LEFT JOIN plan_types pt ON pt.id = bv.plan_type_id
    {"WHERE " + " AND ".join(where) if where else ""}
    ORDER BY c.code, d.document_name, bi.display_order, pt.plan_level
    LIMIT ?
    """
    params.append(_limit(limit, default=150, maximum=300))
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query, params))


@mcp.tool()
@mcp_observe(name="get-short-term-premiums")
def get_short_term_premiums(
    company_code: str | None = None,
    duration_days: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """Return short-term premium rates, optionally filtered by insurer and duration."""
    params = []
    where = []
    if company_code:
        where.append("c.code = ?")
        params.append(company_code)
    if duration_days is not None:
        where.append("(stp.duration_days IS NULL OR stp.duration_days >= ?)")
        params.append(duration_days)

    query = f"""
    SELECT
        stp.source_table_id,
        d.id AS document_id,
        st.file_path AS source_file_path,
        c.code AS company_code,
        c.name AS company_name,
        d.document_name,
        stp.duration_text,
        stp.duration_days,
        stp.premium_rate
    FROM short_term_premiums stp
    JOIN documents d ON d.id = stp.document_id
    JOIN companies c ON c.id = d.company_id
    JOIN source_tables st ON st.id = stp.source_table_id
    {"WHERE " + " AND ".join(where) if where else ""}
    ORDER BY c.code, stp.duration_days, stp.duration_text
    LIMIT ?
    """
    params.append(_limit(limit))
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query, params))


@mcp.tool()
@mcp_observe(name="get-raw-source")
def get_raw_source(source_table_id: int) -> dict:
    """Return the raw extracted JSON and metadata for a source table id."""
    query = """
    SELECT
        st.id AS source_table_id,
        st.file_path,
        st.table_type,
        st.classification_reason,
        st.classification_confidence,
        st.page_number,
        st.table_index,
        st.keys,
        st.content_type,
        st.raw_json,
        d.id AS document_id,
        d.source_path,
        d.document_name,
        c.code AS company_code,
        c.name AS company_name
    FROM source_tables st
    JOIN documents d ON d.id = st.document_id
    JOIN companies c ON c.id = d.company_id
    WHERE st.id = ?
    """
    with get_db_connection() as conn:
        rows = _rows_to_dicts(conn.execute(query, (source_table_id,)))
        return rows[0] if rows else {}


@mcp.tool()
@mcp_observe(name="compare-benefits")
def compare_benefits(
    keyword: str,
    company_codes: list[str],
    plan_codes: list[str] | None = None,
    limit: int = 100,
) -> list[dict]:
    """Compare benefit rows across insurers for a keyword and optional normalized plan codes."""
    if not company_codes:
        raise ValueError("company_codes must contain at least one insurer code.")

    params = [_like(keyword), _like(keyword), _like(keyword), *company_codes]
    where = [
        "(bi.raw_name LIKE ? OR bi.note LIKE ? OR bv.value LIKE ?)",
        f"c.code IN ({_placeholders(company_codes)})",
    ]
    if plan_codes:
        where.append(f"pt.normalized_code IN ({_placeholders(plan_codes)})")
        params.extend(plan_codes)

    query = f"""
    SELECT
        bi.source_table_id,
        d.id AS document_id,
        st.file_path AS source_file_path,
        c.code AS company_code,
        c.name AS company_name,
        d.document_name,
        bi.raw_name AS benefit_name,
        bi.applicable_to,
        bi.note AS benefit_note,
        pt.raw_name AS plan_name,
        pt.normalized_code AS plan_code,
        pt.plan_level,
        bv.value,
        bv.value_numeric,
        bv.value_context,
        bv.unit,
        bv.limit_type,
        bv.is_covered,
        bv.note AS value_note
    FROM benefit_items bi
    JOIN documents d ON d.id = bi.document_id
    JOIN companies c ON c.id = d.company_id
    JOIN source_tables st ON st.id = bi.source_table_id
    LEFT JOIN benefit_values bv ON bv.benefit_item_id = bi.id
    LEFT JOIN plan_types pt ON pt.id = bv.plan_type_id
    WHERE {" AND ".join(where)}
    ORDER BY c.code, pt.plan_level, d.document_name, bi.display_order
    LIMIT ?
    """
    params.append(_limit(limit, default=100))
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query, params))


@mcp.tool()
@mcp_observe(name="search-exclusions")
def search_exclusions(
    keyword: str | None = None,
    company_code: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Search exclusion-related terms and extracted benefit rows across glossary and benefits."""
    terms = ["loại trừ", "không chi trả", "không được bảo hiểm", "exclusion"]
    if keyword:
        terms.append(keyword)

    benefit_params = []
    glossary_params = []
    benefit_clauses = []
    glossary_clauses = []
    for term in terms:
        pattern = _like(term)
        benefit_clauses.append(
            "(bi.raw_name LIKE ? OR bi.note LIKE ? OR bi.applicable_to LIKE ?)"
        )
        benefit_params.extend([pattern, pattern, pattern])
        glossary_clauses.append("(gt.term LIKE ? OR gt.definition LIKE ?)")
        glossary_params.extend([pattern, pattern])

    benefit_where = f"({' OR '.join(benefit_clauses)})"
    glossary_where = f"({' OR '.join(glossary_clauses)})"
    company_filter_benefit = ""
    company_filter_glossary = ""
    if company_code:
        company_filter_benefit = " AND c.code = ?"
        company_filter_glossary = " AND c.code = ?"
        benefit_params.append(company_code)
        glossary_params.append(company_code)

    query = f"""
    SELECT * FROM (
        SELECT
            'benefit_item' AS source_kind,
            bi.source_table_id,
            d.id AS document_id,
            st.file_path AS source_file_path,
            c.code AS company_code,
            c.name AS company_name,
            d.document_name,
            bi.raw_name AS title,
            bi.note AS detail,
            bi.applicable_to AS extra
        FROM benefit_items bi
        JOIN documents d ON d.id = bi.document_id
        JOIN companies c ON c.id = d.company_id
        JOIN source_tables st ON st.id = bi.source_table_id
        WHERE {benefit_where}{company_filter_benefit}

        UNION ALL

        SELECT
            'glossary_term' AS source_kind,
            gt.source_table_id,
            d.id AS document_id,
            st.file_path AS source_file_path,
            c.code AS company_code,
            c.name AS company_name,
            d.document_name,
            gt.term AS title,
            gt.definition AS detail,
            gt.language AS extra
        FROM glossary_terms gt
        JOIN documents d ON d.id = gt.document_id
        JOIN companies c ON c.id = d.company_id
        JOIN source_tables st ON st.id = gt.source_table_id
        WHERE {glossary_where}{company_filter_glossary}
    )
    ORDER BY company_code, source_kind, title
    LIMIT ?
    """
    params = benefit_params + glossary_params + [_limit(limit)]
    with get_db_connection() as conn:
        return _rows_to_dicts(conn.execute(query, params))


if __name__ == "__main__":
    mcp.run()
