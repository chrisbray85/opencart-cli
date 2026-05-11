"""OpenCart version auto-detection and version-aware query helpers.

OpenCart's schema varies between 2.x, 3.x, and 4.x:
  - 2.x: oc_setting has `code` column
  - 3.x: oc_setting has `code` and `store_id`, added `oc_information_to_*`
  - 4.x: namespace changes, oc_setting reorganised, oc_module structure changes

This module sniffs the schema to figure out which version, and caches
the result per profile for the session.
"""

from __future__ import annotations

from typing import Literal

from .db import DBError, OpenCartDB

OCVersion = Literal["2.x", "3.x", "4.x", "unknown"]

_CACHE: dict[str, OCVersion] = {}


def detect_version(db: OpenCartDB) -> OCVersion:
    """Sniff the OpenCart schema to determine the major version family.

    Cached per profile for the duration of the process.
    """
    cache_key = db.profile.name
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    prefix = db.profile.opencart.table_prefix

    # Look for 4.x signature first (more specific): oc_extension_install
    try:
        rows = db.query(
            f"SHOW TABLES LIKE '{prefix}extension_install'",
        )
        if rows:
            _CACHE[cache_key] = "4.x"
            return "4.x"
    except DBError:
        pass

    # 3.x has oc_information_to_store, 2.x does not
    try:
        rows = db.query(
            f"SHOW TABLES LIKE '{prefix}information_to_store'",
        )
        if rows:
            _CACHE[cache_key] = "3.x"
            return "3.x"
    except DBError:
        pass

    # If we got here and there's any oc_product table, assume 2.x
    try:
        rows = db.query(
            f"SHOW TABLES LIKE '{prefix}product'",
        )
        if rows:
            _CACHE[cache_key] = "2.x"
            return "2.x"
    except DBError:
        pass

    _CACHE[cache_key] = "unknown"
    return "unknown"


def effective_version(db: OpenCartDB) -> OCVersion:
    """Return the version to use for queries.

    If the profile pins a version, honour it. Otherwise auto-detect.
    """
    pinned = db.profile.opencart.version
    if pinned in ("2.x", "3.x", "4.x"):
        return pinned  # type: ignore[return-value]
    if pinned == "auto":
        return detect_version(db)
    return detect_version(db)
