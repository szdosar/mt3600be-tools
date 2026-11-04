from pathlib import Path
import os,struct,subprocess,tempfile,unittest,shutil,hashlib,fcntl

P=Path(__file__).resolve().parent
DEFAULT_LEGACY=P.parent/'wan-eee-v1.1/patch-v1'
if not DEFAULT_LEGACY.exists():DEFAULT_LEGACY=P.parent/'mt3600be-eee-release-main-20261026/repairs/wan-eee-v1.1/patch-v1'
LEGACY=Path(os.environ.get('EEE_LEGACY_SOURCE',str(DEFAULT_LEGACY)))
ns={'__file__':str(P/'test_combined.py')};exec((P/'test_combined.py').read_text().split('for answer in')[0],ns)
mk,call=ns['mk'],ns['call']

class ReviewTests(unittest.TestCase):
 def test_import_path_replacement_after_open_never_imports_replacement(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);shim=d/'shim.c';shim.write_text('''#include <unistd.h>\n#include <stdlib.h>\n#include <stdio.h>\n#include <sys/stat.h>\nssize_t inject_read(int fd, void *buf, size_t n){ssize_t k=read(fd,buf,n);if(getenv("REPLACE"))rename(getenv("REPLACE"),getenv("SOURCE"));return k;}\nint inject_fstat(int fd, struct stat *s){int r=fstat(fd,s);if(!r)s->st_uid=0;return r;}\n''')
   obj=d/'helper.o';exe=d/'helper';subprocess.run(['cc','-Dread=inject_read','-Dfstat=inject_fstat','-c',str(P/'patch-v1/eee-state.c'),'-o',str(obj)],check=True)
   subprocess.run(['cc',str(obj),str(shim),'-o',str(exe)],check=True)
   old=struct.pack('=12I',0x45454531,0,0x28,0x28,0x28,1,0,1,1000,0,0,6)
   new=struct.pack('=12I',0x45454531,0,0x28,0,0,0,0,0,1000,0,0,0)
   source=d/'source';replacement=d/'replacement';destination=d/'snapshot';source.write_bytes(old);replacement.write_bytes(new);source.chmod(0o600);replacement.chmod(0o600)
   q=subprocess.run([str(exe),'import',str(source),str(destination)],env=dict(os.environ,SOURCE=str(source),REPLACE=str(replacement)),capture_output=True)
   self.assertEqual(source.read_bytes(),new)
   self.assertTrue((q.returncode==0 and destination.read_bytes()==old) or (q.returncode!=0 and not destination.exists()))

 def legacy_fixture(self):
  r,d,e=mk();state=r/'etc/mt3600be-wan-eee';state.mkdir();(state/'installed').touch();(state/'original.bin').write_bytes(b'original')
  names={'eee-state':'usr/libexec/mt3600be-eee-state','mt3600be-wan-eee':'usr/sbin/mt3600be-wan-eee','init':'etc/init.d/mt3600be-wan-eee','hotplug':'etc/hotplug.d/iface/98-mt3600be-wan-eee'}
  files=[]
  for n,dest in names.items():
   f=r/dest;shutil.copyfile(LEGACY/n,f);files.append(f)
  (state/'files.sha256').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f)+'\n' for f in files))
  (state/'original.sha256').write_text(hashlib.sha256(b'original').hexdigest()+'  original.bin\n')
  helper=d/'patch/eee-state';helper.write_text(helper.read_text().replace('case "$1" in','case "$1" in\n restore-checked) [ ! -e "$FIX/busy" ] || exit 75; if [ -e "$FIX/interrupt" ] && [ ! -e "$FIX/first" ]; then touch "$FIX/first"; exit 130; fi;;',1));rehash(d) if 'rehash' in globals() else None
  (d/'patch/SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in (d/'patch').iterdir() if f.name!='SHA256SUMS'))
  fake=r/'bin/fake-cli';fake.write_text('#!/bin/sh\necho "$1" >> "$FIX/cli-actions"\n');fake.chmod(0o755)
  service=r/'bin/fake-service';service.write_text('#!/bin/sh\nexit 0\n');service.chmod(0o755)
  menu=d/'menu.sh';s=menu.read_text().replace('CLI='+str(r)+'/usr/sbin/mt3600be-wan-eee','CLI='+str(fake)).replace(str(r)+'/etc/init.d/mt3600be-wan-eee enabled',str(service)+' enabled').replace(str(r)+'/etc/init.d/mt3600be-wan-eee running',str(service)+' running').replace(str(r)+'/etc/init.d/mt3600be-wan-eee disable',str(service)+' disable').replace(str(r)+'/etc/init.d/mt3600be-wan-eee stop',str(service)+' stop').replace(str(r)+'/etc/init.d/mt3600be-wan-eee enable',str(service)+' enable').replace(str(r)+'/etc/init.d/mt3600be-wan-eee start',str(service)+' start');menu.write_text(s)
  return r,d,e,state

 def test_legacy_status_rollback_and_repeat_do_not_replace_snapshot(self):
  r,d,e,state=self.legacy_fixture();old=(state/'original.bin').read_bytes()
  for action in ('status','rollback','rollback','enable','install'):
   q=call(d,e,action,'--yes');self.assertEqual(q.returncode,0,(action,q.stderr))
   self.assertEqual((state/'original.bin').read_bytes(),old)
  self.assertEqual((r/'usr/libexec/mt3600be-eee-state').read_bytes(),(LEGACY/'eee-state').read_bytes())

 def test_legacy_tamper_and_busy_lock_fail_closed(self):
  r,d,e,state=self.legacy_fixture();f=r/'usr/libexec/mt3600be-eee-state';f.write_bytes(f.read_bytes()+b'X')
  q=call(d,e,'rollback','--yes');self.assertNotEqual(q.returncode,0);self.assertFalse((r/'cli-actions').exists())
  self.assertEqual((state/'original.bin').read_bytes(),b'original')

 def test_legacy_lock_busy_rejects_then_retry_succeeds(self):
  r,d,e,state=self.legacy_fixture();cli=r/'bin/fake-cli'
  cli.write_text('#!/bin/sh\n[ ! -e "$FIX/busy" ] || exit 75\nexit 0\n');cli.chmod(0o755)
  (r/'busy').touch();q=call(d,e,'rollback','--yes');self.assertEqual(q.returncode,75)
  self.assertEqual((state/'original.bin').read_bytes(),b'original')
  (r/'busy').unlink();self.assertEqual(call(d,e,'rollback','--yes').returncode,0)

 def test_legacy_rollback_interruption_and_retry_keeps_baseline(self):
  r,d,e,state=self.legacy_fixture();(r/'interrupt').touch()
  self.assertEqual(call(d,e,'rollback','--yes').returncode,130)
  self.assertEqual((state/'original.bin').read_bytes(),b'original')
  self.assertTrue((state/'disabled').exists());self.assertFalse((state/'rolled-back').exists())
  self.assertEqual(call(d,e,'rollback','--yes').returncode,0)
  self.assertTrue((state/'rolled-back').exists())
  self.assertEqual((state/'original.bin').read_bytes(),b'original')

 def test_import_existing_target_and_symlink_are_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);blob=struct.pack('=12I',0x45454531,0,0x28,0x28,0x28,1,0,1,1000,0,0,6)
   source=d/'source';source.write_bytes(blob);source.chmod(0o600);dest=d/'existing';dest.write_bytes(b'keep')
   exe=str(P/'helper-test')
   self.assertNotEqual(subprocess.run([exe,'import',str(source),str(dest)],capture_output=True).returncode,0)
   self.assertEqual(dest.read_bytes(),b'keep')
   link=d/'link';link.symlink_to(source);other=d/'new'
   self.assertNotEqual(subprocess.run([exe,'import',str(link),str(other)],capture_output=True).returncode,0)
   self.assertFalse(other.exists())

if __name__=='__main__':unittest.main(verbosity=2)
