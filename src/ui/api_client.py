import requests

BASE_URL = "http://localhost:8000"

def run_query(payload: dict):
    return requests.post(f"{BASE_URL}/query", json=payload).json()

def create_entity(data: dict):
    return requests.post(f"{BASE_URL}/entities", json=data).json()