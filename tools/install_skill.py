"""Install without overwriting a differing existing skill."""
import argparse
from pathlib import Path
import json
import os

ROOT=Path(__file__).resolve().parents[1]

def install(directory):
    manifest=json.loads((ROOT/'docs/core-manifest.json').read_text(encoding='utf-8'))
    target=Path(directory).expanduser()/'ai-life-management'
    source=ROOT/'ai-life-management'
    if target.exists():
        if not target.is_dir():raise ValueError('Existing target is not a directory')
        actual={p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
        expected=set(manifest)
        if actual!=expected or any((target/p).read_bytes()!=(source/p).read_bytes() for p in expected):
            raise ValueError('Existing installation differs; left unchanged: '+str(target))
        print('Identical skill already installed: '+str(target));return
    target.mkdir(parents=True)
    for relative in manifest:
        dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes((source/relative).read_bytes())
    print('Skill installed: '+str(target))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    default=Path(os.environ['CODEX_HOME'])/'skills' if os.environ.get('CODEX_HOME') else Path.home()/'.codex/skills'
    parser.add_argument('--directory',default=str(default))
    try:install(parser.parse_args().directory)
    except (ValueError,OSError) as error:parser.exit(2,str(error)+'\n')
