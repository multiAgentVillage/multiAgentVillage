"""Download the pinned documentation renderer in bounded HTTPS ranges."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import time
import urllib.request

URL = 'https://repo.maven.apache.org/maven2/net/sourceforge/plantuml/plantuml/1.2024.8/plantuml-1.2024.8.jar'
TARGET = Path(__file__).resolve().parent / 'plantuml-1.2024.8.jar'
TOTAL = 21924397
CHUNK = 1024 * 1024


def fetch(index):
    lo = index * CHUNK
    hi = min(TOTAL - 1, lo + CHUNK - 1)
    for attempt in range(3):
        try:
            req = urllib.request.Request(URL, headers={'Range': f'bytes={lo}-{hi}'})
            with urllib.request.urlopen(req, timeout=30) as res:
                if res.status != 206:
                    raise RuntimeError(f'Expected partial response, got {res.status}')
                data = res.read()
                if len(data) != hi - lo + 1:
                    raise RuntimeError('Incomplete range')
                return index, data
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1)


if __name__ == '__main__':
    n = (TOTAL + CHUNK - 1) // CHUNK
    with ThreadPoolExecutor(max_workers=4) as pool:
        pieces = dict(pool.map(fetch, range(n)))
    data = b''.join(pieces[i] for i in range(n))
    assert len(data) == TOTAL
    digest = urllib.request.urlopen(URL + '.sha1', timeout=30).read().decode().strip()
    assert hashlib.sha1(data).hexdigest() == digest
    TARGET.write_bytes(data)
    print('PlantUML JAR length and upstream checksum verified:', len(data))
