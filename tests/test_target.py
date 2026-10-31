#!/usr/bin/env python3
"""No router/network: exact firmware ARM BusyBox/ucode/fs under QEMU+bwrap.
Only uname, curl and the component payload are synthetic. Rootfs is public firmware.
Set MT3600BE_TEST_ROOTFS to the unpacked supported original image.
"""
from pathlib import Path
import os,subprocess,tempfile,hashlib,json,time,signal,unittest,shutil
D=Path(__file__).resolve().parents[1]
ROOT=Path(os.environ['MT3600BE_TEST_ROOTFS']).resolve()
class Target(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='mt-target-');self.r=Path(self.tmp.name)
  for n in ['bin','usr/bin','usr/sbin','usr/lib','sbin','lib','dev','proc','tmp/sysinfo','var/lock','root','etc','fixture','host','arm']:(self.r/n).mkdir(parents=True,exist_ok=True)
  self.write('tmp/sysinfo/board_name','glinet,gl-mt3600be\n');self.write('etc/glversion','4.9.1-op25\n')
  self.write('etc/openwrt_release',"DISTRIB_RELEASE='25.12.5'\nDISTRIB_REVISION='r33051-f5dae5ece4'\nDISTRIB_TARGET='mediatek/filogic'\nDISTRIB_ARCH='aarch64_cortex-a53'\n")
  for n in ['sh','flock','sha256sum','mktemp','ln','cat','grep','mkdir','rm','cp','chmod','id','sleep','touch']:
   app='ash' if n=='sh' else n
   self.write('bin/'+n,'#!/host/busybox sh\nexec /qemu /arm/busybox '+app+' "$@"\n',0o755)
  self.write('bin/uname','#!/bin/sh\necho 6.12.94\n',0o755)
  self.write('usr/bin/ucode','''#!/bin/sh
[ ! -e /fixture/meta-fail ] || { echo '0:0:600'; exit 9; }
if [ -e /fixture/identity-fail ]; then
 case "$3" in identity*) echo fake; exit 9;; esac
fi
exec /qemu /arm-ucode "$@"
''',0o755)
  self.write('bin/curl','''#!/bin/sh
out=
while [ "$#" -gt 0 ]; do
 if [ "$1" = --output ]; then shift; out=$1; fi
 shift
done
[ -n "$out" ] || exit 2
touch /fixture/download-started
if [ -e /fixture/kill-download ]; then
 rm /fixture/kill-download
 printf partial > "$out"
 kill -KILL "$PPID"
 exit 22
fi
if [ -e /fixture/interrupt-download ]; then
 rm /fixture/interrupt-download
 kill -TERM "$PPID"
 sleep 0.1
 exit 22
fi
while [ -e /fixture/hold-download ]; do sleep 0.05; done
if [ -e /fixture/download-fail ]; then echo broken > "$out"; exit 22; fi
cp /fixture/payload "$out"
''',0o755)
  self.write('fixture/payload','''#!/bin/sh
echo "$*" >> /fixture/actions
touch /fixture/child-started
if [ -e /fixture/interrupt-child ]; then kill -TERM "$PPID"; fi
while [ -e /fixture/hold-child ]; do sleep 0.05; done
[ ! -e /fixture/child-fail ] || exit 23
''')
  self.payload=self.r/'fixture/payload';src=(D/'install.sh').read_text()
  self.digest=hashlib.sha256(self.payload.read_bytes()).hexdigest()
  for row in json.loads((D/'catalog.json').read_text()):src=src.replace(row['sha256'],self.digest).replace('SIZE='+str(row['bytes']),'SIZE='+str(self.payload.stat().st_size))
  self.write('fixture/install.sh',src)
  # Synthetic prior config/backup sentinel: no actual router material.
  self.write('etc/old-config','synthetic-config\n',0o664);self.write('root/old-backup','synthetic-backup\n',0o600)
  self.base=['bwrap','--unshare-all','--die-with-parent','--uid','0','--gid','0','--bind',str(self.r),'/', '--ro-bind',str(ROOT/'lib'),'/lib','--ro-bind',str(ROOT/'usr/lib'),'/usr/lib','--ro-bind',str(ROOT/'bin/busybox'),'/arm/busybox','--ro-bind',str(ROOT/'usr/bin/ucode'),'/arm-ucode','--ro-bind','/usr/bin/qemu-aarch64-static','/qemu','--ro-bind','/usr/bin/busybox','/host/busybox','--proc','/proc','--dev','/dev','--clearenv','--setenv','PATH','/usr/sbin:/usr/bin:/sbin:/bin','--chdir','/']
 def write(self,n,s,mode=0o600):p=self.r/n;p.write_text(s);p.chmod(mode)
 def tearDown(self):
  for n,text,mode in [('etc/old-config','synthetic-config\n',0o664),('root/old-backup','synthetic-backup\n',0o600)]:
   p=self.r/n;self.assertEqual(text,p.read_text());self.assertEqual(mode,p.stat().st_mode&0o777)
  self.tmp.cleanup()
 def cmd(self,*args,**kw):return subprocess.run(self.base+list(args),capture_output=True,text=True,timeout=45,**kw)
 def call(self,action='status',input='',tool='passwall2'):return self.cmd('/bin/sh','/fixture/install.sh',tool,action,input=input)
 def start(self,action='download'):return subprocess.Popen(self.base+['/bin/sh','/fixture/install.sh','passwall2',action],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 def waitfor(self,n):
  for _ in range(400):
   if (self.r/'fixture'/n).exists():return
   time.sleep(.025)
  self.fail('timed out: '+n)
 def assertok(self,q):self.assertEqual(0,q.returncode,q.stdout+q.stderr)
 def cache(self):return self.r/'root/mt3600be-tools/passwall2/passwall2-native-r4.2/passwall2-high-native-r4.2.run'
 def clean(self):self.assertFalse(list((self.r/'tmp').glob('mt3600be-online.*')));self.assertFalse(list((self.r/'root').rglob('.download.*')))
 def test_01_actual_no_stat_both_tools_and_repeat(self):
  q=self.cmd('/bin/sh','-c','command -v stat; /qemu /arm/busybox stat --help');self.assertNotEqual(0,q.returncode);self.assertIn('applet not found',q.stderr)
  for tool in ['eee-official','passwall2']:
   for action in ['install','install','status','rollback']:self.assertok(self.call(action,input='YES\n',tool=tool))
  self.clean()
 def test_02_download_failure_retry(self):
  self.write('fixture/download-fail','1');self.assertNotEqual(0,self.call('install',input='YES\n').returncode);self.assertFalse((self.r/'fixture/actions').exists());self.clean()
  (self.r/'fixture/download-fail').unlink();self.assertok(self.call('install',input='YES\n'));self.clean()
 def test_03_two_terminals(self):
  self.write('fixture/hold-download','1');p=self.start()
  try:
   self.waitfor('download-started');self.assertEqual(75,self.call().returncode)
  finally:(self.r/'fixture/hold-download').unlink();out,err=p.communicate(timeout=45)
  self.assertEqual(0,p.returncode,out+err);self.assertok(self.call());self.clean()
 def test_04_symlink_cache_refuses(self):
  self.assertok(self.call('download'));p=self.cache();p.unlink();p.symlink_to('/fixture/payload');self.assertNotEqual(0,self.call().returncode);self.assertTrue(p.is_symlink());self.clean()
 def test_05_bad_mode_cache_refuses(self):
  self.assertok(self.call('download'));self.cache().chmod(0o666);self.assertNotEqual(0,self.call().returncode);self.assertEqual(0o666,self.cache().stat().st_mode&0o777)
 def test_06_api_failure_with_stdout_refuses(self):
  self.write('fixture/meta-fail','1');self.assertNotEqual(0,self.call().returncode);self.assertFalse((self.r/'var/lock/mt3600be-tools-online.lock').exists());self.assertFalse((self.r/'fixture/actions').exists())
 def test_07_missing_fs_module_refuses(self):
  # Replace the ucode call with an actual failing import to exercise missing module.
  self.write('usr/bin/ucode',"#!/bin/sh\nexec /qemu /arm-ucode -e 'import { stat } from \"missing_test_module\";'\n",0o755)
  self.assertNotEqual(0,self.call().returncode);self.assertFalse((self.r/'var/lock/mt3600be-tools-online.lock').exists())
 def test_08_identity_query_failure_after_lock(self):
  s=(self.r/'fixture/install.sh').read_text();s=s.replace('fd_identity=$(meta','touch /fixture/identity-fail\nfd_identity=$(meta',1);self.write('fixture/install.sh',s)
  self.assertNotEqual(0,self.call().returncode);self.assertFalse((self.r/'fixture/actions').exists());self.assertFalse((self.r/'root/mt3600be-tools').exists())
 def test_09_metadata_symlink_modes_and_large_inode(self):
  # Extract the exact production metadata functions and invoke actual target API.
  src=(D/'install.sh').read_text();part=src[src.index('read_meta() {'):src.index('# Check the selected API')]
  self.write('fixture/meta.sh','#!/bin/sh\nMETA_BACKEND=ucode\n'+part+'\nmeta "$@"\n')
  self.write('fixture/record','test');(self.r/'fixture/link').symlink_to('/fixture/record')
  q=self.cmd('/bin/sh','/fixture/meta.sh','mode','/fixture/record');self.assertok(q);self.assertEqual('0:0:600',q.stdout.strip())
  a=self.cmd('/bin/sh','/fixture/meta.sh','identity','/fixture/record');b=self.cmd('/bin/sh','/fixture/meta.sh','identity-follow','/fixture/link');c=self.cmd('/bin/sh','/fixture/meta.sh','identity','/fixture/link')
  for q in [a,b,c]:self.assertok(q)
  self.assertEqual(a.stdout,b.stdout);self.assertNotEqual(a.stdout,c.stdout);self.assertEqual(str((self.r/'fixture/record').stat().st_ino),a.stdout.strip().split(':')[-1])
  q=self.cmd('/bin/sh','/fixture/meta.sh','size','/fixture/record');self.assertok(q);self.assertEqual('4',q.stdout.strip())
  self.assertNotEqual(0,self.cmd('/bin/sh','/fixture/meta.sh','identity','/missing').returncode)
 def test_10_component_failure_keeps_cache_retry(self):
  self.write('fixture/child-fail','1');self.assertEqual(23,self.call('install',input='YES\n').returncode);b=self.cache().read_bytes();self.clean();(self.r/'fixture/child-fail').unlink();self.assertok(self.call('install',input='YES\n'));self.assertEqual(b,self.cache().read_bytes())
 def test_11_TERM_download_cleanup_retry(self):
  self.write('fixture/interrupt-download','1');q=self.call('install',input='YES\n');self.assertNotEqual(0,q.returncode);self.assertFalse((self.r/'fixture/actions').exists());self.clean();self.assertok(self.call('install',input='YES\n'))
 def test_12_TERM_waits_for_child_keeps_lock(self):
  self.write('fixture/interrupt-child','1');self.write('fixture/hold-child','1');p=self.start('install');p.stdin.write('YES\n');p.stdin.flush()
  try:
   self.waitfor('child-started');time.sleep(.2);self.assertIsNone(p.poll());self.assertEqual(75,self.call().returncode)
  finally:(self.r/'fixture/hold-child').unlink();out,err=p.communicate(timeout=45)
  self.assertEqual(0,p.returncode,out+err);self.assertIn('收到中断请求',out);self.clean();(self.r/'fixture/interrupt-child').unlink();self.assertok(self.call())
 def test_13_replaced_lock_refuses(self):
  s=(self.r/'fixture/install.sh').read_text().replace('fd_identity=$(meta','rm -f "$LOCK"\n(umask 077; : > "$LOCK")\nfd_identity=$(meta',1);self.write('fixture/install.sh',s)
  q=self.call();self.assertNotEqual(0,q.returncode);self.assertIn('锁文件被替换',q.stderr);self.assertFalse((self.r/'fixture/actions').exists())
 def test_14_corrupt_cache_not_overwritten(self):
  self.assertok(self.call('download'));self.cache().write_text('synthetic damaged cache');self.assertNotEqual(0,self.call().returncode);self.assertEqual('synthetic damaged cache',self.cache().read_text())
 def test_15_missing_both_metadata_backends(self):
  (self.r/'usr/bin/ucode').unlink();q=self.call();self.assertNotEqual(0,q.returncode);self.assertIn('缺少 stat 和 ucode',q.stderr);self.assertFalse((self.r/'var/lock/mt3600be-tools-online.lock').exists())
 def test_16_private_execution_survives_cache_replacement(self):
  s=(self.r/'fixture/install.sh').read_text().replace('sh "$WORK/tool.run" "$@"', 'printf replaced > "$CACHE"\nsh "$WORK/tool.run" "$@"',1);self.write('fixture/install.sh',s)
  self.assertok(self.call('install',input='YES\n'));self.assertEqual('install --apply\n',(self.r/'fixture/actions').read_text());self.assertEqual('replaced',self.cache().read_text());self.clean()
 def test_17_KILL_download_preserves_orphan_retry_new_copy(self):
  self.write('fixture/kill-download','1');q=self.call('install',input='YES\n');self.assertNotEqual(0,q.returncode);self.assertFalse((self.r/'fixture/actions').exists())
  leftovers=list((self.r/'tmp').glob('mt3600be-online.*'));self.assertTrue(leftovers)
  before={str(p):p.read_bytes() for d in leftovers for p in d.iterdir() if p.is_file()}
  self.assertok(self.call('install',input='YES\n'))
  self.assertEqual(before,{str(p):p.read_bytes() for d in leftovers for p in d.iterdir() if p.is_file()})
 def test_18_linked_lock_not_followed(self):
  lock=self.r/'var/lock/mt3600be-tools-online.lock';lock.symlink_to('/root/old-backup');self.assertNotEqual(0,self.call().returncode);self.assertTrue(lock.is_symlink());self.assertFalse((self.r/'fixture/actions').exists())
if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Target))
 o={'passed':r.wasSuccessful(),'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'source_sha256':hashlib.sha256((D/'install.sh').read_bytes()).hexdigest(),'firmware_binaries':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['bin/busybox','usr/bin/ucode','usr/lib/ucode/fs.so']},'scope':'network-isolated ARM BusyBox/ucode/fs under QEMU; synthetic uname/download/component; no router'}
 (D/'tests/target-results.json').write_text(json.dumps(o,indent=2)+'\n');raise SystemExit(not r.wasSuccessful())
