from src.lms.core.models import ContradictionCreate, ContradictionSeverity
from datetime import datetime

def test_contradiction_create_model():
    """
    Tests the creation of a ContradictionCreate model.
    """
    now = datetime.now()
    test = ContradictionCreate(
        contradiction_id="123",
        contradiction_type="temporal",
        severity=ContradictionSeverity.HIGH,
        description="Example contradiction for validation test",
        evidence={"note": "test evidence"},
        entity_ids=["entity-1", "entity-2"],
        detected_at=now
    )

    assert test.contradiction_id == "123"
    assert test.contradiction_type == "temporal"
    assert test.severity == ContradictionSeverity.HIGH
    assert test.description == "Example contradiction for validation test"
    assert test.evidence == {"note": "test evidence"}
    assert test.entity_ids == ["entity-1", "entity-2"]
    assert test.detected_at == now
