"""Check full analysis response structure."""
import requests
import json

s = requests.Session()
s.get("http://127.0.0.1:5000/")

r = s.get("http://127.0.0.1:5000/api/analysis/an_7a6f93ffc6bb")
data = r.json()
print("Status:", r.status_code)
print("Top-level keys:", list(data.keys()))
print()

# Print all non-null values (truncated)
for k, v in data.items():
    if v is not None:
        vstr = str(v)
        if len(vstr) > 200:
            vstr = vstr[:200] + "..."
        print(f"  {k}: {vstr}")
