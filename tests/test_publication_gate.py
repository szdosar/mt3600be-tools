from pathlib import Path
import unittest,subprocess,tempfile,shutil,json,hashlib,sys
R=Path(__file__).resolve().parents[1];A=Path(sys.argv[1]).resolve();sys.argv=sys.argv[:1]
class Gate(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.r=Path(self.t.name)/'repo';shutil.copytree(R,self.r,ignore=shutil.ignore_patterns('.git','__pycache__'))
 def rehash(self):
  for n in ['online.sha256','sources.sha256']:
   p=self.r/n;paths=[x.split('  ',1)[1] for x in p.read_text().splitlines()];p.write_text(''.join(hashlib.sha256((self.r/x).read_bytes()).hexdigest()+'  '+x+'\n' for x in paths))
 def run_gate(self):return subprocess.run([sys.executable,str(self.r/'tests/check_release.py'),str(A)],capture_output=True)
 def refused(self):
  self.assertNotEqual(self.run_gate().returncode,0);self.assertFalse((self.r/'tests/publication-audit.json').exists())
 def test_current_pass(self):self.assertEqual(self.run_gate().returncode,0)
 def test_failed_eee_test_stops_and_removes_stale_pass(self):
  p=self.r/'tests/eee-r4-validation.json';v=json.loads(p.read_text());v['passed']=False;p.write_text(json.dumps(v));self.rehash();self.refused()
 def test_source_changed_even_with_new_manifest_stops(self):
  p=self.r/'src/eee-v1.2-r4/tool/menu.sh';p.write_text(p.read_text()+'\n# changed\n');self.rehash();self.refused()
 def test_offline_digest_mismatch_stops(self):
  p=self.r/'docs/OFFLINE.md';s=p.read_text();h=json.loads((self.r/'catalog.json').read_text())[1]['sha256'];p.write_text(s.replace(h,'0'*64));self.rehash();self.refused()
 def test_download_catalog_mismatch_stops(self):
  p=self.r/'catalog.json';v=json.loads(p.read_text());v[0]['sha256']='0'*64;p.write_text(json.dumps(v));self.rehash();self.refused()
if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Gate))
 (R/'tests/gate-results.json').write_text(json.dumps({'passed':r.wasSuccessful(),'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'gate_sha256':hashlib.sha256((R/'tests/check_release.py').read_bytes()).hexdigest()},indent=2)+'\n');raise SystemExit(not r.wasSuccessful())
