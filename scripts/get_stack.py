import subprocess

html = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><script src="../app/static/js/opensheetmusicdisplay.min.js"></script></head>
<body>
    <pre id="stack"></pre>
    <div id="osmdCanvas"></div>
    <script>
        window.addEventListener('DOMContentLoaded', async () => {
            try {
                const container = document.getElementById('osmdCanvas');
                const osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay(container, {
                    autoResize: false, backend: 'svg'
                });
                const resp = await fetch('http://127.0.0.1:5000/api/analysis/an_be261202d301/score');
                const xml = await resp.text();
                await osmd.load(xml);
                osmd.render();
                document.getElementById('stack').textContent = 'SUCCESS';
            } catch(e) {
                document.getElementById('stack').textContent = e.stack || e.message;
            }
        });
    </script>
</body>
</html>"""

with open("scripts/get_stack.html", "w", encoding="utf-8") as f:
    f.write(html)

res = subprocess.run([
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "--headless=new",
    "--disable-gpu",
    "--virtual-time-budget=6000",
    "--allow-file-access-from-files",
    "--dump-dom",
    "file:///C:/Users/ADMIN/Documents/MELODYX/scripts/get_stack.html"
], capture_output=True, text=True, encoding="utf-8")

print("Result:")
for line in res.stdout.splitlines():
    if '<pre id="stack">' in line:
        print(line)
