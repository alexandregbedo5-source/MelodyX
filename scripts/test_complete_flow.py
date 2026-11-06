import os
import requests
import time
import subprocess

s = requests.Session()
r = s.get("http://127.0.0.1:5000/")
print("Index status:", r.status_code)
sid = s.cookies.get("melodyx_sid")
print("Session ID:", sid)

# Upload DADJU
mp3 = r"C:\Users\ADMIN\OneDrive\Music\DADJU - Ma Faute (Audio Officiel) - DADJU-instrumental.mp3"
with open(mp3, "rb") as f:
    r_up = s.post(
        "http://127.0.0.1:5000/api/audio/upload",
        files={"file": ("DADJU-Ma-Faute-instrumental.mp3", f, "audio/mpeg")}
    )
print("Upload status:", r_up.status_code, r_up.json())
assert r_up.status_code == 202
aid = r_up.json()["analysis_id"]

# Poll for completion
for i in range(40):
    time.sleep(3)
    r_an = s.get(f"http://127.0.0.1:5000/api/analysis/{aid}")
    if r_an.status_code == 200:
        data = r_an.json()
        status = data.get("status")
        stage = data.get("stage")
        pct = data.get("progress")
        print(f"Poll {i+1}: status={status}, stage={stage}, progress={pct}")
        if status == "completed":
            print("\n🎉 ANALYSIS COMPLETED SUCCESSFULLY!")
            print("  Title:", data.get("original_filename"))
            m = data.get("music", {})
            print("  Key:", m.get("key"))
            print("  Tempo:", m.get("tempo_bpm"))
            print("  Notes:", len(m.get("notes", [])))
            print("  Measures:", len(m.get("measures", [])))
            
            # 1. Test PDF download
            r_pdf = s.get(f"http://127.0.0.1:5000/api/analysis/{aid}/pdf")
            print(f"  PDF response: {r_pdf.status_code}, size={len(r_pdf.content)} bytes")
            assert r_pdf.status_code == 200
            
            # Save PDF and check with pymupdf
            pdf_saved = f"scripts/test_{aid}.pdf"
            with open(pdf_saved, "wb") as f_pdf:
                f_pdf.write(r_pdf.content)
            import pymupdf
            doc = pymupdf.open(pdf_saved)
            print(f"  PDF page count: {doc.page_count}")
            # Render page 1 to image
            pix = doc[0].get_pixmap(dpi=150)
            pix.save(f"scripts/test_{aid}_p1.png")
            doc.close()
            print(f"  Saved page 1 image to scripts/test_{aid}_p1.png")
            
            # 2. Test Score MusicXML
            r_xml = s.get(f"http://127.0.0.1:5000/api/analysis/{aid}/score")
            print(f"  Score XML response: {r_xml.status_code}, size={len(r_xml.content)} bytes")
            assert r_xml.status_code == 200
            
            # 3. Test OSMD browser rendering
            escaped_xml = r_xml.text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
            html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><script src="../app/static/js/opensheetmusicdisplay.min.js"></script></head>
<body>
    <pre id="stack">INIT</pre>
    <div id="osmdCanvas" style="width: 1000px; min-height: 800px;"></div>
    <script>
        window.addEventListener('DOMContentLoaded', async () => {{
            const stack = document.getElementById('stack');
            try {{
                const container = document.getElementById('osmdCanvas');
                const osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay(container, {{
                    autoResize: false, backend: 'svg'
                }});
                const xml = `{escaped_xml}`;
                await osmd.load(xml);
                osmd.render();
                stack.textContent = 'OSMD_SUCCESS_SVGS_' + container.querySelectorAll('svg').length;
            }} catch(err) {{
                stack.textContent = 'ERR: ' + err.message + '\\n' + err.stack;
            }}
        }});
    </script>
</body>
</html>"""
            with open("scripts/test_osmd_verify.html", "w", encoding="utf-8") as f_html:
                f_html.write(html)
                
            res = subprocess.run([
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "--headless=new", "--disable-gpu", "--virtual-time-budget=6000",
                "--allow-file-access-from-files", "--dump-dom",
                "file:///C:/Users/ADMIN/Documents/MELODYX/scripts/test_osmd_verify.html"
            ], capture_output=True, text=True, encoding="utf-8")
            
            for line in res.stdout.splitlines():
                if 'OSMD_SUCCESS' in line or 'ERR:' in line:
                    print(f"  OSMD Browser Verification: {line.strip()}")
            break
        elif status == "failed":
            print(f"FAILED: {data.get('error_message')}")
            break
