"""Verify preserved core, local links, topic coverage and README commands."""
from pathlib import Path
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]

def check():
    manifest=json.loads((ROOT/'docs/core-manifest.json').read_text(encoding='utf-8'))
    assert len(manifest)==8,'Expected original eight skill files'
    for relative,digest in manifest.items():
        p=ROOT/'ai-life-management'/relative
        assert hashlib.sha256(p.read_bytes()).hexdigest()==digest,'Core changed: '+relative
    docs=[ROOT/'README.md',ROOT/'README.zh-CN.md',ROOT/'RIGHTS.md',*list((ROOT/'docs').glob('*.md')),*list((ROOT/'ai-life-management').rglob('*.md')),*list((ROOT/'ai-life-management-easy').rglob('*.md'))]
    for p in docs:
        text=p.read_text(encoding='utf-8')
        assert '[TODO:' not in text,'Unfinished scaffold: '+p.name
        for target in re.findall(r'\]\(([^)]+)\)',text):
            if target.startswith(('http://','https://','#')):continue
            path=target.split('#')[0]
            assert (p.parent/path).exists(),f'Broken link: {p.name} -> {path}'
    a=(ROOT/'README.md').read_text(encoding='utf-8');b=(ROOT/'README.zh-CN.md').read_text(encoding='utf-8')
    # Shell commands must stay identical; narrative language and tree labels may differ.
    commands=lambda s:re.findall(r'```(?:sh|powershell)\n(.*?)```',s,re.S)
    assert commands(a)==commands(b),'README command drift'
    assert '[简体中文](README.zh-CN.md)' in a and '[English](README.md)' in b
    for name in ('theory.md','source-index.md'):
        s=(ROOT/'ai-life-management/references'/name).read_text(encoding='utf-8')
        assert all(f'| A{i:02} |' in s for i in range(1,19))
        assert all(f'| K{i:02} |' in s for i in range(1,25))
    for marker in ['Python **3.12**','3.12.14','revision=6','No open-source license']:
        if marker=='No open-source license':assert marker in (ROOT/'RIGHTS.md').read_text(encoding='utf-8')
        else:assert marker in a and marker in b,marker
    print('Project verification passed')

if __name__=='__main__':check()
