import pytest
from fastapi.testclient import TestClient
from fastapi import status
import uuid
from src.lms.core.models import ContradictionStatus, ContradictionSeverity, EntityType, ApprovalStatus

# The 'client' fixture is now provided by 'tests/conftest.py'

@pytest.fixture(scope="function", autouse=True)
def setup_entities(client: TestClient):
    """A fixture to automatically create entities before each test in this module."""
    # This runs for every test function in this file, thanks to autouse=True
    resp1 = client.post("/entities", json={
        "entity_type": EntityType.CHARACTER.value, "canonical_name": "Entity A",
        "approval_status": ApprovalStatus.APPROVED.value, "confidence_level": "CONFIRMED", "party_knowledge": "KNOWN"
    })
    resp2 = client.post("/entities", json={
        "entity_type": EntityType.CHARACTER.value, "canonical_name": "Entity B",
        "approval_status": ApprovalStatus.APPROVED.value, "confidence_level": "CONFIRMED", "party_knowledge": "KNOWN"
    })
    assert resp1.status_code == status.HTTP_201_CREATED
    assert resp2.status_code == status.HTTP_201_CREATED


def test_create_and_get_contradiction(client: TestClient):
    """
    Tests creating a contradiction with severity/status enums and multiple
    involved entities, then retrieving it to check for data integrity.
    """
    list_entities_resp = client.get("/entities")
    entity_ids = [e['canon_id'] for e in list_entities_resp.json()]
    assert len(entity_ids) >= 2
    
    contradiction_id = str(uuid.uuid4())
    contradiction_data = {
        "contradiction_id": contradiction_id,
        "contradiction_type": "Temporal",
        "severity": ContradictionSeverity.HIGH.value,
        "description": "Entity A cannot be born after Entity B dies if B is A's parent.",
        "evidence": {"timeline_A": "...", "timeline_B": "..."},
        "entity_ids": entity_ids
    }

    create_response = client.post("/api/contradictions", json=contradiction_data)
    assert create_response.status_code == status.HTTP_201_CREATED
    
    created = create_response.json()
    assert created['contradiction_id'] == contradiction_id
    assert created['severity'] == ContradictionSeverity.HIGH.value
    assert created['status'] == ContradictionStatus.PENDING.value
    assert sorted(created['entity_ids']) == sorted(entity_ids)
    
    get_response = client.get(f"/api/contradictions/{contradiction_id}")
    assert get_response.status_code == status.HTTP_200_OK
    
    retrieved = get_response.json()
    assert retrieved['contradiction']['contradiction_id'] == contradiction_id
    assert sorted(retrieved['contradiction']['entity_ids']) == sorted(entity_ids)
    assert retrieved['analysis'] is None

def test_add_triage_analysis_and_update_status(client: TestClient):
    """
    Tests adding a triage analysis to a contradiction and verifies that
    the contradiction's status is automatically updated to 'IN_REVIEW'.
    """
    # 1. Create a contradiction
    contradiction_id = str(uuid.uuid4())
    contradiction_data = {
        "contradiction_id": contradiction_id,
        "contradiction_type": "Logical",
        "severity": ContradictionSeverity.MEDIUM.value,
        "description": "A character cannot be in two places at once.",
        "evidence": {},
        "entity_ids": []
    }
    create_resp = client.post("/api/contradictions", json=contradiction_data)
    assert create_resp.status_code == status.HTTP_201_CREATED

    # 2. Add triage analysis
    analysis_data = {
        "contradiction_id": contradiction_id,
        "analyst": "AI_TEST_HARNESS",
        "analysis": "The logical conflict is confirmed based on event logs.",
        "recommendation": "Merge the conflicting event records.",
        "confidence": ContradictionSeverity.HIGH.value
    }
    analysis_response = client.post(f"/api/contradictions/{contradiction_id}/analysis", json=analysis_data)
    assert analysis_response.status_code == status.HTTP_201_CREATED
    
    # 3. Verify the analysis was added and the status was updated
    get_response = client.get(f"/api/contradictions/{contradiction_id}")
    assert get_response.status_code == status.HTTP_200_OK
    
    retrieved = get_response.json()
    assert retrieved['contradiction']['status'] == ContradictionStatus.IN_REVIEW.value
    assert retrieved['analysis'] is not None
    assert retrieved['analysis']['analyst'] == "AI_TEST_HARNESS"
    assert retrieved['analysis']['confidence'] == ContradictionSeverity.HIGH.value