import zipfile
from xml.etree import ElementTree as ET

path = r"docs/prop_desemp.docx"
with zipfile.ZipFile(path) as z:
    xml = z.read('word/document.xml')

ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
root = ET.fromstring(xml)

paras = []
for p in root.findall('.//w:p', ns):
    texts = [t.text for t in p.findall('.//w:t', ns) if t.text]
    if texts:
        paras.append(''.join(texts))

out_path = r"docs/prop_desemp_extracted.txt"
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(paras))
print(out_path)
