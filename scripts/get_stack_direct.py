import os
import subprocess

xml_path = r"C:\Users\ADMIN\Documents\MELODYX\uploads\an_ce4fa2f6b6db\an_be261202d301.musicxml"
with open(xml_path, "r", encoding="utf-8") as f:
    xml_content = f.read()

escaped_xml = xml_content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="../app/static/js/opensheetmusicdisplay.min.js"></script>
</head>
<body>
    <pre id="stack">INIT</pre>
    <div id="osmdCanvas" style="width: 1000px; min-height: 800px;"></div>
    <script>
        window.addEventListener('DOMContentLoaded', async () => {{
            const stack = document.getElementById('stack');
            try {{
                const container = document.getElementById('osmdCanvas');
                const osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay(container, {{
                    autoResize: false,
                    backend: 'svg'
                }});
                const xml = `{escaped_xml}`;
                await osmd.load(xml);
                osmd.render();
                stack.textContent = 'SUCCESS_SVGS_' + container.querySelectorAll('svg').length;
            }} catch(err) {{
                stack.textContent = 'ERR: ' + err.message + '\\nSTACK:\\n' + (err.stack || 'NO_STACK');
            }}
        }});
    </script>
</body>
</html>
"""

with open("scripts/test_stack_direct.html", "w", encoding="utf-8") as f:
    f.write(html)

res = subprocess.run([
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "--headless=new",
    "--disable-gpu",
    "--virtual-time-budget=6000",
    "--allow-file-access-from-files",
    "--dump-dom",
    "file:///C:/Users/ADMIN/Documents/MELODYX/scripts/test_stack_direct.html"
], capture_output=True, text=True, encoding="utf-8")

in_pre = False
for line in res.stdout.splitlines():
    if '<pre id="stack">' in line:
        in_pre = True
    if in_pre:
        print(line)
        if '</pre>' in line:
            break
