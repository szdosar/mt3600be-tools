#!/usr/bin/env python3
"""Isolated local fixture: no real router, network or package operations."""
from pathlib import Path
import hashlib,json,os,shutil,signal,subprocess,tempfile,time,unittest
D=Path(__file__).resolve().parents[1]
class Online(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='mt-tools-test-');self.d=Path(self.tmp.name);self.root=self.d/'root';self.root.mkdir(mode=0o700);self.bin=self.d/'bin';self.bin.mkdir();(self.d/'tmp').mkdir();(self.d/'lock').mkdir()
  self.board=self.d/'board';self.board.write_text('glinet,gl-mt3600be\n');(self.d/'kernel').write_text('6.12.94\n');(self.d/'glversion').write_text('4.9.1-op25\n');(self.d/'release').write_text("DISTRIB_RELEASE='25.12.5'\nDISTRIB_REVISION='r33051-f5dae5ece4'\nDISTRIB_TARGET='mediatek/filogic'\nDISTRIB_ARCH='aarch64_cortex-a53'\n")
  self.payload=self.d/'payload';self.payload.write_text('#!/bin/sh\nset -eu\nprintf "%s\\n" "$*" >> "'+str(self.d/'actions')+'"\nif [ -e "'+str(self.d/'hold-child')+'" ];then touch "'+str(self.d/'child-started')+'";while [ -e "'+str(self.d/'hold-child')+'" ];do sleep .05;done;fi\n[ ! -e "'+str(self.d/'fail-child')+'" ] || exit 23\n')
  self.sha=hashlib.sha256(self.payload.read_bytes()).hexdigest();src=(D/'install.sh').read_text()
  src=src.replace('PATH=/usr/sbin:/usr/bin:/sbin:/bin;',f'PATH={self.bin}:/usr/sbin:/usr/bin:/sbin:/bin;').replace('/root',str(self.root)).replace('/var/lock/mt3600be-tools-online.lock',str(self.d/'lock/online.lock')).replace('/tmp/sysinfo/board_name',str(self.board)).replace('/etc/glversion',str(self.d/'glversion')).replace('/etc/openwrt_release',str(self.d/'release')).replace('/tmp/mt3600be-online.',str(self.d/'tmp/work.')).replace('= 0:0:',f'= {os.getuid()}:{os.getgid()}:')
  src=src.replace('[ "$(id -u)" = 0 ]','[ 1 = 1 ]').replace('$(uname -r)', '$(cat '+str(self.d/'kernel')+')')
  for h in ['b9b1b10c86fc5c21c87669a4401a2fae482f1184969c4f85f669e1f59203d074','4ed3294a9cd45086883d722b48436205fcaea95112eaba54bf9a5105bb7248de','7651ad40e4bc429f4a28ac829e02d4af5b5d9923d9cb76b2aca42a301cc6e488']:src=src.replace(h,self.sha)
  for n in [184936,42907,41489723]:src=src.replace('SIZE='+str(n),'SIZE='+str(self.payload.stat().st_size))
  self.script=self.d/'install.sh';self.script.write_text(src)
  self.write('id','#!/bin/sh\necho 0\n');self.write('uname','#!/bin/sh\ncat '+str(self.d/'kernel')+'\n')
  self.write('curl',f'''#!/usr/bin/python3
from pathlib import Path
import sys,time
D=Path({str(self.d)!r});a=sys.argv[1:]
assert a[0]=='-q' and '--fail' in a and a[a.index('--proto')+1]=='=https' and a[a.index('--proto-redir')+1]=='=https'
assert a[-1].startswith('https://github.com/szdosar/mt3600be-tools/releases/download/')
p=Path(a[a.index('--output')+1]);m=(D/'download-mode').read_text() if (D/'download-mode').exists() else 'ok'
with (D/'downloads').open('a') as f:f.write(a[-1]+'\\n')
if m=='hold':
 (D/'download-started').touch()
 while (D/'download-mode').read_text()=='hold':time.sleep(.05)
b=(D/'payload').read_bytes()
if m=='fail':p.write_bytes(b[:5]);sys.exit(22)
if m=='empty':b=b''
if m=='truncated':b=b[:5]
if m=='corrupt':b=b[:-1]+bytes([b[-1]^1])
p.write_bytes(b)
''')
  self.write('sh',f'''#!/bin/sh
if [ -e '{self.d}/replace-cache' ];then printf 'replaced cache\n' > '{self.cache()}';fi
printf '%s\n' "$1" >> '{self.d}/executed-path'
exec /bin/sh "$@"
''')
 def write(self,n,s):p=self.bin/n;p.write_text(s);p.chmod(0o755)
 def tearDown(self):self.tmp.cleanup()
 def cache(self):return self.root/'mt3600be-tools/passwall2/passwall2-native-r4.3/passwall2-high-native-r4.3.run'
 def call(self,*a,input='',shell=None):return subprocess.run((shell or ['/bin/sh'])+[str(self.script),*a],input=input,capture_output=True,text=True,timeout=15)
 def start(self,*a):return subprocess.Popen(['/bin/sh',str(self.script),*a],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 def waitfor(self,n):
  for _ in range(200):
   if (self.d/n).exists():return
   time.sleep(.025)
  self.fail('timeout '+n)
 def noexec(self):self.assertFalse((self.d/'actions').exists())
 def clean(self):self.assertEqual([],list((self.d/'tmp').iterdir()));self.assertFalse(list(self.root.rglob('.download.*')))
 def test_01_download_install_cache_and_arguments(self):
  p=self.call('passwall2','download');self.assertEqual(0,p.returncode,p.stderr);self.noexec();self.assertEqual(self.sha,hashlib.sha256(self.cache().read_bytes()).hexdigest());self.clean()
  p=self.call('passwall2','install',input='YES\n');self.assertEqual(0,p.returncode,p.stderr);self.assertEqual('install --apply\n',(self.d/'actions').read_text());self.assertEqual(1,len((self.d/'downloads').read_text().splitlines()));self.clean()
 def test_02_decline_no_download_or_execution(self):
  p=self.call('passwall2','install',input='no\n');self.assertEqual(0,p.returncode);self.noexec();self.assertFalse(self.cache().exists());self.assertFalse((self.d/'downloads').exists())
 def test_03_wrong_board_refuses(self):self.board.write_text('other\n');self.assertNotEqual(0,self.call('passwall2','install',input='YES\n').returncode);self.noexec()
 def test_04_wrong_kernel_refuses(self):(self.d/'kernel').write_text('6.12.115\n');self.assertNotEqual(0,self.call('passwall2','download').returncode);self.noexec()
 def test_05_failed_download_no_old_execution_retry(self):
  old=self.root/'old.run';old.write_text('old');(self.d/'download-mode').write_text('fail');self.assertNotEqual(0,self.call('passwall2','install',input='YES\n').returncode);self.noexec();self.clean();self.assertEqual('old',old.read_text());(self.d/'download-mode').unlink();self.assertEqual(0,self.call('passwall2','install',input='YES\n').returncode)
 def test_06_empty_download(self):(self.d/'download-mode').write_text('empty');self.assertNotEqual(0,self.call('passwall2','check').returncode);self.noexec();self.clean()
 def test_07_corrupt_download(self):(self.d/'download-mode').write_text('corrupt');self.assertNotEqual(0,self.call('passwall2','check').returncode);self.noexec();self.clean()
 def test_08_truncated_download(self):(self.d/'download-mode').write_text('truncated');self.assertNotEqual(0,self.call('passwall2','check').returncode);self.noexec();self.clean()
 def test_09_corrupt_cache_never_overwritten(self):
  self.call('passwall2','download');self.cache().write_text('old damaged');p=self.call('passwall2','install',input='YES\n');self.assertNotEqual(0,p.returncode);self.noexec();self.assertEqual('old damaged',self.cache().read_text())
 def test_10_cache_link_refuses(self):
  p=self.cache();p.parent.mkdir(parents=True,mode=0o700);p.symlink_to(self.payload);self.assertNotEqual(0,self.call('passwall2','status').returncode);self.noexec();self.assertTrue(p.is_symlink())
 def test_11_cache_directory_link_refuses(self):
  (self.root/'mt3600be-tools').symlink_to(self.d/'tmp');self.assertNotEqual(0,self.call('passwall2','download').returncode);self.noexec()
 def test_12_two_terminals_refuse_retry(self):
  (self.d/'download-mode').write_text('hold');p=self.start('passwall2','download');self.waitfor('download-started');q=self.call('passwall2','status');self.assertEqual(75,q.returncode);(self.d/'download-mode').write_text('ok');p.communicate(timeout=10);self.assertEqual(0,p.returncode);self.assertEqual(0,self.call('passwall2','status').returncode);self.clean()
 def test_13_TERM_download_cleanup_retry(self):
  (self.d/'download-mode').write_text('hold');p=self.start('passwall2','download');self.waitfor('download-started');p.send_signal(signal.SIGTERM);(self.d/'download-mode').write_text('ok');p.communicate(timeout=10);self.assertNotEqual(0,p.returncode);self.noexec();self.clean();self.assertEqual(0,self.call('passwall2','download').returncode)
 def test_14_TERM_waits_for_component(self):
  (self.d/'hold-child').touch();p=self.start('passwall2','install');p.stdin.write('YES\n');p.stdin.flush();self.waitfor('child-started');p.send_signal(signal.SIGTERM);time.sleep(.1);self.assertIsNone(p.poll());self.assertTrue(list((self.d/'tmp').iterdir()));self.assertEqual(75,self.call('passwall2','status').returncode);(self.d/'hold-child').unlink();p.communicate(timeout=10);self.assertEqual(0,p.returncode);self.clean()
 def test_15_component_failure_preserves_cache_retry(self):
  (self.d/'fail-child').touch();p=self.call('passwall2','install',input='YES\n');self.assertEqual(23,p.returncode);self.assertTrue(self.cache().exists());self.clean();(self.d/'fail-child').unlink();self.assertEqual(0,self.call('passwall2','install',input='YES\n').returncode)
 def test_16_executes_independent_verified_copy(self):
  (self.d/'replace-cache').touch();p=self.call('passwall2','install',input='YES\n');self.assertEqual(0,p.returncode,p.stderr);self.assertEqual('replaced cache\n',self.cache().read_text());self.assertIn('/tmp/work.',(self.d/'executed-path').read_text());self.assertEqual('install --apply\n',(self.d/'actions').read_text())
 def test_17_rollback_requires_confirmation(self):
  self.assertEqual(0,self.call('passwall2','rollback',input='\n').returncode);self.noexec();self.assertEqual(0,self.call('passwall2','rollback',input='YES\n').returncode);self.assertEqual('rollback --apply\n',(self.d/'actions').read_text())
 def test_18_EEE_official_command_and_decline(self):
  self.assertEqual(0,self.call('eee-official','install',input='YES\n').returncode);self.assertEqual('install --yes\n',(self.d/'actions').read_text());self.assertEqual(0,self.call('eee-official','rollback',input='NO\n').returncode);self.assertEqual(1,len((self.d/'actions').read_text().splitlines()))
 def test_19_unknown_tool_refuses_without_download(self):
  self.assertNotEqual(0,self.call('unsupported-tool','download').returncode);(self.d/'kernel').write_text('6.12.115\n');self.assertNotEqual(0,self.call('unsupported-tool','install',input='YES\n').returncode);self.noexec();self.assertFalse((self.d/'downloads').exists())
 def test_20_unknown_action_refuses(self):self.assertNotEqual(0,self.call('passwall2','enable').returncode);self.noexec()
 def test_21_bad_cache_permissions_not_changed(self):
  self.call('passwall2','download');self.cache().chmod(0o666);self.assertNotEqual(0,self.call('passwall2','check').returncode);self.assertEqual(0o666,self.cache().stat().st_mode&0o777);self.noexec()
 def test_22_cache_publish_competitor_not_overwritten(self):
  self.write('ln',f'#!/bin/sh\nprintf "competitor\\n" > "$2"\nexit 1\n');self.assertNotEqual(0,self.call('passwall2','install',input='YES\n').returncode);self.noexec();self.assertEqual('competitor\n',self.cache().read_text());self.clean()
 def test_23_interactive_menu(self):
  p=self.call(input='2\n2\n');self.assertEqual(0,p.returncode,p.stderr);self.assertEqual('status\n',(self.d/'actions').read_text())
 def test_24_lock_link_refuses(self):
  (self.d/'lock/online.lock').symlink_to(self.payload);b=self.payload.read_bytes();self.assertNotEqual(0,self.call('passwall2','download').returncode);self.assertEqual(b,self.payload.read_bytes());self.noexec()
 def test_25_check_argument(self):self.assertEqual(0,self.call('passwall2','check').returncode);self.assertEqual('--check\n',(self.d/'actions').read_text())
 def test_26_busybox_ash(self):
  bb=shutil.which('busybox')
  if not bb:self.skipTest('BusyBox absent')
  p=self.call('passwall2','status',shell=[bb,'ash']);self.assertEqual(0,p.returncode,p.stderr);self.assertEqual('status\n',(self.d/'actions').read_text());self.clean()
 def test_27_corrupt_stage_never_published(self):
  self.write('cp','#!/bin/sh\nprintf broken > "$2"\nexit 0\n');self.assertNotEqual(0,self.call('passwall2','install',input='YES\n').returncode);self.noexec();self.assertFalse(self.cache().exists());self.clean()
 def test_28_stage_write_failure_cleans_only_owned_file(self):
  self.write('cp','#!/bin/sh\nprintf partial > "$2"\nexit 1\n');self.assertNotEqual(0,self.call('passwall2','download').returncode);self.assertFalse(self.cache().exists());self.clean()
 def test_29_wrong_gl_version_both_tools(self):
  (self.d/'glversion').write_text('4.9.2-op25\n')
  for tool in ['eee-official','passwall2']:self.assertNotEqual(0,self.call(tool,'download').returncode)
  self.noexec();self.assertFalse((self.d/'downloads').exists())
 def test_30_other_OpenWrt_release_both_tools(self):
  p=self.d/'release';p.write_text(p.read_text().replace('25.12.5','25.12.6'))
  for tool in ['eee-official','passwall2']:self.assertNotEqual(0,self.call(tool,'download').returncode)
  self.noexec()
 def test_31_wrong_build_both_tools(self):
  p=self.d/'release';p.write_text(p.read_text().replace('r33051-f5dae5ece4','r33052-other'))
  for tool in ['eee-official','passwall2']:self.assertNotEqual(0,self.call(tool,'download').returncode)
  self.noexec()
 def test_32_arch_target_missing_fields_refuse(self):
  p=self.d/'release';before=p.read_text()
  for text in [before.replace('aarch64_cortex-a53','x86_64'),before.replace('mediatek/filogic','other/target'),"DISTRIB_RELEASE='25.12.5'\n"]:
   p.write_text(text)
   for tool in ['eee-official','passwall2']:self.assertNotEqual(0,self.call(tool,'download').returncode)
  self.noexec();self.assertFalse((self.d/'downloads').exists())
if __name__=='__main__':
 s=unittest.defaultTestLoader.loadTestsFromTestCase(Online);r=unittest.TextTestRunner(verbosity=2).run(s)
 report={'passed':r.wasSuccessful(),'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'source_sha256':hashlib.sha256((D/'install.sh').read_bytes()).hexdigest(),'scope':'isolated synthetic files and component commands; no router or real installation'}
 (D/'tests/results.json').write_text(json.dumps(report,indent=2)+'\n');raise SystemExit(not r.wasSuccessful())
