
import requests
import os
import sys

# Load env vars
from dotenv import load_dotenv
load_dotenv()

OCR_URL = os.getenv("OCR_API_URL")

def test_ocr():
    print(f"Testing OCR URL: {OCR_URL}")
    
    if not OCR_URL:
        print("❌ Error: OCR_API_URL not set in .env")
        return

    # Create a minimal valid PDF
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog /Pages 2 0 R >>\n"
        b"endobj\n"
        b"2 0 obj\n"
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
        b"endobj\n"
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << >> /Contents 4 0 R >>\n"
        b"endobj\n"
        b"4 0 obj\n"
        b"<< /Length 21 >>\n"
        b"stream\n"
        b"BT /F1 24 Tf 100 700 Td (Hello World) Tj ET\n"
        b"endstream\n"
        b"endobj\n"
        b"xref\n"
        b"0 5\n"
        b"0000000000 65535 f \n"
        b"0000000010 00000 n \n"
        b"0000000060 00000 n \n"
        b"0000000117 00000 n \n"
        b"0000000224 00000 n \n"
        b"trailer\n"
        b"<< /Size 5 /Root 1 0 R >>\n"
        b"startxref\n"
        b"294\n"
        b"%%EOF"
    )
    import base64
    base64_content = base64.b64encode(pdf_content).decode('utf-8')
    
    variations = [
        {
            "desc": "Valid PDF - Original keys",
            "payload": {
                "Name": "test_valid.pdf",
                "StringBase64Content": base64_content,
                "BinaryContent": None
            }
        },
        {
            "desc": "Valid PDF - No BinaryContent",
            "payload": {
                "Name": "test_valid.pdf",
                "StringBase64Content": base64_content
            }
        }
    ]
    
    for v in variations:
        print(f"\n--- Testing: {v['desc']} ---")
        try:
            resp = requests.post(OCR_URL, json=v['payload'], headers={"Content-Type": "application/json"}, timeout=15)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text[:200]}")
            if resp.status_code == 200:
                print("✅ PASSED!")
                break
        except Exception as e:
            print(f"Failed: {e}")

if __name__ == "__main__":
    test_ocr()
