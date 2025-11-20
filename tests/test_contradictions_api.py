import pytest
from httpx import AsyncClient
from fastapi import status
from src.api import app
from src.database import get_db, get_db_connection
from src.models import ContradictionCreate, ContradictionStatus, ContradictionSeverity, TriageAnalysisCreate
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

# Fixture for an in-memory database for API tests
@pytest.fixture
async def client():
    test_db_conn = get_db_connection(":memory:")
    
    # Initialize schema
    schema_path = Path(__file__).parent.parent / "data/schema.sql"
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    test_db_conn.executescript(schema_sql)
    test_db_conn.commit()

    def override_get_db():
        try:
            yield test_db_conn
        finally:
            test_db_conn.close()

    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_create_contradiction(client: AsyncClient):
    contradiction_data = ContradictionCreate(
        contradiction_id=str(uuid.uuid4()),
        contradiction_type="consistency",
        severity=ContradictionSeverity.HIGH,
        description="Test contradiction description",
        evidence={"field1": "value1"},
        entity_ids=[],
        detected_at=datetime.now(timezone.utc)
    )
    response = await client.post("/contradictions", json=contradiction_data.model_dump(mode='json'))
    assert response.status_code == status.HTTP_201_CREATED
    created_contradiction = response.json()
    assert created_contradiction['description'] == "Test contradiction description"
    assert created_contradiction['status'] == ContradictionStatus.PENDING.value

@pytest.mark.asyncio
async def test_list_contradictions(client: AsyncClient):
    # Create a few contradictions
    for i in range(2):
        contradiction_data = ContradictionCreate(
            contradiction_id=str(uuid.uuid4()),
            contradiction_type=f"type{i}",
            severity=ContradictionSeverity.LOW if i == 0 else ContradictionSeverity.MEDIUM,
            description=f"Description {i}",
            evidence={},
            entity_ids=[],
            detected_at=datetime.now(timezone.utc)
        )
        await client.post("/contradictions", json=contradiction_data.model_dump(mode='json'))
    
    response = await client.get("/contradictions")
    assert response.status_code == status.HTTP_200_OK
    contradictions = response.json()
    assert len(contradictions) >= 2

    # Test filter by status
    response_pending = await client.get("/contradictions", params={"status": ContradictionStatus.PENDING.value})
    assert response_pending.status_code == status.HTTP_200_OK
    pending_contradictions = response_pending.json()
    for con in pending_contradictions:
        assert con['status'] == ContradictionStatus.PENDING.value

@pytest.mark.asyncio
async def test_get_contradiction_details(client: AsyncClient):
    # Create a contradiction
    c_id = str(uuid.uuid4())
    contradiction_data = ContradictionCreate(
        contradiction_id=c_id,
        contradiction_type="temporal",
        severity=ContradictionSeverity.HIGH,
        description="Temporal paradox detected",
        evidence={"time_a": "past", "time_b": "future"},
        entity_ids=["entity-1", "entity-2"],
        detected_at=datetime.now(timezone.utc)
    )
    await client.post("/contradictions", json=contradiction_data.model_dump(mode='json'))

    response = await client.get(f"/contradictions/{c_id}")
    assert response.status_code == status.HTTP_200_OK
    details = response.json()
    assert details['contradiction']['contradiction_id'] == c_id
    assert details['contradiction']['evidence']['time_a'] == "past"
    assert "entity-1" in details['contradiction']['entity_ids']

@pytest.mark.asyncio
async def test_update_contradiction_status(client: AsyncClient):
    # Create a contradiction
    c_id = str(uuid.uuid4())
    contradiction_data = ContradictionCreate(
        contradiction_id=c_id,
        contradiction_type="spatial",
        severity=ContradictionSeverity.MEDIUM,
        description="Spatial anomaly",
        evidence={},
        entity_ids=[],
        detected_at=datetime.now(timezone.utc)
    )
    await client.post("/contradictions", json=contradiction_data.model_dump(mode='json'))

    # Update status to RESOLVED
    update_payload = {"status": ContradictionStatus.RESOLVED.value}
    response = await client.patch(f"/contradictions/{c_id}/status", json=update_payload)
    assert response.status_code == status.HTTP_200_OK
    updated_contradiction = response.json()
    assert updated_contradiction['status'] == ContradictionStatus.RESOLVED.value

@pytest.mark.asyncio
async def test_add_triage_analysis(client: AsyncClient):
    # Create a contradiction
    c_id = str(uuid.uuid4())
    contradiction_data = ContradictionCreate(
        contradiction_id=c_id,
        contradiction_type="logical",
        severity=ContradictionSeverity.LOW,
        description="Logical inconsistency",
        evidence={},
        entity_ids=[],
        detected_at=datetime.now(timezone.utc)
    )
    await client.post("/contradictions", json=contradiction_data.model_dump(mode='json'))

    # Add analysis
    analysis_data = TriageAnalysisCreate(
        contradiction_id=c_id,
        analyst="Test Analyst",
        analysis="Detailed analysis of inconsistency.",
        recommendation="Suggest review by lead DM.",
        confidence=ContradictionSeverity.MEDIUM # Use the Enum for confidence
    )
    response = await client.post(f"/contradictions/{c_id}/analysis", json=analysis_data.model_dump(mode='json'))
    assert response.status_code == status.HTTP_201_CREATED
    created_analysis = response.json()
    assert created_analysis['analyst'] == "Test Analyst"
    assert created_analysis['contradiction_id'] == c_id
    assert created_analysis['confidence'] == ContradictionSeverity.MEDIUM.value

    # Verify contradiction status updated to IN_REVIEW
    response_details = await client.get(f"/contradictions/{c_id}")
    assert response_details.status_code == status.HTTP_200_OK
    details = response_details.json()
    assert details['contradiction']['status'] == ContradictionStatus.IN_REVIEW.value
    assert details['analysis'] is not None
    assert details['analysis']['analyst'] == "Test Analyst"
