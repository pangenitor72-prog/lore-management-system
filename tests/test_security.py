import pytest
from src.db.neo4j_adapter import Neo4jDatabase
from src.services.audit_log import redact_credentials

def test_cypher_identifier_sanitization():
    """Test that Cypher identifiers are properly sanitized."""
    db = Neo4jDatabase("bolt://localhost:7687", ("neo4j", "password"))
    
    # Valid identifiers should be returned as-is
    assert db._sanitize_cypher_identifier("valid_name", "fallback") == "valid_name"
    assert db._sanitize_cypher_identifier("Entity123", "fallback") == "Entity123"
    
    # Invalid identifiers should return the default/fallback
    assert db._sanitize_cypher_identifier("'; DROP INDEX--", "fallback") == "fallback"
    assert db._sanitize_cypher_identifier("", "fallback") == "fallback"
    assert db._sanitize_cypher_identifier("123index", "fallback") == "fallback"  # Can't start with number

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

