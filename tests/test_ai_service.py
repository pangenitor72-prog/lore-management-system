# This is the NEW, SIMPLER test script.
# It lives in the root folder, next to .env and ai_service.py

from dotenv import load_dotenv
import os
import sys

# 1. Load the .env file from the current folder
load_dotenv()

# 2. We can import ai_service directly now
try:
    from ai_service import generate_content
except ImportError as e:
    print("--- ❌ CRITICAL ERROR ---")
    print(f"ImportError: {e}")
    print("This means a library is missing. Did you run:")
    print("pip install -U google-generativeai ollama python-dotenv")
    sys.exit(1)
except Exception as e:
    print(f"An unknown error occurred on import: {e}")
    sys.exit(1)


# 3. Define our test
def run_test():
    print("--- 🚀 KICKING OFF AI SERVICE TEST ---")
    
    # Check which backend is active
    backend = os.environ.get("AI_BACKEND", "local")
    print(f"Active backend from .env: {backend}\n")
    
    # Define a simple test prompt
    system_prompt = "You are a TTRPG assistant. Be brief."
    test_prompt = "Who is the most famous drow in all of fantasy?"

    # 4. Call our unified function
    try:
        response = generate_content(test_prompt, system_prompt)
        print("\n--- ✅ AI RESPONSE ---")
        print(response)
        print("---------------------\n")
        print(f"--- 👍 TEST SUCCEEDED (using {backend}) ---")
        
    except Exception as e:
        print(f"\n--- ❌ TEST FAILED (using {backend}) ---")
        print(f"An error occurred: {e}")
        print("---------------------\n")

# 5. Run the test
if __name__ == "__main__":
    run_test()
