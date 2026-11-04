from pathlib import Path
import unittest,subprocess,os,struct,tempfile,hashlib,signal,shutil,json,sys
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P/'timer0-lab/tests'))
from test_timer0 import Transactions,snapshot,rehash
class RestoredCases(Transactions):
 # Only new tests below; run explicitly to avoid counting inherited tests twice.
 def test_r4_archive_then_link_change_new_baseline_preserves_old(self):
  r,d,e=self.fixture(True);state=r/'etc/mt3600be-wan-eee';state.mkdir();(state/'original.bin').write_bytes(snapshot());before=(state/'original.bin').read_bytes()
  self.assertEqual(call(d,e,'archive-incomplete','--yes').returncode,0)
  self.assertEqual(call(d,e,'install','--yes').returncode,4)
  (r/'zero').unlink();self.assertEqual(call(d,e,'install','--yes').returncode,0)
  old=list((r/'etc').glob('mt3600be-wan-eee-incomplete.*/transaction/original.bin'))
  self.assertEqual(len(old),1);self.assertEqual(old[0].read_bytes(),before);self.assertNotEqual((state/'original.bin').read_bytes(),before)
 def test_r4_incomplete_status_shows_current_without_restoring(self):
  r,d,e=self.fixture();state=r/'etc/mt3600be-wan-eee';state.mkdir();(state/'original.bin').write_bytes(snapshot());q=call(d,e,'status')
  self.assertEqual(q.returncode,1);self.assertIn('当前硬件',q.stdout);self.assertIn('archive-incomplete',q.stderr);self.assertEqual((state/'original.bin').read_bytes(),snapshot());self.assertNotIn('disable',(r/'actions').read_text())
 def test_r4_marker_alone_never_adopts(self):
  r,d,e=self.fixture();state=r/'etc/mt3600be-wan-eee';state.mkdir();(state/'installed').touch();(state/'original.bin').write_bytes(snapshot(1000))
  self.assertNotEqual(call(d,e,'install','--yes').returncode,0);self.assertEqual((state/'original.bin').read_bytes(),snapshot(1000));self.assertNotIn('disable',(r/'actions').read_text())
 def test_r4_archive_interrupt_after_rename_keeps_old_and_retry_safe(self):
  r,d,e=self.fixture();state=r/'etc/mt3600be-wan-eee';state.mkdir();(state/'original.bin').write_bytes(snapshot());h=d/'patch/eee-state';src=h.read_text();h.write_text(src.replace('mv "$2" "$3";;','mv "$2" "$3"; kill -KILL $$;;'));rehash(d)
  self.assertNotEqual(call(d,e,'archive-incomplete','--yes').returncode,0);self.assertFalse(state.exists());h.write_text(src);rehash(d)
  self.assertNotEqual(call(d,e,'archive-incomplete','--yes').returncode,0);self.assertEqual(call(d,e,'install','--yes').returncode,0)
  old=list((r/'etc').glob('mt3600be-wan-eee-incomplete.*/transaction/original.bin'));self.assertEqual(len(old),1);self.assertEqual(old[0].read_bytes(),snapshot())
from fixture import call
class Arm(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cc='/home/dosar/immortalwrt/staging_dir/toolchain-aarch64_cortex-a53_gcc-14.3.0_musl/bin/aarch64-openwrt-linux-musl-gcc';env=dict(os.environ,STAGING_DIR='/home/dosar/immortalwrt/staging_dir')
  subprocess.run([cc,'-Os','-Dioctl=test_ioctl','-Dsocket=test_socket','-Dfstat=test_fstat','-c',str(P/'patch-v1/eee-state.c'),'-o',str(P/'results/helper-arm.o')],check=True,env=env)
  subprocess.run([cc,'-static',str(P/'results/helper-arm.o'),str(P/'timer0-lab/tests/mock_ioctl.c'),'-o',str(P/'results/helper-arm')],check=True,env=env)
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.d=Path(self.t.name);self.m=self.d/'model';self.f=self.d/'snapshot';self.f.write_bytes(snapshot());self.f.chmod(0o600);self.m.write_bytes(snapshot()+struct.pack('II',0,0))
 def runh(self,*args,**env):return subprocess.run(['/usr/bin/qemu-aarch64-static',str(P/'results/helper-arm'),*map(str,args)],env=dict(os.environ,MODEL=str(self.m),**env),capture_output=True)
 def test_zero_refuses_without_write_arm(self):
  before=self.m.read_bytes()
  for c in ['0','1']:
   self.assertEqual(self.runh('assess',CARRIER=c).returncode,4);self.assertEqual(self.runh('disable').returncode,4)
  self.assertEqual(self.runh('restore-checked',self.f,hashlib.sha256(self.f.read_bytes()).hexdigest()).returncode,4);self.assertEqual(self.m.read_bytes(),before)
 def test_thousand_roundtrip_arm(self):
  blob=snapshot(1000);self.f.write_bytes(blob);self.m.write_bytes(blob+struct.pack('II',0,0));self.assertEqual(self.runh('assess',CARRIER='1').returncode,0);self.assertEqual(self.runh('disable').returncode,0);self.assertEqual(self.runh('restore-checked',self.f,hashlib.sha256(blob).hexdigest()).returncode,0);self.assertEqual(self.f.read_bytes(),blob)
 def test_interrupted_restore_retry_arm(self):
  blob=snapshot(1000);self.f.write_bytes(blob)
  for phase in ['after-seteee','after-miiwrite','after-nway']:
   self.m.write_bytes(blob+struct.pack('II',0,0));self.assertEqual(self.runh('disable').returncode,0);self.assertEqual(self.runh('restore-checked',self.f,hashlib.sha256(blob).hexdigest(),CRASH=phase).returncode,-signal.SIGKILL);self.assertEqual(self.runh('restore-checked',self.f,hashlib.sha256(blob).hexdigest()).returncode,0);self.assertEqual(self.f.read_bytes(),blob)
if __name__=='__main__':
 suite=unittest.TestSuite(RestoredCases(n) for n in dir(RestoredCases) if n.startswith('test_r4_'));suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(Arm));r=unittest.TextTestRunner(verbosity=2).run(suite)
 (P/'results/r4-tests.json').write_text(json.dumps({'passed':r.wasSuccessful(),'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'scope':'isolated and ARM user-mode ioctl simulation; no router'},indent=2)+'\n');raise SystemExit(not r.wasSuccessful())
