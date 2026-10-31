#!/usr/bin/env python3
from native_fixture import *
import unittest
RESULTS=[]
SOURCE_HASH={p.name:sha(p) for p in S.iterdir() if p.is_file() and p.suffix in ['.sh','.c']}
class Tests(unittest.TestCase):
 def setUp(self):self.f=Fixture()
 def tearDown(self):
  for c in ['network','wireless','vpn']:
   self.assertEqual(self.f.before[c],(self.f.root/'etc/config'/c).read_bytes())
  RESULTS.append(self.id().split('.')[-1]);self.f.close()
 def restored(self):
  for c,b in self.f.before.items():
   p=self.f.root/'etc/config'/c;self.assertEqual(b,p.read_bytes(),c);self.assertEqual(self.f.before_modes[c],p.stat().st_mode&0o777,c)
 def interrupt(self,flag,action='install'):
  f=self.f;f.flag(flag);p=f.start(action)
  try:f.barrier(p)
  finally:f.kill(p);f.clear(flag)
 def test_01_offline_signed_install_repeat_rollback(self):
  f=self.f;f.action();self.assertEqual('installed\n',(f.state/'phase').read_text());db=(f.root/'lib/apk/db/installed').read_bytes()
  calls=(f.root/'fixture/service-calls').read_bytes();f.action();self.assertEqual(calls,(f.root/'fixture/service-calls').read_bytes());self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes())
  f.action('rollback');self.restored();f.action('rollback');self.restored();f.action(ok=False)
 def test_02_concurrent_install_rollback_status(self):
  f=self.f;f.flag('before-add');p=f.start()
  try:
   f.barrier(p);seal=(f.state/'SEAL').read_bytes()
   self.assertEqual(75,f.action(ok=False).returncode);self.assertEqual(75,f.action('rollback',ok=False).returncode)
   f.action('status');self.assertEqual(seal,(f.state/'SEAL').read_bytes())
  finally:f.kill(p);f.clear('before-add')
  f.action();f.action('rollback');self.restored()
 def test_03_kill_after_apk_commit_retry(self):
  self.interrupt('after-add');self.f.action();self.f.action('rollback');self.restored()
 def test_04_before_apk_failure_retry(self):
  f=self.f;f.flag('fail-add');f.action(ok=False);f.clear('fail-add');f.action();f.action('rollback');self.restored()
 def test_05_real_native_uci_commit_interruption_retry(self):
  self.interrupt('after-native-firewall');self.f.action();self.f.action('rollback');self.restored()
 def test_06_real_native_uci_commit_interruption_rollback(self):
  self.interrupt('after-native-firewall');self.f.action('rollback');self.restored()
 def test_07_uninstall_before_and_after_commit_retry(self):
  f=self.f;f.action();self.interrupt('before-del','rollback');self.interrupt('after-del','rollback');f.action('rollback');self.restored()
 def test_08_uninstall_failure_retry(self):
  f=self.f;f.action();f.flag('fail-del');f.action('rollback',ok=False);f.clear('fail-del');f.action('rollback');self.restored()
 def test_09_preexisting_cores_preserved(self):
  f=self.f
  paths=[p for p in (f.kit/'repo').glob('*.apk') if p.name.startswith(('shadowsocks-rust-sslocal-','haproxy-','sing-box-','libltdl7-','libpcre2-'))]
  f.cmd('/usr/bin/apk','--no-network','--keys-dir','/kit/keys','--repositories-file','/dev/null','add',*['/kit/repo/'+p.name for p in paths])
  f.action();f.action('rollback');self.restored()
  db=(f.root/'lib/apk/db/installed').read_text()
  for n in ['shadowsocks-rust-sslocal','haproxy','sing-box']:self.assertIn('P:'+n+'\n',db)
 def test_10_modified_shared_config_refuses_before_removal(self):
  f=self.f;f.action();p=f.root/'etc/config/firewall';p.write_text(p.read_text()+'\n# later user change\n');db=(f.root/'lib/apk/db/installed').read_bytes();f.action('rollback',ok=False);self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes())
 def test_11_changed_plugin_config_preserved_on_uninstall(self):
  f=self.f;f.action();p=f.root/'etc/config/passwall2';p.write_text(p.read_text()+'\n# synthetic later user config\n');data=p.read_bytes();f.action('rollback');self.assertEqual(data,p.read_bytes());self.restored()
 def test_12_uci_failure_and_pending_refuse(self):
  f=self.f;f.flag('fail-uci');f.action(ok=False);self.assertFalse(f.state.exists());f.clear('fail-uci')
  f.cmd('uci','set','network.later=interface');f.action(ok=False);self.assertFalse(f.state.exists());f.cmd('uci','revert','network');f.action();f.action('rollback');self.restored()
 def test_13_corrupt_signature_or_manifest_refuse(self):
  f=self.f;p=f.kit/'repo/xray-core-26.10.21-r2.apk';b=bytearray(p.read_bytes());b[len(b)//2]^=1;p.write_bytes(b)
  # Rehash envelope and package inventory to force the APK signature check itself.
  rows=(f.kit/'packages.tsv').read_text().splitlines();(f.kit/'packages.tsv').write_text('\n'.join('|'.join([n,v,sha(p) if n=='xray-core' else h,z]) for n,v,h,z in [r.split('|') for r in rows])+'\n');f.freeze();f.action(ok=False);self.assertFalse(f.state.exists())
 def test_14_corrupt_or_foreign_transaction_refuse(self):
  f=self.f;f.action();db=(f.root/'lib/apk/db/installed').read_bytes();p=f.state/'additions';p.write_text('luci-base=evil\n');f.action('rollback',ok=False);self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes())
 def test_15_unknown_lock_refuses(self):
  f=self.f;p=f.root/'tmp/mt3600be-passwall2-run-v1.lock';p.symlink_to('/fixture/target');f.action(ok=False);self.assertFalse(f.state.exists());self.assertFalse((f.root/'fixture/target').exists())
 def test_16_changed_orphan_file_refuses_retry(self):
  self.interrupt('after-native-firewall');f=self.f;p=f.root/'usr/bin/xray';p.write_bytes(b'user replacement');f.action(ok=False);self.assertEqual(b'user replacement',p.read_bytes())
 def test_17_private_uci_ignores_global_delta(self):
  f=self.f;d=f.root/'root/mt3600be-passwall2-run-v4/.attempt.fixture';d.mkdir(parents=True);(d/'.delta').mkdir();(d/'.override').mkdir();shutil.copyfile(f.root/'etc/config/dhcp',d/'dhcp')
  f.cmd('uci','set','dhcp.@dnsmasq[0].domain=globalpending');before=(f.root/'tmp/.uci/dhcp').read_bytes()
  f.cmd('/kit/uci-plan','/root/mt3600be-passwall2-run-v4/.attempt.fixture','dhcp')
  self.assertNotIn(b'globalpending',(d/'dhcp').read_bytes());self.assertEqual(before,(f.root/'tmp/.uci/dhcp').read_bytes());self.assertEqual(f.before['dhcp'],(f.root/'etc/config/dhcp').read_bytes())
 def test_18_rollback_restore_interruption_retry(self):
  f=self.f;f.action();real=f.kit/'fs-safe';real.rename(f.kit/'fs-safe-real')
  f.write('kit/fs-safe',r'''#!/bin/sh
/kit/fs-safe-real "$@" || exit $?
if [ "$1" = restore ] && [ "$3" = /etc/config/dhcp ] && [ -e /fixture/restore-barrier ];then
 touch /fixture/barrier;while :;do sleep .05;done
fi
''',0o755)
  # Fixture-only tool substitution: keep the transaction identity tied to rehash.
  f.freeze();(f.state/'identity').write_text('run-native-v4|'+sha(f.kit/'SHA256SUMS')+'\n')
  f.cmd('/bin/sh','-c','cd /root/mt3600be-passwall2-run-v4/transaction;find . -type f ! -name SEAL ! -name phase ! -path "./native/delta/*" ! -path "./native/commits/*" ! -path "./defaults/*" | sort | while read f;do sha256sum "$f";done > SEAL')
  self.interrupt('restore-barrier','rollback');f.action('rollback');self.restored()
 def test_19_real_apk_file_deletion_interrupt_retry(self):
  f=self.f;f.action();self.interrupt('after-native-unlink','rollback');f.action('rollback');self.restored()
 def test_20_different_installed_version_refuses(self):
  f=self.f
  # No production metadata altered: a fixture-only prior package DB entry.
  p=f.root/'lib/apk/db/installed';p.write_text(p.read_text()+'P:xray-core\nV:0.0.1-r1\nA:aarch64_cortex-a53\nS:1\nI:1\nT:fixture\nU:https://example.invalid\nL:MIT\n\n')
  before=p.read_bytes();f.action(ok=False);self.assertEqual(before,p.read_bytes());self.assertFalse(f.state.exists())
 def test_21_core_binaries_run_and_target_apk_signatures(self):
  f=self.f;f.action()
  for exe,args,version in [('xray',['version'],'26.10.21'),('sslocal',['--version'],'1.25.0'),('sing-box',['version'],'1.12.17')]:
   out=f.cmd('/bin/qemu','-L','/','/usr/bin/'+exe,*args).stdout;self.assertIn(version,out)
  out=f.cmd('/bin/qemu','-L','/','/usr/sbin/haproxy','-vv').stdout;self.assertIn('3.2.15',out)
  shutil.copyfile(PUBLIC/'usr/bin/apk',f.root/'fixture/apk.arm');(f.root/'fixture/apk.arm').chmod(0o755)
  f.cmd('/bin/qemu','-L','/','/fixture/apk.arm','--no-network','--keys-dir','/kit/keys','verify','/kit/repo/packages.adb',*['/kit/repo/'+p.name for p in (f.kit/'repo').glob('*.apk')])
  f.action('rollback');self.restored()
 def test_22_private_projection_fails_without_modification(self):
  f=self.f;p=f.root/'etc/config/dhcp';p.write_text('broken { config\n');before=p.read_bytes();f.action(ok=False);self.assertEqual(before,p.read_bytes());self.assertFalse(f.state.exists())
 def test_23_bind_mount_restore_refuses_then_retry(self):
  f=self.f;f.action();prefix=f.prefix
  f.prefix=lambda:prefix()+['--bind',str(f.root/'etc/config/firewall'),'/etc/config/firewall']
  f.action('rollback',ok=False)
  self.assertEqual('cleaning\n',(f.state/'phase').read_text())
  f.prefix=prefix;f.action('rollback');self.restored()
 def test_24_shared_permissions_changed_refuses(self):
  f=self.f;f.action();p=f.root/'etc/config/firewall';p.chmod(0o644);db=(f.root/'lib/apk/db/installed').read_bytes();f.action('rollback',ok=False);self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes())
 def test_25_rollback_write_failure_then_retry(self):
  f=self.f;f.action();real=f.kit/'fs-safe';real.rename(f.kit/'fs-safe-real')
  f.write('kit/fs-safe',r'''#!/bin/sh
if [ "$1" = restore ] && [ -e /fixture/fail-restore ];then exit 28;fi
exec /kit/fs-safe-real "$@"
''',0o755)
  f.freeze();(f.state/'identity').write_text('run-native-v4|'+sha(f.kit/'SHA256SUMS')+'\n')
  f.cmd('/bin/sh','-c','cd /root/mt3600be-passwall2-run-v4/transaction;find . -type f ! -name SEAL ! -name phase ! -path "./native/delta/*" ! -path "./native/commits/*" ! -path "./defaults/*" | sort | while read f;do sha256sum "$f";done > SEAL')
  f.flag('fail-restore');f.action('rollback',ok=False);f.clear('fail-restore');f.action('rollback');self.restored()
 def test_26_phase_record_interruption_leaves_transaction_retryable(self):
  f=self.f;real=f.kit/'fs-safe';real.rename(f.kit/'fs-safe-real')
  f.write('kit/fs-safe',r'''#!/bin/sh
if [ "$1" = record ] && [ -e /fixture/phase-record-barrier ];then
 LD_PRELOAD=/fixture/apk-fault.so exec /kit/fs-safe-real "$@"
fi
exec /kit/fs-safe-real "$@"
''',0o755);f.freeze()
  self.interrupt('phase-record-barrier');f.action();f.action('rollback');self.restored()
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 dest=W/'mt3600be-run-native-high-r4.3-20261031/native-tests.json'
 assert SOURCE_HASH=={p.name:sha(p) for p in S.iterdir() if p.is_file() and p.suffix in ['.sh','.c']},'source changed during tests'
 dest.write_text(json.dumps({'source_sha256':SOURCE_HASH,'payload_packages_sha256':sha(PAYLOAD/'packages.json'),'passed':result.wasSuccessful(),'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'cases':RESULTS,'real_signed_APKs':True,'real_ARM_UCI':True,'native_package_hooks':True,'network_isolated':True,'services':'fixtures; no procd/kernel traffic acceptance','no_router_or_VM':True},indent=2)+'\n')
 raise SystemExit(0 if result.wasSuccessful() else 1)
