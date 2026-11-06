import os
import subprocess

xml_path = r"C:\Users\ADMIN\Documents\MELODYX\uploads\an_ce4fa2f6b6db\an_be261202d301.musicxml"
with open(xml_path, "r", encoding="utf-8") as f:
    xml_content = f.read()

# Escape backticks and backslashes for JS template literal
escaped_xml = xml_content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>OSMD Test</title>
    <script src="../app/static/js/opensheetmusicdisplay.min.js"></script>
</head>
<body>
    <div id="status">INIT</div>
    <div id="osmdCanvas" style="width: 1000px; min-height: 800px;"></div>
    <script>
        window.addEventListener('DOMContentLoaded', async () => {{
            const status = document.getElementById('status');
            try {{
                status.textContent = 'STARTING';
                const container = document.getElementById('osmdCanvas');
                const osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay(container, {{
                    autoResize: false,
                    drawTitle: false,
                    drawSubtitle: false,
                    drawComposer: false,
                    drawLyricist: false,
                    drawPartNames: true,
                    backend: 'svg'
                }});
                status.textContent = 'OSMD_CREATED';
                const xml = `{escaped_xml}`;
                status.textContent = 'PARSING_XML_' + xml.length;
                await osmd.load(xml);
                status.textContent = 'XML_LOADED';
                osmd.render();
                const svgs = container.querySelectorAll('svg');
                status.textContent = 'RENDERED_SUCCESS_SVGS_' + svgs.length;
            }} catch(err) {{
                status.textContent = 'ERROR: ' + err.name + ': ' + err.message + ' | STACK: ' + err.stack;
            }}
        }});
    </script>
</body>
</html>
"""

test_html_path = r"C:\Users\ADMIN\Documents\MELODYX\scripts\test_osmd_direct.html"
with open(test_html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Generated test HTML, running Chrome headless...")
res = subprocess.run([
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "--headless=new",
    "--disable-gpu",
    "--virtual-time-budget=10000",
    "--allow-file-access-from-files",
    "--dump-dom",
    f"file:///{test_html_path.replace(os.sep, '/')}"
], capture_output=True, text=True, encoding="utf-8")

for line in res.stdout.splitlines():
    if 'id="status"' in line:
        print("Status div:", line)
    if '<svg' in line:
        print("Found SVG in output! Length of output:", len(res.stdout))
        break
else:
    print("No SVG found. Status check:")
    for line in res.stdout.splitlines():
        if "status" in line.lower() or "error" in line.lower():
            print("  ", line[:150])
