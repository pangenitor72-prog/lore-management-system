"""Regression checks for credential configuration hardening."""
from pathlib import Path

import pytest

from src.mantle.db.neo4j_adapter import Neo4jDatabase


@pytest.mark.parametrize(
    "kwargs",
    [
        {"uri": "", "auth": ("neo4j", "valid-password")},
        {"uri": "  ", "auth": ("neo4j", "valid-password")},
        {"uri": None, "auth": ("neo4j", "valid-password")},
        {"uri": "bolt://localhost:7687", "auth": None},
        {"uri": "bolt://localhost:7687", "auth": ("neo4j", "")},
        {"uri": "bolt://localhost:7687", "auth": ("", "valid-password")},
        {"uri": "bolt://localhost:7687", "user": "neo4j", "password": None},
        {"uri": "bolt://localhost:7687", "user": None, "password": "valid-password"},
    ],
)
def test_neo4j_constructor_rejects_incomplete_credentials(kwargs):
    with pytest.raises(ValueError):
        Neo4jDatabase(**kwargs)


def test_neo4j_constructor_retains_both_supported_auth_forms():
    assert Neo4jDatabase(
        "bolt://localhost:7687", auth=("neo4j", "valid-password")
    ).auth == ("neo4j", "valid-password")
    assert Neo4jDatabase(
        "bolt://localhost:7687", "neo4j", "valid-password"
    ).auth == ("neo4j", "valid-password")


def test_production_template_uses_only_credentials_placeholders():
    template = (Path(__file__).resolve().parents[1] / ".env.production.template").read_text()
    lines = template.splitlines()
    for key in ("NEO4J_PASSWORD", "API_SECRET_KEY", "EMBEDDING_API_KEY"):
        assert f"{key}=CHANGE_ME_{key}" in lines
    assert "SECURITY: Example values only" in template


def test_gitignore_covers_nested_environment_files():
    ignore = (Path(__file__).resolve().parents[1] / ".gitignore").read_text()
    assert "**/.env.*" in ignore
    assert "!**/.env.example" in ignore
