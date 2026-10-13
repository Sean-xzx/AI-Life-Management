"""Install without overwriting a differing existing skill."""
import argparse
from pathlib import Path
import os
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from distribution import files

ROOT=Path(__file__).resolve().parents[1]

def install(directory):
    candidates=files();base=Path(directory).expanduser();groups={}
    for path in candidates:
        rel=path.relative_to(ROOT)
        if len(rel.parts)>1:groups.setdefault(rel.parts[0],[]).append(path)
    # Preflight every target before writing any group.
    for name,paths in groups.items():
        target=base/name
        if not target.exists():continue
        if not target.is_dir():raise ValueError('Existing target is not a directory')
        actual={p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
        expected={p.relative_to(ROOT/name).as_posix() for p in paths}
        if actual!=expected or any((target/p.relative_to(ROOT/name)).read_bytes()!=p.read_bytes() for p in paths):
            raise ValueError('Existing installation differs; left unchanged: '+str(target))
    for name,paths in groups.items():
        target=base/name
        if target.exists():print('Identical skill already installed: '+str(target));continue
        target.mkdir(parents=True)
        for path in paths:
            dest=target/path.relative_to(ROOT/name);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(path.read_bytes())
        print('Skill installed: '+str(target))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    default=Path(os.environ['CODEX_HOME'])/'skills' if os.environ.get('CODEX_HOME') else Path.home()/'.codex/skills'
    parser.add_argument('--directory',default=str(default))
    try:install(parser.parse_args().directory)
    except (ValueError,OSError) as error:parser.exit(2,str(error)+'\n')
