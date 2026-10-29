"""Env-var validation for the rxiv-feed action.

Adapted from ``qte77/gha-arxiv-stats-action-legacy/src/validation.py``. Validates
env vars that are actually consumed by ``src/app.py`` and per-server
fetchers — not the stale ``START_RESULT``/``RESULT_COUNT``/
``MAX_RESULTS_PER_QUERY`` triple from the original which is unused.
"""

from datetime import datetime

_ALLOWED_SERVERS = frozenset({"biorxiv", "medrxiv", "arxiv", "psyarxiv"})
_INTEGER_VARS = ("DAYS", "MAX_AGE_DAYS", "PAGE_SIZE", "MAX_PAGES")
_DATE_VARS = ("DATE_FROM", "DATE_TO")


def _check_out_dir(env: dict) -> None:
    out_dir = env.get("OUT_DIR", "./data")
    if ".." in out_dir:
        raise ValueError(f"OUT_DIR must not contain path traversal: {out_dir}")


def _check_server(env: dict) -> str:
    server = env.get("SERVER", "biorxiv")
    if server not in _ALLOWED_SERVERS:
        raise ValueError(f"SERVER must be one of {sorted(_ALLOWED_SERVERS)}, got: {server}")
    return server


def _check_include_citations(env: dict) -> None:
    citations = env.get("INCLUDE_CITATIONS")
    if citations is not None and citations not in ("true", "false"):
        raise ValueError(f"INCLUDE_CITATIONS must be 'true' or 'false', got: {citations}")


def _check_integer_var(key: str, val: str) -> None:
    try:
        n = int(val)
    except (ValueError, TypeError):
        raise ValueError(f"{key} must be a positive integer, got: {val}") from None
    if n < 0:
        raise ValueError(f"{key} must be a positive integer, got: {val}")


def _check_integer_vars(env: dict) -> None:
    for key in _INTEGER_VARS:
        val = env.get(key)
        if val:
            _check_integer_var(key, val)


def _check_date_vars(env: dict) -> None:
    for key in _DATE_VARS:
        val = env.get(key)
        if not val:
            continue
        try:
            datetime.strptime(val, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"{key} must be YYYY-MM-DD, got: {val}") from None


def _check_topics_for_arxiv(env: dict, server: str) -> None:
    if server == "arxiv" and not env.get("TOPICS"):
        raise ValueError("TOPICS must be non-empty when SERVER=arxiv")


def validate_env(env: dict) -> None:
    """Raise ``ValueError`` if any env var is malformed.

    Server-conditional: ``TOPICS`` is required (non-empty) only when
    ``SERVER=arxiv``. ``CATEGORIES`` is optional for all servers.
    """
    _check_out_dir(env)
    server = _check_server(env)
    _check_include_citations(env)
    _check_integer_vars(env)
    _check_date_vars(env)
    _check_topics_for_arxiv(env, server)
