"""Test DADJU upload end-to-end."""
import requests
import time

s = requests.Session()

# 1. Visit index to get session cookie
r = s.get("http://127.0.0.1:5000/")
print("Index:", r.status_code)
print("Cookie after index:", s.cookies.get("melodyx_sid"))

# 2. Upload DADJU file
mp3 = r"C:\Users\ADMIN\OneDrive\Music\DADJU - Ma Faute (Audio Officiel) - DADJU-instrumental.mp3"
with open(mp3, "rb") as f:
    r = s.post(
        "http://127.0.0.1:5000/api/audio/upload",
        files={"file": ("DADJU-Ma-Faute-instrumental.mp3", f, "audio/mpeg")},
    )
print("Upload:", r.status_code, r.json())
print("Cookie after upload:", s.cookies.get("melodyx_sid"))

if r.status_code == 202:
    aid = r.json()["analysis_id"]
    # 3. Poll for completion
    for i in range(40):
        time.sleep(3)
        r2 = s.get(f"http://127.0.0.1:5000/api/analysis/{aid}")
        if r2.status_code == 200:
            data = r2.json()
            status = data.get("status")
            stage = data.get("stage")
            progress = data.get("progress")
            print(f"Poll {i+1}: status={status}, stage={stage}, progress={progress}")
            if status in ("completed", "failed"):
                if status == "completed":
                    print("SUCCESS! Analysis completed.")
                    m = data.get("result", {}).get("music", {})
                    print(f"  Key: {m.get('key')}")
                    print(f"  Tempo: {m.get('tempo_bpm')}")
                    print(f"  Measures: {len(m.get('measures', []))}")
                    print(f"  Chords: {len(m.get('chords', []))}")
                    # Test PDF
                    r3 = s.get(f"http://127.0.0.1:5000/api/analysis/{aid}/pdf")
                    print(f"  PDF: {r3.status_code}, size={len(r3.content)} bytes")
                    # Test score
                    r4 = s.get(f"http://127.0.0.1:5000/api/analysis/{aid}/score")
                    print(f"  Score: {r4.status_code}")
                    # Test audio
                    r5 = s.get(f"http://127.0.0.1:5000/api/analysis/{aid}/audio")
                    print(f"  Audio: {r5.status_code}")
                else:
                    print(f"FAILED: {data.get('error_message')}")
                break
        else:
            print(f"Poll {i+1}: HTTP {r2.status_code}")
else:
    print("Upload failed!")
