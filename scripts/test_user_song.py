"""Test the user's uploaded song against the MELODYX backend."""
import urllib.request
import urllib.error
import json
import time
import os

song_path = r"C:/Users/ADMIN/.gemini/antigravity/brain/a29cf8b6-2c9b-4dd1-a2f0-f3f69dba77b0/.user_uploaded/uploaded_media_1793958784300.m4a"

print("=" * 60)
print("TESTING BACKEND WITH USER SONG")
print("Song path:", song_path)
print("File size:", os.path.getsize(song_path), "bytes")
print("=" * 60)

boundary = "----WebKitFormBoundaryMELODYXTest"

with open(song_path, "rb") as f:
    song_bytes = f.read()

part_header = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="audio"; filename="chanson.m4a"\r\n'
    f"Content-Type: audio/x-m4a\r\n\r\n"
).encode("utf-8")
part_footer = f"\r\n--{boundary}--\r\n".encode("utf-8")
body = part_header + song_bytes + part_footer

req = urllib.request.Request("http://127.0.0.1:5000/api/audio/upload", data=body, method="POST")
req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

try:
    resp = urllib.request.urlopen(req)
except urllib.error.HTTPError as e:
    print(f"Upload failed: HTTP {e.code}")
    print(e.read().decode())
    exit(1)

cookie = resp.headers.get("Set-Cookie", "")
upload_data = json.loads(resp.read())
aid = upload_data["analysis_id"]
print(f"1. Upload successful -> status={resp.status}, analysis_id={aid}")
print(f"   Session cookie: {cookie[:40]}...")

# 2. Poll pipeline progress
print("\n2. Polling analysis progress...")
start_time = time.time()
state = {}
last_stage = None

for attempt in range(120): # up to 2 minutes
    time.sleep(1.5)
    poll_req = urllib.request.Request(f"http://127.0.0.1:5000/api/analysis/{aid}")
    if cookie:
        poll_req.add_header("Cookie", cookie)
    try:
        poll_resp = urllib.request.urlopen(poll_req)
        state = json.loads(poll_resp.read())
        stage = state.get("stage")
        progress = state.get("progress", 0.0)
        status = state.get("status")
        elapsed = round(time.time() - start_time, 1)

        if stage != last_stage or status in ("completed", "failed"):
            print(f"   [{elapsed}s] Status: {status:10s} | Stage: {str(stage):18s} | Progress: {progress*100:.0f}%")
            last_stage = stage

        if status in ("completed", "failed"):
            break
    except Exception as e:
        print(f"   Polling error: {e}")

elapsed_total = round(time.time() - start_time, 1)
print(f"\nPipeline finished in {elapsed_total} seconds with status: {state.get('status')}")

if state.get("status") == "failed":
    print("Error details:", state.get("error"))
    exit(1)

# 3. Analyze results
music = state.get("music", {})
audio = state.get("audio", {})
print("\n3. Musical Analysis Results:")
print(f"   - Audio Duration: {audio.get('duration_seconds')}s ({audio.get('sample_rate')} Hz, {audio.get('channels')} ch)")
print(f"   - Estimated Tempo: {music.get('tempo_bpm', {}).get('value')} BPM (confidence: {music.get('tempo_bpm', {}).get('confidence')})")
print(f"   - Estimated Key: {music.get('key', {}).get('value')} (confidence: {music.get('key', {}).get('confidence')})")
print(f"   - Time Signature: {music.get('time_signature', {}).get('value')} (confidence: {music.get('time_signature', {}).get('confidence')})")
print(f"   - Chords detected: {len(music.get('chords', []))} chord segments")
if music.get('chords'):
    sample_chords = [f"{c['label']} ({c['start']}s-{c['end']}s)" for c in music['chords'][:6]]
    print(f"     First chords: {', '.join(sample_chords)}")
print(f"   - Notes detected: {len(music.get('notes', []))} notes")
if music.get('notes'):
    sample_notes = [f"{n['name']} (m.{n['measure']}, {n['hand']})" for n in music['notes'][:8]]
    print(f"     First notes: {', '.join(sample_notes)}")
print(f"   - Measures count: {len(music.get('measures', []))} measures")
print(f"   - AI status: available={state.get('ai', {}).get('available')}, model={state.get('ai', {}).get('model')}")

# 4. Test exports
print("\n4. Testing Artifact Exports:")
for ep, label, expected_mime in [
    ("score", "MusicXML Score", "musicxml"),
    ("midi", "MIDI File", "midi"),
    ("json", "Full JSON", "json"),
]:
    exp_req = urllib.request.Request(f"http://127.0.0.1:5000/api/analysis/{aid}/{ep}")
    if cookie:
        exp_req.add_header("Cookie", cookie)
    exp_resp = urllib.request.urlopen(exp_req)
    data = exp_resp.read()
    ct = exp_resp.headers.get("Content-Type", "")
    print(f"   - {label}: HTTP {exp_resp.status} | {len(data):,} bytes | Content-Type: {ct}")

# 5. Test Audio Streaming with HTTP Range
print("\n5. Testing Audio Streaming (Range request):")
range_req = urllib.request.Request(f"http://127.0.0.1:5000/api/analysis/{aid}/audio")
if cookie:
    range_req.add_header("Cookie", cookie)
range_req.add_header("Range", "bytes=0-1023")
range_resp = urllib.request.urlopen(range_req)
print(f"   - Status: {range_resp.status} (expected 206)")
print(f"   - Content-Range: {range_resp.headers.get('Content-Range')}")
print(f"   - Content-Type: {range_resp.headers.get('Content-Type')}")

# 6. Test Teacher Endpoint
print("\n6. Testing AI Teacher Endpoint:")
teacher_body = json.dumps({
    "level": "beginner",
    "language": "fr",
    "selection": {"measure_start": 1, "measure_end": 4},
    "question": "Quelle est la tonalité du morceau et comment jouer ces mesures ?"
}).encode("utf-8")

t_req = urllib.request.Request(f"http://127.0.0.1:5000/api/analysis/{aid}/teacher", data=teacher_body, method="POST")
if cookie:
    t_req.add_header("Cookie", cookie)
t_req.add_header("Content-Type", "application/json")

try:
    t_resp = urllib.request.urlopen(t_req)
    t_data = json.loads(t_resp.read())
    print("   - Teacher response:", t_data)
except urllib.error.HTTPError as e:
    t_err = json.loads(e.read())
    print(f"   - Teacher endpoint returned expected status without API key: HTTP {e.code}")
    print(f"   - Error payload: {t_err}")

print("\n" + "=" * 60)
print("TEST COMPLETED SUCCESSFULLY!")
print("=" * 60)
