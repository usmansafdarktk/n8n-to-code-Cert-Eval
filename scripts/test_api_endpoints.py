
import requests
import sys
import os

# Add project root to path to import utils
sys.path.append(os.getcwd())
from app.utils.auth import generate_token_for_user

BASE_URL = "http://localhost:8000"

def test_api():
    print(f"🚀 Starting API Test against {BASE_URL}...\n")
    
    # 1. Test Health (No Auth)
    try:
        resp = requests.get(f"{BASE_URL}/health")
        if resp.status_code == 200:
            print("✅ /health check passed")
        else:
            print(f"❌ /health check failed: {resp.status_code}")
    except Exception as e:
        print(f"❌ Could not connect to server: {e}")
        return

    # 2. Generate Token
    token = generate_token_for_user("tester@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    print("🔑 Generated test token")

    # 3. Test Certificate Types (With Auth)
    print("\nTesting /api/certificate-types:")
    resp = requests.get(f"{BASE_URL}/api/certificate-types", headers=headers)
    
    if resp.status_code == 200:
        types = resp.json()
        print(f"✅ Success! Found {len(types)} certificate types.")
        if types:
            print(f"   Sample: {types[0]['name_en']}")
    else:
        print(f"❌ Failed: {resp.status_code} - {resp.text}")

    # 4. Test Requests Summary
    print("\nTesting /api/requests/summary:")
    resp = requests.get(f"{BASE_URL}/api/requests/summary", headers=headers)
    
    if resp.status_code == 200:
        summaries = resp.json()
        print(f"✅ Success! Found {len(summaries)} requests.")
    else:
        print(f"❌ Failed: {resp.status_code} - {resp.text}")

    print("\n✨ Basic API connectivity test completed.")

if __name__ == "__main__":
    test_api()
