from pathlib import Path
import os,hashlib,struct,subprocess,shutil,unittest
P=Path(__file__).resolve().parent
ns={'__file__':str(P/'test_patch.py')};exec((P/'test_patch.py').read_text().split('passed=[]')[0],ns)

class CheckedRollbackTests(unittest.TestCase):
 def test_snapshot_replacement_after_verification_refuses_and_retry(self):
  r,s,w,e=ns['fixture']()
  old=struct.pack('=12I',0x45454531,0,0x28,0x28,0x28,1,0,1,1000,0,0,6)
  other=struct.pack('=12I',0x45454531,0,0x28,0,0,0,0,0,1000,0,0,0)
  (s/'original.bin').write_bytes(old);(s/'original.bin').chmod(0o600)
  (s/'original.sha256').write_text(hashlib.sha256(old).hexdigest()+'  original.bin\n')
  (r/'replacement').write_bytes(other);model=r/'model';model.write_bytes(old+struct.pack('II',0,0));e['MODEL']=str(model)
  helper=r/'usr/libexec/mt3600be-eee-state';shutil.copy(P/'helper-test',helper);helper.chmod(0o755)
  service=r/'etc/init.d/mt3600be-wan-eee';service.write_text('#!/bin/sh\nif [ "$1" = stop ] && [ ! -e "$FIX/no-swap" ]; then cp "$FIX/replacement" "$FIX/etc/mt3600be-wan-eee/original.bin"; chmod 600 "$FIX/etc/mt3600be-wan-eee/original.bin"; fi\n');service.chmod(0o755)
  (s/'files.sha256').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f)+'\n' for f in [w,helper,service]))
  before=model.read_bytes();q=subprocess.run([str(w),'rollback'],env=e,capture_output=True,text=True)
  self.assertEqual(q.returncode,8,q.stderr);self.assertEqual(model.read_bytes(),before)
  self.assertTrue((s/'disabled').exists());self.assertFalse((s/'rolled-back').exists())
  (s/'original.bin').write_bytes(old);(s/'original.bin').chmod(0o600);(r/'no-swap').touch()
  q=subprocess.run([str(w),'rollback'],env=e,capture_output=True,text=True)
  self.assertEqual(q.returncode,0,q.stderr);self.assertTrue((s/'rolled-back').exists())
  self.assertEqual((s/'original.bin').read_bytes(),old)

 def test_wrong_digest_and_missing_hasher_refuse_before_ioctl(self):
  r,s,w,e=ns['fixture']();old=struct.pack('=12I',0x45454531,0,0x28,0x28,0x28,1,0,1,1000,0,0,6)
  f=r/'snapshot';f.write_bytes(old);f.chmod(0o600);model=r/'model';model.write_bytes(old+struct.pack('II',0,0));e['MODEL']=str(model);before=model.read_bytes()
  for digest,path in [('0'*64,e['PATH']),(hashlib.sha256(old).hexdigest(),str(r/'empty-path'))]:
   (r/'empty-path').mkdir(exist_ok=True)
   q=subprocess.run([str(P/'helper-test'),'restore-checked',str(f),digest],env=dict(e,PATH=path),capture_output=True)
   self.assertNotEqual(q.returncode,0);self.assertEqual(model.read_bytes(),before)

 def test_legacy_menu_replacement_refuses_then_retry(self):
  x={'__file__':str(P/'test-review-r2.py'),'__name__':'fixture_module'}
  exec(compile((P/'test-review-r2.py').read_text(),str(P/'test-review-r2.py'),'exec'),x)
  fixture=x['ReviewTests']();r,d,e,s=fixture.legacy_fixture()
  old=struct.pack('=12I',0x45454531,0,0x28,0x28,0x28,1,0,1,1000,0,0,6)
  other=struct.pack('=12I',0x45454531,0,0x28,0,0,0,0,0,1000,0,0,0)
  (s/'original.bin').write_bytes(old);(s/'original.bin').chmod(0o600);(s/'original.sha256').write_text(hashlib.sha256(old).hexdigest()+'  original.bin\n')
  (r/'replacement').write_bytes(other);model=r/'model';model.write_bytes(old+struct.pack('II',0,0));e['MODEL']=str(model)
  helper=d/'patch/eee-state';shutil.copy(P/'helper-test',helper);helper.chmod(0o755)
  (d/'patch/SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in (d/'patch').iterdir() if f.name!='SHA256SUMS'))
  service=r/'bin/fake-service';service.write_text('#!/bin/sh\nif [ "$1" = stop ] && [ ! -e "$FIX/no-swap" ]; then cp "$FIX/replacement" "$FIX/etc/mt3600be-wan-eee/original.bin"; chmod 600 "$FIX/etc/mt3600be-wan-eee/original.bin"; fi\nexit 0\n');service.chmod(0o755)
  before=model.read_bytes();q=x['call'](d,e,'rollback','--yes');self.assertEqual(q.returncode,8,q.stderr)
  self.assertEqual(model.read_bytes(),before);self.assertTrue((s/'disabled').exists());self.assertFalse((s/'rolled-back').exists())
  (s/'original.bin').write_bytes(old);(s/'original.bin').chmod(0o600);(r/'no-swap').touch()
  q=x['call'](d,e,'rollback','--yes');self.assertEqual(q.returncode,0,q.stderr)
  self.assertTrue((s/'rolled-back').exists());self.assertEqual((s/'original.bin').read_bytes(),old)

if __name__=='__main__':unittest.main(verbosity=2)
