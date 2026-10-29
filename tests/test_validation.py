"""Env-var validator tests for src/validation.py."""

import pytest

from src.validation import validate_env


def test_accepts_valid_biorxiv_config():
    """A minimal biorxiv-server env passes validation."""
    validate_env({"OUT_DIR": "./data/biorxiv", "SERVER": "biorxiv", "DAYS": "7"})


def test_accepts_valid_arxiv_config():
    """A minimal arxiv-server env passes validation."""
    validate_env(
        {
            "OUT_DIR": "./data/arxiv",
            "SERVER": "arxiv",
            "TOPICS": "cat:cs.CV",
            "INCLUDE_CITATIONS": "false",
            "MAX_AGE_DAYS": "7",
        }
    )


def test_rejects_path_traversal_in_out_dir():
    """OUT_DIR containing `..` raises ValueError."""
    with pytest.raises(ValueError, match="OUT_DIR"):
        validate_env({"OUT_DIR": "../../etc", "SERVER": "biorxiv"})


def test_rejects_unknown_server():
    """SERVER must be one of biorxiv/medrxiv/arxiv."""
    with pytest.raises(ValueError, match="SERVER"):
        validate_env({"OUT_DIR": "./data", "SERVER": "chemrxiv"})


def test_rejects_invalid_include_citations_flag():
    """INCLUDE_CITATIONS must be 'true' or 'false'."""
    env = {
        "OUT_DIR": "./data",
        "SERVER": "arxiv",
        "TOPICS": "cat:cs.AI",
        "INCLUDE_CITATIONS": "yes",
    }
    with pytest.raises(ValueError, match="INCLUDE_CITATIONS"):
        validate_env(env)


@pytest.mark.parametrize("var", ["DAYS", "MAX_AGE_DAYS", "PAGE_SIZE", "MAX_PAGES"])
def test_rejects_non_integer_count(var: str):
    """Integer env vars reject non-numeric values."""
    env = {"OUT_DIR": "./data", "SERVER": "biorxiv", var: "abc"}
    with pytest.raises(ValueError, match=var):
        validate_env(env)


@pytest.mark.parametrize("var", ["DAYS", "MAX_AGE_DAYS", "PAGE_SIZE", "MAX_PAGES"])
def test_rejects_negative_count(var: str):
    """Integer env vars reject negative values."""
    env = {"OUT_DIR": "./data", "SERVER": "biorxiv", var: "-1"}
    with pytest.raises(ValueError, match=var):
        validate_env(env)


def test_rejects_invalid_date_format():
    """DATE_FROM / DATE_TO must be YYYY-MM-DD."""
    env = {
        "OUT_DIR": "./data",
        "SERVER": "arxiv",
        "TOPICS": "x",
        "DATE_FROM": "12/09/2024",
    }
    with pytest.raises(ValueError, match="DATE_FROM"):
        validate_env(env)


def test_rejects_empty_topics_when_server_is_arxiv():
    """TOPICS must be non-empty when SERVER=arxiv."""
    with pytest.raises(ValueError, match="TOPICS"):
        validate_env({"OUT_DIR": "./data", "SERVER": "arxiv", "TOPICS": ""})


def test_topics_optional_for_biorxiv():
    """TOPICS is not required when SERVER is biorxiv/medrxiv."""
    validate_env({"OUT_DIR": "./data/biorxiv", "SERVER": "biorxiv"})
    validate_env({"OUT_DIR": "./data/medrxiv", "SERVER": "medrxiv"})


def test_accepts_psyarxiv_server():
    """psyarxiv is an allowlisted SERVER and needs no TOPICS."""
    validate_env({"OUT_DIR": "./data/psyarxiv", "SERVER": "psyarxiv"})
