from native_fixture import *
import unittest
class Recovery(unittest.TestCase):
 def setUp(self):self.f=Fixture()
 def tearDown(self):self.f.close()
 def rebind(self):
  f=self.f;f.freeze();(f.state/'identity').write_text('run-native-v4|'+sha(f.kit/'SHA256SUMS')+'\n')
  f.cmd('/bin/sh','-c','cd /root/mt3600be-passwall2-run-v4/transaction;find . -type f ! -name SEAL ! -name phase ! -path "./native/delta/*" ! -path "./native/commits/*" ! -path "./defaults/*" | sort | while read f;do sha256sum "$f";done > SEAL')
 def interrupted_save(self):
  f=self.f;cc='/home/dosar/immortalwrt/staging_dir/toolchain-aarch64_cortex-a53_gcc-14.3.0_musl/bin/aarch64-openwrt-linux-musl-gcc'
  run([cc,'-O2','-shared','-fPIC',S/'tests/uci_save_fault.c','-ldl','-o',f.root/'fixture/uci-fault.so'])
  f.flag('after-native-firewall');p=f.start()
  try:f.barrier(p)
  finally:f.kill(p);f.clear('after-native-firewall')
  self.assertEqual('',f.cmd('uci','changes').stdout)
  self.assertTrue(any(p.stat().st_size for p in (f.state/'native/delta').iterdir()))
 def restored(self):
  for c,b in self.f.before.items():self.assertEqual(b,(self.f.root/'etc/config'/c).read_bytes(),c)
 def test_27_restore_window_new_config_refused(self):
  f=self.f;f.action();p=f.kit/'fs-safe';p.rename(f.kit/'fs-safe-real')
  f.write('kit/fs-safe',r'''#!/bin/sh
if [ "$1" = restore ] && [ "$3" = /etc/config/firewall ] && [ ! -e /fixture/injected ];then
 cp /etc/config/firewall /fixture/authorized
 printf '\n# later saved config\n' >> /etc/config/firewall
 touch /fixture/injected
fi
exec /kit/fs-safe-real "$@"
''',0o755);self.rebind()
  f.action('rollback',ok=False);self.assertIn(b'later saved config',(f.root/'etc/config/firewall').read_bytes());self.assertNotEqual('rolled-back\n',(f.state/'phase').read_text())
  # Simulate the user resolving the conflicting edit; retry restores normally.
  shutil.copyfile(f.root/'fixture/authorized',f.root/'etc/config/firewall');f.action('rollback');self.restored()
 def test_28_native_private_save_interrupt_install_retry(self):
  self.interrupted_save();self.f.action();self.f.action('rollback');self.restored()
 def test_29_native_private_save_interrupt_rollback_retry(self):
  self.interrupted_save();self.f.action('rollback');self.restored()
  f=self.f
  remaining=[p for n,p,m,k,v in [l.split('|') for l in (f.state/'files').read_text().splitlines()] if not p.startswith('/etc/config/') and ((f.root/p.lstrip('/')).exists() or (f.root/p.lstrip('/')).is_symlink())]
  self.assertEqual([],remaining)
 def test_30_user_pending_not_adopted(self):
  self.interrupted_save();f=self.f;f.cmd('uci','set','network.userchange=interface')
  p=f.root/'tmp/.uci/network';pending=p.read_bytes();db=(f.root/'lib/apk/db/installed').read_bytes()
  f.action(ok=False);f.action('rollback',ok=False);self.assertEqual(pending,p.read_bytes());self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes())
  f.cmd('uci','revert','network');f.action();f.action('rollback');self.restored()
 def test_31_invalid_private_delta_refused(self):
  self.interrupted_save();f=self.f;(f.state/'native/delta/foreign').write_text('no\n')
  db=(f.root/'lib/apk/db/installed').read_bytes();f.action(ok=False);f.action('rollback',ok=False);self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes())

 def test_32_pending_writer_blocks_restore(self):
  f=self.f;f.action();p=f.kit/'fs-safe';p.rename(f.kit/'fs-safe-real')
  f.write('kit/fs-safe',r'''#!/bin/sh
if [ "$1" = restore ] && [ "$3" = /etc/config/firewall ] && [ ! -e /fixture/injected ];then
 touch /etc/config/.firewall.uci-review
 touch /fixture/injected
fi
exec /kit/fs-safe-real "$@"
''',0o755);self.rebind()
  before=(f.root/'etc/config/firewall').read_bytes();f.action('rollback',ok=False);self.assertEqual(before,(f.root/'etc/config/firewall').read_bytes())
  (f.root/'etc/config/.firewall.uci-review').unlink();f.action('rollback');self.restored()
 def test_33_user_delta_created_during_native_hook_is_not_committed(self):
  f=self.f;cc='/home/dosar/immortalwrt/staging_dir/toolchain-aarch64_cortex-a53_gcc-14.3.0_musl/bin/aarch64-openwrt-linux-musl-gcc'
  run([cc,'-O2','-shared','-fPIC',S/'tests/uci_save_fault.c','-ldl','-o',f.root/'fixture/uci-fault.so'])
  f.flag('after-native-firewall');p=f.start()
  try:
   f.barrier(p);f.cmd('uci','set','network.userchange=interface');pending=(f.root/'tmp/.uci/network').read_bytes();f.clear('after-native-firewall');out,err=p.communicate(timeout=120)
   self.assertNotEqual(0,p.returncode,(out,err));self.assertEqual(pending,(f.root/'tmp/.uci/network').read_bytes());self.assertEqual(f.before['network'],(f.root/'etc/config/network').read_bytes())
  finally:
   if p.poll() is None:f.kill(p)
  f.cmd('uci','revert','network');f.action();f.action('rollback');self.restored()
 def test_34_orphan_cleanup_interrupt_retry(self):
  self.interrupted_save();f=self.f;p=f.kit/'fs-safe';p.rename(f.kit/'fs-safe-real')
  f.write('kit/fs-safe',r'''#!/bin/sh
/kit/fs-safe-real "$@" || exit $?
if [ "$1" = remove ] && [ -e /fixture/pause-clean ];then
 touch /fixture/barrier;while :;do sleep .05;done
fi
''',0o755);self.rebind();f.flag('pause-clean');p=f.start('rollback')
  try:f.barrier(p)
  finally:f.kill(p);f.clear('pause-clean')
  f.action('rollback');self.restored()
  for n,p,m,k,v in [l.split('|') for l in (f.state/'files').read_text().splitlines()]:
   if not p.startswith('/etc/config/'):self.assertFalse((f.root/p.lstrip('/')).exists(),p)

 def test_35_native_service_lock_modes_and_busy(self):
  f=self.f;f.action();f.write('var/lock/passwall2.lock','',0o644)
  p=subprocess.Popen(f.prefix()+['/bin/sh','-c','exec 8>>/var/lock/passwall2.lock;flock -x 8;touch /fixture/barrier;while :;do sleep 1;done'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
  try:f.barrier(p);self.assertEqual(75,f.action('rollback',ok=False).returncode)
  finally:f.kill(p)
  f.action('rollback');self.restored()

 def test_36_plan_sync_failure_does_not_publish(self):
  f=self.f;real=f.kit/'fs-safe';real.rename(f.kit/'fs-safe-real')
  f.write('kit/fs-safe',r'''#!/bin/sh
if [ "$1" = sync-tree ] && [ -e /fixture/fail-plan-sync ];then exit 28;fi
exec /kit/fs-safe-real "$@"
''',0o755);f.freeze();before=(f.root/'lib/apk/db/installed').read_bytes();f.flag('fail-plan-sync');f.action(ok=False)
  self.assertFalse(f.state.exists());self.assertEqual(before,(f.root/'lib/apk/db/installed').read_bytes());f.clear('fail-plan-sync');f.action();f.action('rollback');self.restored()
 def test_37_plan_sync_interrupt_before_publish_retry(self):
  f=self.f;real=f.kit/'fs-safe';real.rename(f.kit/'fs-safe-real')
  f.write('kit/fs-safe',r'''#!/bin/sh
/kit/fs-safe-real "$@" || exit $?
if [ "$1" = sync-tree ] && [ -e /fixture/pause-plan-sync ];then touch /fixture/barrier;while :;do sleep .05;done;fi
''',0o755);f.freeze();f.flag('pause-plan-sync');p=f.start()
  try:f.barrier(p)
  finally:f.kill(p);f.clear('pause-plan-sync')
  self.assertFalse(f.state.exists());f.action();f.action('rollback');self.restored()
