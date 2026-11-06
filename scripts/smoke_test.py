"""Quick API smoke test for MELODYX."""
import urllib.request
import urllib.error
import json


BASE = "http://127.0.0.1:5000"


def get(path, cookie=None):
    req = urllib.request.Request(f"{BASE}{path}")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read()), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()), e.headers


def post(path, data=None, cookie=None, content_type=None):
    body = json.dumps(data).encode() if data else b""
    req = urllib.request.Request(f"{BASE}{path}", data=body, method="POST")
    if cookie:
        req.add_header("Cookie", cookie)
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read()), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()), e.headers


print("=" * 50)
print("MELODYX API Smoke Tests")
print("=" * 50)

# 1. Health
status, data, headers = get("/api/health")
assert status == 200
assert data["status"] == "ok"
assert "X-Request-Id" in headers
print(f"[PASS] GET /api/health -> {status}, X-Request-Id present")

# 2. Analyses list (empty, no session)
status, data, headers = get("/api/analyses")
assert status == 200
assert data == []
print(f"[PASS] GET /api/analyses -> {status}, empty list")

# 3. Analysis not found (no session)
status, data, headers = get("/api/analysis/an_doesnotexist")
assert status == 404
assert data["error"]["code"] == "not_found"
print(f"[PASS] GET /api/analysis/an_xxx -> {status}, not_found")

# 4. PDF returns 501
status, data, headers = get("/api/analysis/an_test/pdf")
assert status == 501
assert data["error"]["code"] == "not_implemented"
print(f"[PASS] GET /api/analysis/an_test/pdf -> {status}, not_implemented")

# 5. Upload no file
status, data, headers = post("/api/audio/upload")
assert status == 400
print(f"[PASS] POST /api/audio/upload (no file) -> {status}")

print()
print("All smoke tests passed!")
