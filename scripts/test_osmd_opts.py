import subprocess

for opt in ["drawChordSymbols: false", "drawChordSymbols: true"]:
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><script src="../app/static/js/opensheetmusicdisplay.min.js"></script></head>
<body>
    <pre id="stack"></pre>
    <div id="osmdCanvas"></div>
    <script>
        window.addEventListener('DOMContentLoaded', async () => {{
            const stack = document.getElementById('stack');
            try {{
                const container = document.getElementById('osmdCanvas');
                const osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay(container, {{
                    autoResize: false, backend: 'svg', {opt}
                }});
                const xml = document.getElementById('xml').textContent;
                await osmd.load(xml);
                osmd.render();
                stack.textContent = 'SUCCESS_{opt}';
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
    with open("scripts/test_opt.html", "w", encoding="utf-8") as f:
        f.write(html)
    res = subprocess.run([
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--headless=new", "--disable-gpu", "--virtual-time-budget=5000",
        "--allow-file-access-from-files", "--dump-dom",
        "file:///C:/Users/ADMIN/Documents/MELODYX/scripts/test_opt.html"
    ], capture_output=True, text=True, encoding="utf-8")
    for line in res.stdout.splitlines():
        if '<pre id="stack">' in line:
            print(f"Option {opt}: {line.strip()}")
            break
