"""Test MELODYX pipeline on DADJU - Ma Faute (Audio Officiel) - DADJU-instrumental.mp3"""

import sys
import os
import time
import requests
from pathlib import Path

DADJU_PATH = r"C:\Users\ADMIN\OneDrive\Music\DADJU - Ma Faute (Audio Officiel) - DADJU-instrumental.mp3"
BASE_URL = "http://127.0.0.1:5000"

def main():
    if not os.path.isfile(DADJU_PATH):
        print("ERROR: File not found:", DADJU_PATH)
        sys.exit(1)

    file_size_mb = os.path.getsize(DADJU_PATH) / (1024 * 1024)
    print(f"File found: {DADJU_PATH}")
    print(f"Size: {file_size_mb:.2f} MB")

    session = requests.Session()
    session_id = "user_dadju_session_01"
    session.cookies.set("melodyx_sid", session_id)

    print("\n1. Uploading Dadju track to MELODYX API...")
    t0 = time.time()
    with open(DADJU_PATH, "rb") as f:
        files = {"audio": ("DADJU - Ma Faute (Audio Officiel) - DADJU-instrumental.mp3", f, "audio/mpeg")}
        resp = session.post(f"{BASE_URL}/api/audio/upload", files=files)

    if resp.status_code != 202:
        print("Upload failed:", resp.status_code, resp.text)
        sys.exit(1)

    data = resp.json()
    aid = data["analysis_id"]
    print(f"Upload accepted (202): Analysis ID = {aid}")

    print("\n2. Polling analysis progress...")
    max_wait = 180  # seconds
    poll_interval = 3
    elapsed = 0

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed = time.time() - t0

        r = session.get(f"{BASE_URL}/api/analysis/{aid}")
        if r.status_code != 200:
            print(f"Polling error ({r.status_code}):", r.text)
            continue

        info = r.json()
        status = info.get("status")
        stage = info.get("stage")
        progress = info.get("progress", 0.0)

        print(f"  [{elapsed:.1f}s] status={status}, stage={stage}, progress={progress*100:.0f}%")

        if status == "completed":
            print(f"\n🎉 Analysis COMPLETED in {elapsed:.1f} seconds!")
            result = info.get("result", {})
            music = result.get("music", {})
            tempo = music.get("tempo_bpm", {})
            key = music.get("key", {})
            time_sig = music.get("time_signature", {})
            notes = music.get("notes", [])
            measures = music.get("measures", [])
            chords = music.get("chords", [])

            print(f"\n--- RÉSULTATS MUSICAUX DADJU ---")
            print(f"• Titre original : {info.get('original_filename')}")
            print(f"• Durée : {info.get('duration_seconds'):.1f} s")
            print(f"• Tempo estimé : {tempo.get('value')} BPM (confiance: {tempo.get('confidence')})")
            print(f"• Tonalité estimée : {key.get('value')} (confiance: {key.get('confidence')})")
            print(f"• Signature rythmique : {time_sig.get('value')}")
            print(f"• Notes transcrites : {len(notes)} notes")
            print(f"• Mesures calculées : {len(measures)} mesures")
            print(f"• Segments d'accords : {len(chords)}")

            # Test artifact downloads
            print("\n3. Testing exports for Dadju analysis...")
            
            # MusicXML
            r_xml = session.get(f"{BASE_URL}/api/analysis/{aid}/score")
            print(f"• MusicXML export: HTTP {r_xml.status_code}, size: {len(r_xml.content)} bytes")
            assert r_xml.status_code == 200

            # MIDI
            r_mid = session.get(f"{BASE_URL}/api/analysis/{aid}/midi")
            print(f"• MIDI export: HTTP {r_mid.status_code}, size: {len(r_mid.content)} bytes")
            assert r_mid.status_code == 200

            # PDF Sheet Music Score
            r_pdf = session.get(f"{BASE_URL}/api/analysis/{aid}/pdf")
            print(f"• PDF Sheet Music export: HTTP {r_pdf.status_code}, size: {len(r_pdf.content)} bytes")
            assert r_pdf.status_code == 200
            assert r_pdf.content[:5] == b"%PDF-"

            # Save the Dadju PDF locally for inspection
            pdf_dest = os.path.join(os.path.dirname(__file__), "dadju_ma_faute_partition.pdf")
            with open(pdf_dest, "wb") as pf:
                pf.write(r_pdf.content)
            print(f"• Saved Dadju score PDF to: {pdf_dest}")

            # Audio Range 206
            headers = {"Range": "bytes=0-1023"}
            r_audio = session.get(f"{BASE_URL}/api/analysis/{aid}/audio", headers=headers)
            print(f"• Audio Range 206 stream: HTTP {r_audio.status_code}, content-range: {r_audio.headers.get('Content-Range')}")
            assert r_audio.status_code == 206

            print("\nALL EXPORTS VALIDATED SUCCESSFULLY FOR DADJU!")
            return aid

        elif status == "failed":
            print(f"\n❌ Pipeline failed: {info.get('error_code')} - {info.get('error_message')}")
            sys.exit(1)

    print("Timeout waiting for pipeline.")
    sys.exit(1)

if __name__ == "__main__":
    main()
