"""Deterministic bundle of preserved core and additive interaction layer."""
import argparse
from pathlib import Path
import zipfile
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from distribution import files

ROOT = Path(__file__).resolve().parents[1]

def build(destination):
    destination = Path(destination); destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in files():
            content = path.read_bytes()
            item=zipfile.ZipInfo(path.relative_to(ROOT).as_posix(),date_time=(1980,1,1,0,0,0))
            item.compress_type=zipfile.ZIP_DEFLATED;item.external_attr=0o100644<<16
            archive.writestr(item,content,compresslevel=9)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None: raise ValueError('Invalid archive')
    print('Package created: '+str(destination))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default=str(ROOT/'dist/ai-life-management.zip'))
    build(parser.parse_args().output)
