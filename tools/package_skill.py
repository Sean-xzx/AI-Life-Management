"""Deterministic distribution of the eight original skill files only."""
import argparse
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def build(destination):
    manifest = json.loads((ROOT/'docs/core-manifest.json').read_text(encoding='utf-8'))
    destination = Path(destination); destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for relative,digest in sorted(manifest.items()):
            content = (ROOT/'ai-life-management'/relative).read_bytes()
            if hashlib.sha256(content).hexdigest() != digest:
                raise ValueError('Core differs from preserved baseline: '+relative)
            item=zipfile.ZipInfo('ai-life-management/'+relative,date_time=(1980,1,1,0,0,0))
            item.compress_type=zipfile.ZIP_DEFLATED;item.external_attr=0o100644<<16
            archive.writestr(item,content,compresslevel=9)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None: raise ValueError('Invalid archive')
    print('Package created: '+str(destination))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default=str(ROOT/'dist/ai-life-management.zip'))
    build(parser.parse_args().output)
