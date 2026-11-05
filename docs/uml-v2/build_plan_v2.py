"""Validate current v2 and synchronize the section 3.11 extract.
The v2 document is the source of truth; never reconstruct it from v1.
"""
from pathlib import Path
import hashlib
import re
ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'project-plan.md'
PLAN = ROOT.parent / 'project-plan-v2.md'
EXPECTED_V1_SHA256 = 'ffd1925354feaa2122a87133b6d623e42fac2b7121c4832cec2f61eb3432f0f6'

def build():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED_V1_SHA256
    text = PLAN.read_text(encoding='utf-8')
    assert text.count('```') % 2 == 0
    for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text):
        if not link.startswith(('http:', 'https:', '#')):
            assert (PLAN.parent / link).is_file(), link
    start,end = text.index('### 3.11 '),text.index('## 4. ')
    # The extract lives inside uml-v2/, one level below the full plan.
    section = text[start:end].replace('](uml-v2/', '](').rstrip() + '\n'
    (ROOT / 'design-section.md').write_text(section,encoding='utf-8',newline='\n')
    print('Validated current v2; synchronized section 3.11; no plan overwritten.')

if __name__ == '__main__':
    build()
