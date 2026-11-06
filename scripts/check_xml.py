import xml.etree.ElementTree as ET

try:
    tree = ET.parse('uploads/an_ce4fa2f6b6db/an_be261202d301.musicxml')
    print('XML is valid well-formed XML!')
    root = tree.getroot()
    print('Root tag:', root.tag)
    parts = root.findall('part')
    print('Number of parts:', len(parts))
    for p in parts:
        measures = p.findall('measure')
        print(f"Part {p.attrib.get('id')}: {len(measures)} measures")
except Exception as e:
    print('XML Parse error:', e)
