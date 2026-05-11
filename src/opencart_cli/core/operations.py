"""High-level OpenCart operations.

Each function takes an `OpenCartDB` and returns plain Python data structures
(dicts/lists). No printing, no formatting — that's the CLI layer's job.

These are designed for reuse: the CLI commands wrap them, the `ask` AI
command calls them after generating SQL, and a future MCP server could
expose them as tools.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from .audit import log_mutation
from .db import OpenCartDB

# ---------- Schema discovery ----------

_DESTRUCTIVE_KEYWORDS = re.compile(
    r"\b(DROP|TRUNCATE|ALTER|CREATE|RENAME|GRANT|REVOKE|REPLACE)\b",
    re.IGNORECASE,
)
_MUTATION_KEYWORDS = re.compile(r"\b(INSERT|UPDATE|DELETE)\b", re.IGNORECASE)


def list_tables(db: OpenCartDB, pattern: str = "oc_%") -> list[dict[str, Any]]:
    """SHOW TABLES LIKE pattern."""
    return db.query(f"SHOW TABLES LIKE '{_safe_like(pattern)}'")


def describe_table(db: OpenCartDB, table: str) -> list[dict[str, Any]]:
    """DESCRIBE a table — columns, types, keys, nullability."""
    _check_ident(table)
    return db.query(f"DESCRIBE `{table}`")


def schema_summary(db: OpenCartDB, max_cols: int = 24) -> dict[str, list[dict[str, Any]]]:
    """Compact schema snapshot for AI prompts: {table: [{col, type}, ...]}."""
    tables = [next(iter(r.values())) for r in list_tables(db)]
    summary: dict[str, list[dict[str, Any]]] = {}
    for tbl in tables:
        try:
            rows = describe_table(db, tbl)[:max_cols]
            summary[tbl] = [{"col": r["Field"], "type": r["Type"]} for r in rows]
        except Exception:
            continue
    return summary


# ---------- Products ----------


def list_products(
    db: OpenCartDB,
    search: str | None = None,
    status: int | None = None,
    low_stock_under: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List products with optional filters."""
    where_clauses: list[str] = []
    params: list[Any] = []
    if status is not None:
        where_clauses.append("p.status = ?")
        params.append(status)
    if low_stock_under is not None:
        where_clauses.append("p.quantity < ?")
        params.append(low_stock_under)
    if search:
        where_clauses.append("(pd.name LIKE ? OR p.model LIKE ? OR p.sku LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    params.append(limit)
    sql = f"""
        SELECT p.product_id, p.model, p.sku, pd.name, p.price, p.quantity, p.status, p.date_modified
        FROM oc_product p
        LEFT JOIN oc_product_description pd
          ON pd.product_id = p.product_id AND pd.language_id = 1
        {where}
        ORDER BY p.product_id DESC
        LIMIT ?
    """
    return db.query(sql, params)


def get_product(db: OpenCartDB, product_id: int) -> dict[str, Any] | None:
    """Full product detail by ID. Returns None if not found."""
    rows = db.query(
        """
        SELECT p.*, pd.name, pd.description, pd.meta_title, pd.meta_description, pd.meta_keyword
        FROM oc_product p
        LEFT JOIN oc_product_description pd
          ON pd.product_id = p.product_id AND pd.language_id = 1
        WHERE p.product_id = ?
        """,
        [int(product_id)],
    )
    return rows[0] if rows else None


def update_product_field(
    db: OpenCartDB,
    product_id: int,
    field: str,
    value: Any,
) -> dict[str, int]:
    """Update a single product column. Whitelisted columns only."""
    allowed = {"price", "quantity", "status", "model", "sku", "ean", "weight"}
    if field not in allowed:
        raise ValueError(f"Field '{field}' not in writable allowlist: {sorted(allowed)}")
    before = get_product(db, product_id)
    if before is None:
        raise ValueError(f"Product {product_id} not found")
    result = db.execute(
        f"UPDATE oc_product SET {field} = ?, date_modified = NOW() WHERE product_id = ?",
        [value, int(product_id)],
    )
    log_mutation(
        profile=db.profile.name,
        action="update_product_field",
        target=f"oc_product[{product_id}].{field}",
        before={field: before.get(field)},
        after={field: value},
    )
    return result


# ---------- Orders ----------


def list_orders(
    db: OpenCartDB,
    days: int | None = 30,
    status: int | None = None,
    min_total: float | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Recent orders, optionally filtered by status / minimum total."""
    where: list[str] = []
    params: list[Any] = []
    if days is not None:
        where.append("o.date_added >= ?")
        params.append((datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00"))
    if status is not None:
        where.append("o.order_status_id = ?")
        params.append(int(status))
    if min_total is not None:
        where.append("o.total >= ?")
        params.append(float(min_total))
    clause = "WHERE " + " AND ".join(where) if where else ""
    params.append(limit)
    sql = f"""
        SELECT o.order_id, o.firstname, o.lastname, o.email, o.total,
               o.order_status_id, os.name AS status,
               o.payment_method, o.shipping_method, o.date_added
        FROM oc_order o
        LEFT JOIN oc_order_status os
          ON os.order_status_id = o.order_status_id AND os.language_id = 1
        {clause}
        ORDER BY o.order_id DESC
        LIMIT ?
    """
    return db.query(sql, params)


def get_order(db: OpenCartDB, order_id: int) -> dict[str, Any]:
    """Order header + line items + status history."""
    header = db.query(
        """
        SELECT o.*, os.name AS status
        FROM oc_order o
        LEFT JOIN oc_order_status os
          ON os.order_status_id = o.order_status_id AND os.language_id = 1
        WHERE o.order_id = ?
        """,
        [int(order_id)],
    )
    if not header:
        return {}
    products = db.query(
        "SELECT name, model, quantity, price, total FROM oc_order_product WHERE order_id = ?",
        [int(order_id)],
    )
    history = db.query(
        """
        SELECT oh.date_added, os.name AS status, oh.comment
        FROM oc_order_history oh
        LEFT JOIN oc_order_status os
          ON os.order_status_id = oh.order_status_id AND os.language_id = 1
        WHERE oh.order_id = ?
        ORDER BY oh.order_history_id
        """,
        [int(order_id)],
    )
    return {"order": header[0], "products": products, "history": history}


# ---------- Customers ----------


def list_customers(
    db: OpenCartDB,
    search: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List or search customers."""
    where: list[str] = []
    params: list[Any] = []
    if search:
        where.append("(email LIKE ? OR firstname LIKE ? OR lastname LIKE ? OR telephone LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like, like])
    clause = "WHERE " + " AND ".join(where) if where else ""
    params.append(limit)
    sql = f"""
        SELECT customer_id, firstname, lastname, email, telephone, status, date_added
        FROM oc_customer
        {clause}
        ORDER BY customer_id DESC
        LIMIT ?
    """
    return db.query(sql, params)


# ---------- Stock ----------


def low_stock_report(db: OpenCartDB, threshold: int = 15) -> list[dict[str, Any]]:
    """Products at or below a stock threshold, lowest first."""
    return db.query(
        """
        SELECT p.product_id, p.model, p.sku, pd.name, p.quantity, p.price, p.status
        FROM oc_product p
        LEFT JOIN oc_product_description pd
          ON pd.product_id = p.product_id AND pd.language_id = 1
        WHERE p.quantity <= ? AND p.status = 1
        ORDER BY p.quantity ASC, pd.name ASC
        """,
        [int(threshold)],
    )


# ---------- Sales ----------


def sales_summary(db: OpenCartDB, days: int = 30) -> dict[str, Any]:
    """Revenue, order count, AOV, and a daily breakdown for sparklines."""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
    # Totals
    totals = db.query(
        """
        SELECT
          COUNT(*) AS orders,
          COALESCE(SUM(total), 0) AS revenue,
          COALESCE(AVG(total), 0) AS aov
        FROM oc_order
        WHERE date_added >= ?
          AND order_status_id > 0  -- exclude missing/cart
          AND order_status_id NOT IN (7, 8, 9, 10, 11)  -- cancelled/refunded/voided
        """,
        [since],
    )
    # Daily breakdown
    daily = db.query(
        """
        SELECT DATE(date_added) AS day,
               COUNT(*) AS orders,
               COALESCE(SUM(total), 0) AS revenue
        FROM oc_order
        WHERE date_added >= ?
          AND order_status_id > 0
          AND order_status_id NOT IN (7, 8, 9, 10, 11)
        GROUP BY DATE(date_added)
        ORDER BY day
        """,
        [since],
    )
    # Top sellers
    top = db.query(
        """
        SELECT op.product_id, op.name,
               SUM(op.quantity) AS qty,
               SUM(op.total) AS revenue
        FROM oc_order_product op
        JOIN oc_order o ON o.order_id = op.order_id
        WHERE o.date_added >= ?
          AND o.order_status_id > 0
          AND o.order_status_id NOT IN (7, 8, 9, 10, 11)
        GROUP BY op.product_id, op.name
        ORDER BY revenue DESC
        LIMIT 10
        """,
        [since],
    )
    summary = totals[0] if totals else {"orders": 0, "revenue": 0, "aov": 0}
    return {
        "period_days": days,
        "since": since,
        "orders": int(summary["orders"] or 0),
        "revenue": float(summary["revenue"] or 0),
        "aov": float(summary["aov"] or 0),
        "daily": daily,
        "top_products": top,
    }


# ---------- Settings ----------


def get_settings(
    db: OpenCartDB,
    group: str | None = None,
    key: str | None = None,
) -> list[dict[str, Any]]:
    """OpenCart settings, optionally filtered by group code or key."""
    where: list[str] = []
    params: list[Any] = []
    if group:
        where.append("code = ?")
        params.append(group)
    if key:
        where.append("`key` = ?")
        params.append(key)
    clause = "WHERE " + " AND ".join(where) if where else ""
    return db.query(
        f"SELECT setting_id, store_id, code, `key`, value FROM oc_setting {clause} ORDER BY code, `key`",
        params,
    )


def set_setting(db: OpenCartDB, group: str, key: str, value: str) -> dict[str, int]:
    """Update an existing setting key/value pair."""
    before = get_settings(db, group=group, key=key)
    result = db.execute(
        "UPDATE oc_setting SET value = ? WHERE code = ? AND `key` = ?",
        [value, group, key],
    )
    log_mutation(
        profile=db.profile.name,
        action="set_setting",
        target=f"oc_setting[{group}.{key}]",
        before={"value": before[0]["value"]} if before else None,
        after={"value": value},
    )
    return result


# ---------- Raw SQL ----------


def safe_select(db: OpenCartDB, sql: str) -> list[dict[str, Any]]:
    """Run a user-supplied SELECT. Refuses destructive or mutation keywords."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise ValueError("Empty SQL")
    first = stripped.split(None, 1)[0].upper()
    if first not in {"SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN"}:
        raise ValueError(f"Only SELECT/SHOW/DESCRIBE/EXPLAIN allowed, got '{first}'")
    if _DESTRUCTIVE_KEYWORDS.search(stripped):
        raise ValueError("DDL keywords (DROP/ALTER/TRUNCATE/CREATE/RENAME) are blocked")
    if _MUTATION_KEYWORDS.search(stripped):
        raise ValueError(
            "INSERT/UPDATE/DELETE are blocked here — use `opencart products update` etc."
        )
    return db.query(stripped)


# ---------- Helpers ----------


def _safe_like(pattern: str) -> str:
    """Sanitize a LIKE pattern: allow %_ and word chars, reject quotes/backticks."""
    if any(c in pattern for c in "'\";\\`"):
        raise ValueError(f"Unsafe LIKE pattern: {pattern!r}")
    return pattern


def _check_ident(name: str) -> None:
    """Identifiers (table/column names) must match a strict whitelist."""
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError(f"Unsafe identifier: {name!r}")
