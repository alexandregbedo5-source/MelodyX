"""Live integration test against running Flask dev server."""
import urllib.request
import json
import time

boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
wav_path = "C:/Users/ADMIN/Documents/MELODYX/fixtures/demo_piano.wav"

with open(wav_path, "rb") as f:
    file_bytes = f.read()

part_header = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="audio"; filename="demo.wav"\r\n'
    f"Content-Type: audio/wav\r\n\r\n"
).encode("utf-8")
part_footer = f"\r\n--{boundary}--\r\n".encode("utf-8")
body = part_header + file_bytes + part_footer

req = urllib.request.Request("http://127.0.0.1:5000/api/audio/upload", data=body, method="POST")
req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

resp = urllib.request.urlopen(req)
cookie = resp.headers.get("Set-Cookie", "")
upload_data = json.loads(resp.read())
aid = upload_data["analysis_id"]
print(f"Upload OK: status={resp.status}, analysis_id={aid}")

# Poll status until complete
state = {}
for attempt in range(25):
    time.sleep(1.0)
    poll_req = urllib.request.Request(f"http://127.0.0.1:5000/api/analysis/{aid}")
    poll_req.add_header("Cookie", cookie)
    poll_resp = urllib.request.urlopen(poll_req)
    state = json.loads(poll_resp.read())
    print(f"Poll #{attempt+1}: status={state['status']}, stage={state.get('stage')}, progress={state.get('progress')}")
    if state["status"] in ("completed", "failed"):
        break

assert state.get("status") == "completed", f"Analysis did not complete: {state}"
print("Pipeline completed successfully!")
print(f"Notes detected: {len(state['music']['notes'])}")
print(f"Key estimated: {state['music']['key']}")
print(f"Tempo estimated: {state['music']['tempo_bpm']}")

# Test exports
for ep, name in [("score", "MusicXML"), ("midi", "MIDI"), ("json", "JSON")]:
    exp_req = urllib.request.Request(f"http://127.0.0.1:5000/api/analysis/{aid}/{ep}")
    exp_req.add_header("Cookie", cookie)
    exp_resp = urllib.request.urlopen(exp_req)
    content = exp_resp.read()
    print(f"Export {name} OK: size={len(content)} bytes, content_type={exp_resp.headers.get('Content-Type')}")

# Test Audio Range request
range_req = urllib.request.Request(f"http://127.0.0.1:5000/api/analysis/{aid}/audio")
range_req.add_header("Cookie", cookie)
range_req.add_header("Range", "bytes=0-100")
range_resp = urllib.request.urlopen(range_req)
print(f"Audio playback Range OK: status={range_resp.status}, Content-Range={range_resp.headers.get('Content-Range')}")
print("ALL LIVE END-TO-END CHECKS PASSED!")
