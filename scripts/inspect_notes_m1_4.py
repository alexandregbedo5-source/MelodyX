import sqlite3
import json

db = sqlite3.connect("melodyx.db")
db.row_factory = sqlite3.Row
row = db.execute("SELECT result_json FROM analysis_results WHERE analysis_id = 'an_be261202d301'").fetchone()
data = json.loads(row["result_json"])
notes = data["music"]["notes"]

print(f"Total notes: {len(notes)}")
for m_idx in range(1, 5):
    m_notes = [n for n in notes if n.get("measure") == m_idx]
    print(f"\n--- Measure {m_idx} ({len(m_notes)} notes) ---")
    for n in sorted(m_notes, key=lambda x: (x.get("hand", "right"), x.get("beat_position", 0))):
        print(f"  Hand={n.get('hand')}, Beat={n.get('beat_position'):.2f}, Pitch={n.get('pitch')}, Dur={n.get('duration'):.2f}s")
