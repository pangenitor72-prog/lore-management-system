import pytest
from src.neo4j_adapter import Neo4jDatabase
from src.audit_log import redact_credentials

def test_cypher_identifier_sanitization():
    """Test that Cypher identifiers are properly sanitized."""
    db = Neo4jDatabase("bolt://localhost:7687", ("neo4j", "password"))
    
    assert db._sanitize_cypher_identifier("valid_name") == "valid_name"
    assert db._sanitize_cypher_identifier("Entity123") == "Entity123"
    assert db._sanitize_cypher_identifier("'; DROP INDEX--") == "DROPINDEX"
    assert db._sanitize_cypher_identifier("", "fallback") == "fallback"
    assert db._sanitize_cypher_identifier("123index") == "_123index"

def test_credential_redaction():
    """Test that credentials are redacted from log messages."""
    assert "***REDACTED***" in redact_credentials(
        "bolt://neo4j:secretpass@localhost:7687"
    )
    
    assert "***REDACTED***" in redact_credentials(
        "Using api_key=AIzaSyDxxxxxxxxxxxxxxxxx"
    )
    
    assert "***REDACTED***" in redact_credentials(
        "password='super_secret_123'"
    )
    
    assert redact_credentials("Neo4j connected successfully") == "Neo4j connected successfully"

