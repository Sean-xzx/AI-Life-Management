from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ProjectTests(unittest.TestCase):
    def run_script(self,path,*args):
        return subprocess.run([sys.executable,'-X','utf8',str(ROOT/path),*map(str,args)],capture_output=True,text=True,encoding='utf-8')
    def test_project_verifier(self):
        r=self.run_script('tools/verify_project.py');self.assertEqual(r.returncode,0,r.stderr)
    def test_demo(self):
        r=self.run_script('examples/demo.py');self.assertEqual(r.returncode,0,r.stderr);self.assertIn('revision=6',r.stdout)
    def test_daily_demo(self):
        r=self.run_script('examples/daily_demo.py');self.assertEqual(r.returncode,0,r.stderr);self.assertIn('events=4, idempotent=True',r.stdout)
    def test_package_is_deterministic(self):
        scratch=ROOT/'tmp';scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as f:
            self.assertTrue(Path(f).resolve().is_relative_to(scratch.resolve()))
            a=Path(f)/'a.zip';b=Path(f)/'b.zip'
            for p in (a,b):
                r=self.run_script('tools/package_skill.py','--output',p);self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(a.read_bytes(),b.read_bytes())
    def test_install_does_not_overwrite_different_files(self):
        scratch=ROOT/'tmp';scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as f:
            self.assertTrue(Path(f).resolve().is_relative_to(scratch.resolve()))
            r=self.run_script('tools/install_skill.py','--directory',f);self.assertEqual(r.returncode,0,r.stderr)
            adapter=Path(f)/'ai-life-management-easy/scripts/daily.py'
            clock=subprocess.run([sys.executable,str(adapter),'clock'],capture_output=True,text=True)
            self.assertEqual(clock.returncode,0,clock.stderr)
            self.assertEqual(self.run_script('tools/install_skill.py','--directory',f).returncode,0)
            p=Path(f)/'ai-life-management/SKILL.md';p.write_text('existing user edit')
            self.assertEqual(self.run_script('tools/install_skill.py','--directory',f).returncode,2)
            self.assertEqual(p.read_text(),'existing user edit')

    def test_explicit_upgrade_preserves_backup(self):
        scratch=ROOT/'tmp';scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as f:
            base=Path(f)/'skills';backups=Path(f)/'backups'
            self.assertEqual(self.run_script('tools/install_skill.py','--directory',base).returncode,0)
            old=base/'ai-life-management/SKILL.md';old.write_text('old installed version',encoding='utf-8')
            upgraded=self.run_script('tools/install_skill.py','--directory',base,'--upgrade','--backup-directory',backups)
            self.assertEqual(upgraded.returncode,0,upgraded.stderr)
            self.assertEqual(old.read_bytes(),(ROOT/'ai-life-management/SKILL.md').read_bytes())
            saved=list(backups.glob('*/ai-life-management/SKILL.md'))
            self.assertEqual(len(saved),1)
            self.assertEqual(saved[0].read_text(encoding='utf-8'),'old installed version')

    def test_upgrade_refuses_unexpected_custom_files(self):
        scratch=ROOT/'tmp';scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as f:
            base=Path(f)/'skills'
            self.assertEqual(self.run_script('tools/install_skill.py','--directory',base).returncode,0)
            custom=base/'ai-life-management/private-note.txt';custom.write_text('synthetic local edit')
            result=self.run_script('tools/install_skill.py','--directory',base,'--upgrade')
            self.assertEqual(result.returncode,2)
            self.assertEqual(custom.read_text(),'synthetic local edit')

if __name__=='__main__':unittest.main()
