"""Install without overwriting a differing existing skill."""
import argparse
from pathlib import Path
import os
import shutil
import sys
from datetime import datetime, timezone
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parent))
from distribution import files

ROOT=Path(__file__).resolve().parents[1]

def install(directory, upgrade=False, backup_directory=None):
    candidates=files();base=Path(directory).expanduser().resolve();groups={};differing=[]
    for path in candidates:
        rel=path.relative_to(ROOT)
        if len(rel.parts)>1:groups.setdefault(rel.parts[0],[]).append(path)
    # Preflight every target before writing any group.
    for name,paths in groups.items():
        target=base/name
        if not target.exists():continue
        if target.is_symlink():raise ValueError('Existing skill target must not be a symlink')
        if not target.is_dir():raise ValueError('Existing target is not a directory')
        if any(p.is_symlink() for p in target.rglob('*')):raise ValueError('Skill files must not be symlinks')
        actual={p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
        expected={p.relative_to(ROOT/name).as_posix() for p in paths}
        if actual!=expected or any(not (target/p.relative_to(ROOT/name)).is_file() or
                                  (target/p.relative_to(ROOT/name)).read_bytes()!=p.read_bytes() for p in paths):
            if not upgrade:raise ValueError('Existing installation differs; left unchanged: '+str(target))
            if actual-expected:raise ValueError('Custom files found; preserve and reconcile before upgrading: '+str(target))
            differing.append(name)
    # A user-requested upgrade backs up every affected skill before replacing a file.
    if differing:
        backup_base=Path(backup_directory).expanduser().resolve() if backup_directory else base.parent/'skill-backups'
        if backup_base==base or base in backup_base.parents:
            raise ValueError('Upgrade backups must be outside the active skills directory.')
        backup=backup_base/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
        backup.mkdir(parents=True)
        for name in differing:
            shutil.copytree(base/name,backup/name)
        print('Upgrade backup: '+str(backup))
    for name,paths in groups.items():
        target=base/name
        if target.exists() and name not in differing:print('Identical skill already installed: '+str(target));continue
        target.mkdir(parents=True,exist_ok=True)
        for path in paths:
            dest=target/path.relative_to(ROOT/name);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(path.read_bytes())
        print('Skill installed: '+str(target))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    default=Path(os.environ['CODEX_HOME'])/'skills' if os.environ.get('CODEX_HOME') else Path.home()/'.codex/skills'
    parser.add_argument('--directory',default=str(default))
    parser.add_argument('--upgrade',action='store_true',help='Explicitly replace a differing skill after backing it up')
    parser.add_argument('--backup-directory',help='Backup location outside the active skills directory')
    args=parser.parse_args()
    try:install(args.directory,args.upgrade,args.backup_directory)
    except (ValueError,OSError) as error:parser.exit(2,str(error)+'\n')
