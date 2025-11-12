from models import ContradictionCreate

test = ContradictionCreate(
    contradiction_id="123",
    contradiction_type="temporal",
    severity="HIGH",
    description="Example contradiction for validation test",
    evidence={"note": "test evidence"}
)

print(test)
