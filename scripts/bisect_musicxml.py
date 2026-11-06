import xml.etree.ElementTree as ET
import subprocess
import os

xml_path = r"C:\Users\ADMIN\Documents\MELODYX\uploads\an_ce4fa2f6b6db\an_be261202d301.musicxml"
tree = ET.parse(xml_path)
root = tree.getroot()

parts = root.findall("part")

def test_num_measures(num_m):
    # clone tree
    test_tree = ET.parse(xml_path)
    test_root = test_tree.getroot()
    for p in test_root.findall("part"):
        measures = p.findall("measure")
        for m in measures[num_m:]:
            p.remove(m)
    
    xml_str = ET.tostring(test_root, encoding="utf-8").decode("utf-8")
    escaped_xml = xml_str.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
    
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><script src="../app/static/js/opensheetmusicdisplay.min.js"></script></head>
<body>
    <div id="status">INIT</div>
    <div id="osmdCanvas" style="width: 1000px; min-height: 800px;"></div>
    <script>
        window.addEventListener('DOMContentLoaded', async () => {{
            const status = document.getElementById('status');
            try {{
                const container = document.getElementById('osmdCanvas');
                const osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay(container, {{
                    autoResize: false, backend: 'svg'
                }});
                const xml = `{escaped_xml}`;
                await osmd.load(xml);
                osmd.render();
                const svgs = container.querySelectorAll('svg');
                status.textContent = 'SUCCESS_SVGS_' + svgs.length;
            }} catch(err) {{
                status.textContent = 'ERR: ' + err.message;
            }}
        }});
    </script>
</body>
</html>"""
    test_file = r"C:\Users\ADMIN\Documents\MELODYX\scripts\temp_bisect.html"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(html)
        
    res = subprocess.run([
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--headless=new",
        "--disable-gpu",
        "--virtual-time-budget=5000",
        "--allow-file-access-from-files",
        "--dump-dom",
        f"file:///{test_file.replace(os.sep, '/')}"
    ], capture_output=True, text=True, encoding="utf-8")
    
    for line in res.stdout.splitlines():
        if 'id="status"' in line:
            return line.strip()
    return "NO_STATUS"

print("Testing 1 measure:", test_num_measures(1))
print("Testing 2 measures:", test_num_measures(2))
print("Testing 5 measures:", test_num_measures(5))
