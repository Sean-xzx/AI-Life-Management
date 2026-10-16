"""Explicit distribution whitelist, verified against the current release hashes."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
EASY_FILES=['SKILL.md','agents/openai.yaml','assets/start.txt','references/interaction.md','scripts/daily.py']

def files():
    manifest=json.loads((ROOT/'docs/core-manifest.json').read_text(encoding='utf-8'))
    result=[]
    for relative,digest in manifest.items():
        path=ROOT/'ai-life-management'/relative
        if not path.resolve().is_relative_to((ROOT/'ai-life-management').resolve()):raise ValueError('Manifest path escapes skill')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Protected core changed: '+relative)
        result.append(path)
    result.extend(ROOT/'ai-life-management-easy'/p for p in EASY_FILES)
    result.append(ROOT/'RIGHTS.md')
    if not all(p.is_file() for p in result):raise ValueError('Distribution file missing')
    return sorted(result,key=lambda p:p.relative_to(ROOT).as_posix())
