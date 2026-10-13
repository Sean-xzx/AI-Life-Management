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
            self.assertEqual(self.run_script('tools/install_skill.py','--directory',f).returncode,0)
            p=Path(f)/'ai-life-management/SKILL.md';p.write_text('existing user edit')
            self.assertEqual(self.run_script('tools/install_skill.py','--directory',f).returncode,2)
            self.assertEqual(p.read_text(),'existing user edit')

if __name__=='__main__':unittest.main()
