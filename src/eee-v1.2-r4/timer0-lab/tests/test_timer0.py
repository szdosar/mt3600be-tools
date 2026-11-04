from pathlib import Path
import ctypes as C,unittest,subprocess,os,struct,tempfile,hashlib,signal,fcntl,time,shutil,json
from fixture import mk,call,baseline
P=Path(__file__).resolve().parents[1]
class Eee(C.Structure):
 _fields_=[(n,C.c_uint) for n in ['cmd','supported','advertised','lp_advertised','enabled','active','tx','timer','r0','r1']]
lib=C.CDLL(str(P/'tests/driver-lab.so'))
lib.observe.argtypes=[C.POINTER(Eee)]
def snapshot(timer=0):return struct.pack('=12I',0x45454531,0,0x28,0x28,0,0,0,1,timer,0,0,6)
def rehash(d):(d/'patch/SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in (d/'patch').iterdir() if f.name!='SHA256SUMS'))
class DriverEvidence(unittest.TestCase):
 def setUp(self):lib.reset(0,1)
 def test_get_reads_zero_without_write(self):
  e=Eee();self.assertEqual(lib.observe(C.byref(e)),0);self.assertEqual((e.timer,e.tx,lib.cache(),lib.writes()),(0,1,1,0))
 def test_zero_write_sets_hidden_mode(self):
  self.assertEqual(lib.apply(0,0,0),0);self.assertEqual(lib.raw(),0x11240001);self.assertEqual(lib.cache(),0)
 def test_visible_roundtrip_does_not_restore_raw_or_cache(self):
  before=Eee();lib.observe(C.byref(before));lib.apply(0,0,0);lib.apply(0,1,0);after=Eee();lib.observe(C.byref(after))
  self.assertEqual((before.timer,before.tx,before.enabled),(after.timer,after.tx,after.enabled));self.assertNotEqual(lib.raw(),0);self.assertNotEqual(lib.cache(),1)
 def test_distinct_hidden_states_have_same_timer(self):
  seen=[]
  for raw in [0,1,0x11240000,0x11240001]:
   lib.reset(raw,1);e=Eee();lib.observe(C.byref(e));seen.append(e.timer)
  self.assertEqual(seen,[0]*4)
 def test_canonical_thousand_roundtrip(self):
  lib.reset(0x11240100,1);lib.apply(0,0,1000);lib.apply(0,1,1000);self.assertEqual((lib.raw(),lib.cache()),(0x11240100,1))
 def test_get_failure_does_not_write(self):
  lib.fault(0,0,1);self.assertEqual(lib.observe(C.byref(Eee())),-5);self.assertEqual(lib.writes(),0)
 def test_phy_failure_before_changes_no_mac_write(self):
  lib.fault(1,0,0);self.assertEqual(lib.apply(0,0,0),-5);self.assertEqual((lib.raw(),lib.cache(),lib.writes()),(0,1,0))
 def test_error_after_phy_change_is_not_noop(self):
  lib.fault(0,1,0);self.assertEqual(lib.apply(0,0,0),-5);self.assertEqual(lib.writes(),0);self.assertEqual(lib.adv(),0)
 def test_binary_getter_extracts_only_timer_bits(self):
  t=(P/'evidence/mtk_get_eee.txt').read_text();self.assertIn('ubfx\tx0, x0, #8, #8',t);self.assertIn('#0x3e8',t)
 def test_binary_setter_constructs_zero_mode_constant(self):
  t=(P/'evidence/mtk_set_eee.txt').read_text();self.assertIn('#0x11240000',t);self.assertIn('mov\tw0, #0x1',t);self.assertIn('csel\tw21, w2, w0, hi',t);self.assertIn('strb\tw19, [x22, #2378]',t)
class CompiledHelper(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name);self.blob=snapshot();self.f=self.p/'original.bin';self.f.write_bytes(self.blob);self.f.chmod(0o600);self.m=self.p/'model';self.m.write_bytes(self.blob+struct.pack('II',0,0));self.env=dict(os.environ,MODEL=str(self.m))
 def runh(self,*args,legacy=False,**env):return subprocess.run([str(P/'tests'/('legacy-helper-host' if legacy else 'candidate-helper-host')),*map(str,args)],env=dict(self.env,**env),capture_output=True,text=True)
 def test_save_zero_is_read_only_and_exact(self):
  before=self.m.read_bytes();out=self.p/'saved';self.assertEqual(self.runh('save',out).returncode,0);self.assertEqual(out.read_bytes(),self.blob);self.assertEqual(self.m.read_bytes(),before)
 def test_saved_destination_not_overwritten(self):
  before=self.f.read_bytes();self.assertNotEqual(self.runh('save',self.f).returncode,0);self.assertEqual(self.f.read_bytes(),before)
 def test_validate_zero_still_rejected(self):self.assertEqual(self.runh('validate',self.f).returncode,4)
 def test_restore_zero_rejected_before_write(self):
  before=self.m.read_bytes();q=self.runh('restore-checked',self.f,hashlib.sha256(self.blob).hexdigest());self.assertEqual(q.returncode,4);self.assertEqual(self.m.read_bytes(),before)
 def test_candidate_disable_zero_rejected_before_write(self):
  before=self.m.read_bytes();self.assertEqual(self.runh('disable').returncode,4);self.assertEqual(self.m.read_bytes(),before)
 def test_legacy_disable_did_not_guard_current_zero(self):
  before=self.m.read_bytes();self.assertEqual(self.runh('disable',legacy=True).returncode,0);self.assertNotEqual(self.m.read_bytes(),before)
 def test_assess_carrier_down_and_up_never_authorize_zero(self):
  before=self.m.read_bytes()
  for c in ['0','1']:
   q=self.runh('assess',CARRIER=c);self.assertEqual(q.returncode,4);self.assertIn('carrier='+c,q.stdout);self.assertEqual(self.m.read_bytes(),before)
 def test_thousand_restore_after_each_interrupt(self):
  blob=snapshot(1000);self.f.write_bytes(blob)
  for phase in ['after-seteee','after-miiwrite','after-nway']:
   self.m.write_bytes(blob+struct.pack('II',0,0));self.assertEqual(self.runh('disable').returncode,0)
   self.assertEqual(self.runh('restore-checked',self.f,hashlib.sha256(blob).hexdigest(),CRASH=phase).returncode,-signal.SIGKILL)
   self.assertEqual(self.runh('restore-checked',self.f,hashlib.sha256(blob).hexdigest()).returncode,0);self.assertEqual(self.f.read_bytes(),blob)
class Transactions(unittest.TestCase):
 def fixture(self,zero=False):
  r,d,e=mk();self.addCleanup(shutil.rmtree,r);h=d/'patch/eee-state'
  s=h.read_text().replace('case "$1" in','case "$1" in\n assess) echo assess >> "$FIX/actions"; [ ! -e "$FIX/zero" ] || exit 4;;\n archive) mv "$2" "$3";;',1)
  h.write_text(s);rehash(d)
  if zero:(r/'zero').touch()
  return r,d,e
 def test_restored_config_zero_defers_before_transaction(self):
  r,d,e=self.fixture(True);(r/'etc/config/network').chmod(0o664);before=baseline(r);q=call(d,e,'install','--yes');self.assertEqual(q.returncode,4);self.assertFalse((r/'etc/mt3600be-wan-eee').exists());self.assertEqual(baseline(r),before);self.assertEqual((r/'actions').read_text().splitlines(),['assess'])
 def test_repeat_zero_no_new_transaction(self):
  r,d,e=self.fixture(True)
  for _ in range(3):self.assertEqual(call(d,e,'install','--yes').returncode,4)
  self.assertFalse((r/'etc/mt3600be-wan-eee').exists())
 def test_later_supported_baseline_installs_keeps_config(self):
  r,d,e=self.fixture(True);before=baseline(r);self.assertEqual(call(d,e,'install','--yes').returncode,4);(r/'zero').unlink();q=call(d,e,'install','--yes');self.assertEqual(q.returncode,0,q.stderr);self.assertEqual(baseline(r),before)
 def test_old_incomplete_zero_record_not_replaced(self):
  r,d,e=self.fixture(True);s=r/'etc/mt3600be-wan-eee';s.mkdir();old=s/'original.bin';old.write_bytes(snapshot());self.assertNotEqual(call(d,e,'install','--yes').returncode,0);self.assertEqual(old.read_bytes(),snapshot());self.assertNotIn('save',(r/'actions').read_text());self.assertNotIn('disable',(r/'actions').read_text())
 def test_partial_restored_service_not_adopted(self):
  r,d,e=self.fixture();f=r/'etc/init.d/mt3600be-wan-eee';f.write_text('old restored service');q=call(d,e,'install','--yes');self.assertNotEqual(q.returncode,0);self.assertEqual(f.read_text(),'old restored service');self.assertFalse((r/'etc/mt3600be-wan-eee').exists())
 def test_busy_lock_then_safe_retry(self):
  r,d,e=self.fixture(True)
  with (r/'var/lock/mt3600be-wan-eee.lock').open('w') as f:
   fcntl.flock(f,fcntl.LOCK_EX);self.assertEqual(call(d,e,'install','--yes').returncode,75)
  self.assertEqual(call(d,e,'install','--yes').returncode,4);self.assertFalse((r/'etc/mt3600be-wan-eee').exists())
 def test_interrupt_after_assess_retry(self):
  r,d,e=self.fixture();f=d/'patch/install.sh';s=f.read_text();f.write_text(s.replace('umask 077','kill -KILL $$\numask 077',1));rehash(d);self.assertNotEqual(call(d,e,'install','--yes').returncode,0);self.assertFalse((r/'etc/mt3600be-wan-eee').exists());f.write_text(s);rehash(d);self.assertEqual(call(d,e,'install','--yes').returncode,0)
 def test_change_after_assess_saved_record_still_validated(self):
  r,d,e=self.fixture();h=d/'patch/eee-state';h.write_text(h.read_text().replace('printf original > "$2"','printf zero > "$2"'));rehash(d);self.assertNotEqual(call(d,e,'install','--yes').returncode,0);self.assertEqual((r/'etc/mt3600be-wan-eee/original.bin').read_text(),'zero');self.assertNotIn('disable',(r/'actions').read_text());self.assertNotEqual(call(d,e,'install','--yes').returncode,0)
 def test_archive_retry_does_not_normalize_old_zero(self):
  r,d,e=self.fixture(True);s=r/'etc/mt3600be-wan-eee';s.mkdir();(s/'original.bin').write_bytes(snapshot());self.assertEqual(call(d,e,'archive-incomplete','--yes').returncode,0);self.assertEqual(call(d,e,'install','--yes').returncode,4);a=list((r/'etc').glob('mt3600be-wan-eee-incomplete.*/transaction/original.bin'));self.assertEqual(len(a),1);self.assertEqual(a[0].read_bytes(),snapshot())
 def test_normal_repeat_and_rollback_only_owned_files(self):
  r,d,e=self.fixture();before=baseline(r);self.assertEqual(call(d,e,'install','--yes').returncode,0);old=(r/'etc/mt3600be-wan-eee/original.bin').read_bytes();self.assertEqual(call(d,e,'install','--yes').returncode,0);self.assertEqual(call(d,e,'rollback','--yes').returncode,0);self.assertEqual(baseline(r),before);self.assertEqual((r/'etc/mt3600be-wan-eee/original.bin').read_bytes(),old)
 def test_assess_read_error_creates_nothing(self):
  r,d,e=self.fixture();h=d/'patch/eee-state';h.write_text(h.read_text().replace('assess) echo','assess) exit 1; echo'));rehash(d);self.assertEqual(call(d,e,'install','--yes').returncode,1);self.assertFalse((r/'etc/mt3600be-wan-eee').exists());self.assertEqual((r/'phy').read_text(),'on\n')
 def test_two_actual_processes_assessment_lock_and_retry(self):
  r,d,e=self.fixture(True);h=d/'patch/eee-state';h.write_text(h.read_text().replace('assess) echo assess', 'assess) touch "$FIX/assess-ready"; while [ ! -e "$FIX/release" ]; do sleep .02; done; echo assess'));rehash(d)
  a=subprocess.Popen(['sh',str(d/'menu.sh'),'install','--yes'],env=e,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  try:
   for _ in range(200):
    if (r/'assess-ready').exists():break
    time.sleep(.01)
   self.assertTrue((r/'assess-ready').exists());self.assertEqual(call(d,e,'install','--yes').returncode,75)
   (r/'release').touch();a.communicate(timeout=5);self.assertEqual(a.returncode,4);self.assertEqual(call(d,e,'install','--yes').returncode,4);self.assertFalse((r/'etc/mt3600be-wan-eee').exists())
  finally:
   if a.poll() is None:a.kill();a.communicate()
 def test_kill_at_saved_record_checkpoints_never_overwrites(self):
  for needle in ['mkdir "$STATE"','"$DIR/eee-state" save "$STATE/original.bin"','"$DIR/eee-state" validate "$STATE/original.bin"','(cd "$STATE"; sha256sum original.bin > original.sha256)', ': > "$STATE/disabled"']:
   with self.subTest(point=needle):
    r,d,e=self.fixture();f=d/'patch/install.sh';s=f.read_text();self.assertIn(needle,s);f.write_text(s.replace(needle,needle+'; kill -KILL $$',1));rehash(d);self.assertNotEqual(call(d,e,'install','--yes').returncode,0)
    rec=r/'etc/mt3600be-wan-eee/original.bin';old=rec.read_bytes() if rec.exists() else None;f.write_text(s);rehash(d);self.assertNotEqual(call(d,e,'install','--yes').returncode,0);self.assertEqual(rec.read_bytes() if rec.exists() else None,old);self.assertNotIn('disable',(r/'actions').read_text());self.assertFalse((r/'enabled').exists())
 def test_disabled_complete_restored_transaction_not_reenabled(self):
  r,d,e=self.fixture();self.assertEqual(call(d,e,'install','--yes').returncode,0);self.assertEqual(call(d,e,'rollback','--yes').returncode,0);before=baseline(r);actions=(r/'actions').read_bytes();self.assertEqual(call(d,e,'install','--yes').returncode,0);self.assertEqual((r/'actions').read_bytes(),actions);self.assertFalse((r/'enabled').exists());self.assertEqual(baseline(r),before)
 def test_disabled_hardware_alone_is_not_installed(self):
  r,d,e=self.fixture();(r/'phy').write_text('off');q=call(d,e,'status');self.assertEqual(q.returncode,0);self.assertIn('未安装',q.stdout);self.assertIn('不等于补丁已安装',q.stdout);self.assertNotIn('save',(r/'actions').read_text());self.assertNotIn('disable',(r/'actions').read_text())
 def test_status_snapshot_only_explains_incomplete(self):
  r,d,e=self.fixture();s=r/'etc/mt3600be-wan-eee';s.mkdir();(s/'original.bin').write_bytes(snapshot());q=call(d,e,'status');self.assertNotEqual(q.returncode,0);self.assertIn('不完整事务',q.stderr);self.assertEqual((s/'original.bin').read_bytes(),snapshot());self.assertNotIn('save',(r/'actions').read_text());self.assertNotIn('disable',(r/'actions').read_text())
 def test_status_restored_orphan_file_is_not_fresh_install(self):
  r,d,e=self.fixture();f=r/'etc/init.d/mt3600be-wan-eee';f.write_text('restored');q=call(d,e,'status');self.assertNotEqual(q.returncode,0);self.assertIn('缺少事务记录',q.stderr);self.assertEqual(f.read_text(),'restored')
 def test_complete_service_files_without_original_never_claims_success(self):
  r,d,e=self.fixture();self.assertEqual(call(d,e,'install','--yes').returncode,0);(r/'etc/mt3600be-wan-eee/original.bin').unlink();q=call(d,e,'status');self.assertNotEqual(q.returncode,0);self.assertNotIn('mode=enabled',q.stdout)
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__)))
 (P/'results/timer0-tests.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'hardware_tested':False,'timer_zero_write_enabled':False},indent=2)+'\n')
 raise SystemExit(not result.wasSuccessful())
