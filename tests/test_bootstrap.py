from pathlib import Path
import hashlib,json,subprocess,tempfile,unittest,os
D=Path(__file__).resolve().parents[1]
class Bootstrap(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='mt-bootstrap-test-');self.d=Path(self.temp.name);self.bin=self.d/'bin';self.bin.mkdir();(self.d/'tmp').mkdir();self.payload=self.d/'payload';self.payload.write_text('#!/bin/sh\necho executed > '+str(self.d/'executed')+'\n')
  self.source=(D/'bootstrap.sh').read_text();self.pin=hashlib.sha256((D/'install.sh').read_bytes()).hexdigest();self.assertIn(self.pin,self.source)
  p=self.bin/'curl';p.write_text('#!/usr/bin/python3\nfrom pathlib import Path\nimport sys\na=sys.argv;d=Path('+repr(str(self.d))+');p=Path(a[a.index("--output")+1]);p.write_bytes((d/"payload").read_bytes());sys.exit(22 if (d/"fail").exists() else 0)\n');p.chmod(0o755)
 def tearDown(self):self.temp.cleanup()
 def call(self,pin=True):
  s=self.source.replace('/tmp/mt3600be-launch.',str(self.d/'tmp/launch.'));s=s.replace('set -eu\n','set -eu\nPATH='+str(self.bin)+':/usr/bin:/bin;export PATH\n')
  if pin:s=s.replace(self.pin,hashlib.sha256(self.payload.read_bytes()).hexdigest())
  p=self.d/'bootstrap.sh';p.write_text(s);r=subprocess.run(['/bin/sh',str(p)],capture_output=True,text=True,timeout=10);self.assertEqual([],list((self.d/'tmp').iterdir()));return r
 def test_valid_and_cleanup(self):self.assertEqual(0,self.call().returncode);self.assertTrue((self.d/'executed').exists())
 def test_failed_download_never_executes_old(self):
  (self.d/'fail').touch();old=self.d/'install.sh';old.write_text('old script');self.assertNotEqual(0,self.call().returncode);self.assertFalse((self.d/'executed').exists());self.assertEqual('old script',old.read_text())
 def test_empty_even_with_matching_digest(self):self.payload.write_bytes(b'');self.assertNotEqual(0,self.call().returncode);self.assertFalse((self.d/'executed').exists())
 def test_bad_digest(self):self.assertNotEqual(0,self.call(False).returncode);self.assertFalse((self.d/'executed').exists())
 def test_syntax_error_even_with_matching_digest(self):self.payload.write_text('#!/bin/sh\nif then\n');self.assertNotEqual(0,self.call().returncode);self.assertFalse((self.d/'executed').exists())
 def test_failed_retry(self):
  (self.d/'fail').touch();self.assertNotEqual(0,self.call().returncode);(self.d/'fail').unlink();self.assertEqual(0,self.call().returncode)
 def test_catalog_and_README_pins(self):
  src=(D/'install.sh').read_text();readme=(D/'README.md').read_text();self.assertIn(self.pin,readme)
  for row in json.loads((D/'catalog.json').read_text()):
   for value in [row['sha256'],row['tag'],row['file'],'SIZE='+str(row['bytes'])]:self.assertIn(value,src)
  cmd=readme.split('```sh\n',1)[1].split('```',1)[0];self.assertEqual(0,subprocess.run(['/bin/sh','-n'],input=cmd,text=True,capture_output=True).returncode)
if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Bootstrap));o={'passed':r.wasSuccessful(),'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'bootstrap_sha256':hashlib.sha256((D/'bootstrap.sh').read_bytes()).hexdigest(),'launcher_sha256':hashlib.sha256((D/'install.sh').read_bytes()).hexdigest(),'no_router':True};(D/'tests/bootstrap-results.json').write_text(json.dumps(o,indent=2)+'\n');raise SystemExit(not r.wasSuccessful())
