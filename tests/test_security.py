import pytest
from src.db.neo4j_adapter import Neo4jDatabase
from src.services.audit_log import redact_credentials
from src.core.utils import sanitize_user_input, validate_canon_id, validate_env_var


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


def test_neo4j_credential_validation():
    """Test that Neo4jDatabase validates credentials properly."""
    # Valid credentials should work
    db = Neo4jDatabase("bolt://localhost:7687", auth=("neo4j", "password"))
    assert db.uri == "bolt://localhost:7687"
    assert db.auth == ("neo4j", "password")
    
    # Empty URI should raise ValueError
    with pytest.raises(ValueError, match="Neo4j URI cannot be empty"):
        Neo4jDatabase("", auth=("neo4j", "password"))
    
    with pytest.raises(ValueError, match="Neo4j URI cannot be empty"):
        Neo4jDatabase("   ", auth=("neo4j", "password"))
    
    # Empty username should raise ValueError
    with pytest.raises(ValueError, match="Neo4j username cannot be empty"):
        Neo4jDatabase("bolt://localhost:7687", auth=("", "password"))
    
    # Empty password should raise ValueError
    with pytest.raises(ValueError, match="Neo4j password cannot be empty"):
        Neo4jDatabase("bolt://localhost:7687", auth=("neo4j", ""))
    
    # None credentials via user/password should raise ValueError (username will be None)
    with pytest.raises(ValueError, match="Neo4j username cannot be empty"):
        Neo4jDatabase("bolt://localhost:7687", user=None, password=None)
    
    # Invalid auth tuple length should raise ValueError
    with pytest.raises(ValueError, match="Neo4j auth must be a tuple"):
        Neo4jDatabase("bolt://localhost:7687", auth=("only_one",))


def test_sanitize_user_input():
    """Test user input sanitization."""
    # Valid input should be returned stripped
    assert sanitize_user_input("  Hello World  ") == "Hello World"
    assert sanitize_user_input("Valid-Name_123") == "Valid-Name_123"
    assert sanitize_user_input("Question?") == "Question?"
    
    # Empty input should return empty string
    assert sanitize_user_input("") == ""
    assert sanitize_user_input(None) == ""
    
    # Input too long should raise ValueError
    with pytest.raises(ValueError, match="Input too long"):
        sanitize_user_input("a" * 501)
    
    # Special characters without allow_special should raise ValueError
    with pytest.raises(ValueError, match="disallowed special characters"):
        sanitize_user_input("Hello<script>alert('xss')</script>")
    
    with pytest.raises(ValueError, match="disallowed special characters"):
        sanitize_user_input("DROP TABLE users;")
    
    # Special characters with allow_special=True should work
    result = sanitize_user_input("Hello<world>", allow_special=True)
    assert result == "Hello<world>"


def test_validate_canon_id():
    """Test canonical ID validation."""
    # Valid IDs should pass
    assert validate_canon_id("valid_id") == "valid_id"
    assert validate_canon_id("Character-123") == "Character-123"
    assert validate_canon_id("  spaced_id  ") == "spaced_id"
    
    # Empty ID should raise ValueError
    with pytest.raises(ValueError, match="Canon ID must be a non-empty string"):
        validate_canon_id("")
    
    with pytest.raises(ValueError, match="Canon ID must be a non-empty string"):
        validate_canon_id(None)
    
    # Whitespace-only should raise after stripping
    with pytest.raises(ValueError, match="Canon ID must be a non-empty string"):
        validate_canon_id("   ")
    
    # Invalid characters should raise ValueError
    with pytest.raises(ValueError, match="invalid characters"):
        validate_canon_id("id with spaces")
    
    with pytest.raises(ValueError, match="invalid characters"):
        validate_canon_id("id@special")
    
    with pytest.raises(ValueError, match="invalid characters"):
        validate_canon_id("id/path")
    
    # Too long should raise ValueError
    with pytest.raises(ValueError, match="Canon ID too long"):
        validate_canon_id("a" * 101)


def test_validate_env_var():
    """Test environment variable validation."""
    # Valid values should be returned stripped
    assert validate_env_var("TEST_VAR", "value") == "value"
    assert validate_env_var("TEST_VAR", "  spaced  ") == "spaced"
    
    # Required variable missing should raise ValueError
    with pytest.raises(ValueError, match="Required environment variable TEST_VAR"):
        validate_env_var("TEST_VAR", None)
    
    with pytest.raises(ValueError, match="Required environment variable TEST_VAR"):
        validate_env_var("TEST_VAR", "")
    
    with pytest.raises(ValueError, match="Required environment variable TEST_VAR"):
        validate_env_var("TEST_VAR", "   ")
    
    # Optional variable missing should return None
    assert validate_env_var("OPTIONAL_VAR", None, required=False) is None
    assert validate_env_var("OPTIONAL_VAR", "", required=False) is None
    assert validate_env_var("OPTIONAL_VAR", "   ", required=False) is None
    
    # Optional variable with value should be returned
    assert validate_env_var("OPTIONAL_VAR", "value", required=False) == "value"


