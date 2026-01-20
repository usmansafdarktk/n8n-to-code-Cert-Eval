
import requests
import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())
from app.utils.auth import generate_token_for_user

def test_upload():
    # 1. Get Token
    email = "test-user@example.com"
    token = generate_token_for_user(email)
    
    # 2. Upload File
    url = "http://localhost:8000/api/files/upload"
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create a dummy pdf
    with open("test_doc.pdf", "wb") as f:
        f.write(b"%PDF-1.4 dummy content")
        
    files = {"file": ("test_doc.pdf", open("test_doc.pdf", "rb"), "application/pdf")}
    
    print(f"Submitting upload to {url}...")
    try:
        resp = requests.post(url, headers=headers, files=files)
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.text}")
        
        if resp.status_code == 200:
            data = resp.json()
            if "localhost" in data["signed_url"]:
                print("\n✅ SUCCESS: Fallback worked! URL is local.")
            else:
                print("\n✅ SUCCESS: Uploaded to GCS (Real URL).")
        else:
            print("\n❌ FAILED: API Error.")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_upload()
