import asyncio
import os
from dotenv import load_dotenv
from src.lms.db.neo4j_adapter import Neo4jDatabase
from src.lms.agents.auditor_agent import AuditorAgent

load_dotenv()

DB_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
DB_AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# THE LIE - Test contradiction detection
# We know from the graph:
# - Vulture Clan uses technology (Gyrocopters, machines)
# - Vulture Clan is ENEMY_OF Lead Corps, Smoker Legion
# Let's submit contradictory claims
CONTRADICTING_SUBMISSION = """
The Vulture Clan is a pacifist group that hates technology. 
They refuse to use machines or flying devices. 
They are currently best friends and close allies with the Lead Corps.
The Smoker Legion considers Vulture Clan their greatest ally.
"""

# A safe submission that adds new info without contradicting
SAFE_SUBMISSION = """
The Vulture Clan recently discovered an ancient Roost in the northern wastes.
Their Scrap-Shamans are studying new machine spirit rituals.
Buzzard, their famous pilot, is training new recruits.
"""

async def run_semantic_audit():
    print("👮 Starting Semantic Auditor Agent...")
    db = Neo4jDatabase(DB_URI, DB_AUTH)
    await db.connect()
    
    auditor = AuditorAgent(db, GEMINI_KEY)
    
    # Test 1: Contradicting submission
    print("\n" + "=" * 60)
    print("🧪 TEST 1: CONTRADICTING SUBMISSION")
    print("=" * 60)
    print(f"\n📄 Submission:\n{CONTRADICTING_SUBMISSION.strip()}\n")
    
    result1 = await auditor.audit_submission(CONTRADICTING_SUBMISSION)
    
    print("\n🚨 AUDIT RESULT:")
    print(f"   Status: {result1['status']}")
    print(f"   Entities Checked: {result1['entities_checked']}")
    
    if result1['contradictions']:
        print(f"   Contradictions Found: {len(result1['contradictions'])}")
        for i, c in enumerate(result1['contradictions'], 1):
            print(f"\n   [{i}] {c.get('severity', 'UNKNOWN')} SEVERITY")
            print(f"       Claim: {c.get('claim', 'N/A')}")
            print(f"       Truth: {c.get('truth', 'N/A')}")
            print(f"       Why: {c.get('explanation', 'N/A')}")
    else:
        print(f"   Notes: {result1['notes']}")

    # Test 2: Safe submission
    print("\n" + "=" * 60)
    print("🧪 TEST 2: SAFE SUBMISSION (New Info, No Conflict)")
    print("=" * 60)
    print(f"\n📄 Submission:\n{SAFE_SUBMISSION.strip()}\n")
    
    result2 = await auditor.audit_submission(SAFE_SUBMISSION)
    
    print("\n✅ AUDIT RESULT:")
    print(f"   Status: {result2['status']}")
    print(f"   Entities Checked: {result2['entities_checked']}")
    print(f"   Notes: {result2['notes']}")
    
    await db.close()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"Test 1 (Should be CONTRADICTION): {result1['status']}")
    print(f"Test 2 (Should be SAFE): {result2['status']}")

if __name__ == "__main__":
    asyncio.run(run_semantic_audit())
