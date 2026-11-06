import subprocess

with open("app/static/js/opensheetmusicdisplay.min.js", "r", encoding="utf-8") as f:
    js = f.read()

target = "s.graphicalVoiceEntries[0].parentVoiceEntry"
replacement = "(s.graphicalVoiceEntries[0]&&s.graphicalVoiceEntries[0].parentVoiceEntry)"
js_patched = js.replace(target, replacement)
print("Replaced", js.count(target), "times")

with open("scripts/osmd_patched.js", "w", encoding="utf-8") as f:
    f.write(js_patched)

html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><script src="osmd_patched.js"></script></head>
<body>
    <pre id="stack"></pre>
    <div id="osmdCanvas" style="width: 1000px; min-height: 800px;"></div>
    <script>
        window.addEventListener('DOMContentLoaded', async () => {{
            const stack = document.getElementById('stack');
            try {{
                const container = document.getElementById('osmdCanvas');
                const osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay(container, {{
                    autoResize: false, backend: 'svg'
                }});
                const xml = document.getElementById('xml').textContent;
                await osmd.load(xml);
                osmd.render();
                stack.textContent = 'PATCHED_SUCCESS_SVGS_' + container.querySelectorAll('svg').length;
            }} catch(e) {{
                stack.textContent = 'ERR: ' + e.message;
            }}
        }});
    </script>
    <script type="text/xml" id="xml">
""" + open(r"C:\Users\ADMIN\Documents\MELODYX\uploads\an_ce4fa2f6b6db\an_be261202d301.musicxml", encoding="utf-8").read() + """
    </script>
</body>
</html>"""

with open("scripts/test_patched.html", "w", encoding="utf-8") as f:
    f.write(html)

res = subprocess.run([
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "--headless=new", "--disable-gpu", "--virtual-time-budget=6000",
    "--allow-file-access-from-files", "--dump-dom",
    "file:///C:/Users/ADMIN/Documents/MELODYX/scripts/test_patched.html"
], capture_output=True, text=True, encoding="utf-8")

for line in res.stdout.splitlines():
    if '<pre id="stack">' in line:
        print(line.strip())
