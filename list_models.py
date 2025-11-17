# list_models.py
# This script will connect to Google and print all models
# your API key has permission to use.

from dotenv import load_dotenv
import google.generativeai as genai
import os

# 1. Load the .env file
load_dotenv()
print("--- Loading .env file ---")

# 2. Configure with your API key
try:
    API_KEY = os.environ["GOOGLE_API_KEY"]
    genai.configure(api_key=API_KEY)
except Exception as e:
    print(f"Error: Could not configure API key. Is it in your .env? {e}")
    exit()

print("--- Successfully configured API key ---")
print("--- Fetching available models... ---")

# 3. List all models
for m in genai.list_models():
  # We only care about models that can be used for generateContent
  if 'generateContent' in m.supported_generation_methods:
    print(m.name)

print("--- End of list ---")