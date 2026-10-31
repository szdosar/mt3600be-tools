from native_fixture import *
from test_recovery_v2 import Recovery
import unittest
class Transaction(unittest.TestCase):
 def setUp(self):self.f=Fixture()
 def tearDown(self):
  for c in ['network','wireless','vpn']:self.assertEqual(self.f.before[c],(self.f.root/'etc/config'/c).read_bytes())
  self.f.close()
 rebind=Recovery.rebind
 def restored(self):
  for c,b in self.f.before.items():self.assertEqual(b,(self.f.root/'etc/config'/c).read_bytes())
 def fault(self):
  f=self.f;cc='/home/dosar/immortalwrt/staging_dir/toolchain-aarch64_cortex-a53_gcc-14.3.0_musl/bin/aarch64-openwrt-linux-musl-gcc'
  run([cc,'-O2','-shared','-fPIC',S/'tests/commit_fault.c','-ldl','-o',f.root/'fixture/commit-fault.arm.so'])
  run(['cc','-O2','-shared','-fPIC',S/'tests/commit_fault.c','-ldl','-o',f.root/'fixture/commit-fault.so'])
  p=f.root/'sbin/uci';t=p.read_text().replace('exec /bin/qemu','[ -z "${MT3600BE_NATIVE_DELTA:-}" ] || preload="${preload:+$preload:}/fixture/commit-fault.arm.so"\nexec /bin/qemu');p.write_text(t)
  # Fixture-only adapter hash; original ARM UCI and production interposer intact.
  p=f.kit/'target-runtime.tsv';p.write_text(''.join(sha(f.root/n.lstrip('/'))+'  '+n+'\n' for n in [l.split()[1] for l in p.read_text().splitlines()]));f.freeze()
 def stop_commit(self,flag='pause-rename'):
  f=self.f;self.fault();f.flag(flag);p=f.start()
  try:f.barrier(p)
  finally:f.kill(p);f.clear(flag)
  self.assertTrue(list((f.state/'native/commits').iterdir()))
 def test_38_snapshot_boundary_user_save_refused(self):
  f=self.f;p=f.kit/'fs-safe';p.rename(f.kit/'fs-safe-real')
  f.write('kit/fs-safe',r'''#!/bin/sh
/kit/fs-safe-real "$@" || exit $?
if [ "$1" = snapshot ] && [ "$2" = /etc/config/firewall ] && [ ! -e /fixture/saved ];then
 uci set firewall.user_new=rule && uci set firewall.user_new.name=new-user-rule && uci commit firewall || exit 1
 touch /fixture/saved
fi
''',0o755);f.freeze();db=(f.root/'lib/apk/db/installed').read_bytes();f.action(ok=False)
  self.assertFalse(f.state.exists());self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes());self.assertIn(b'new-user-rule',(f.root/'etc/config/firewall').read_bytes())
  f.before['firewall']=(f.root/'etc/config/firewall').read_bytes();f.action();f.action('rollback');self.restored()
 def test_39_snapshot_inode_replaced_during_capture_refused(self):
  f=self.f;self.fault();p=f.kit/'fs-safe';p.rename(f.kit/'fs-safe-real')
  f.write('kit/fs-safe','#!/bin/sh\nLD_PRELOAD=/fixture/commit-fault.so exec /kit/fs-safe-real "$@"\n',0o755);f.freeze();f.flag('pause-snapshot');p=f.start()
  try:
   f.barrier(p);c=f.root/'etc/config/firewall';q=c.with_name('replacement');q.write_bytes(c.read_bytes()+b'\n# newer inode\n');q.chmod(c.stat().st_mode&0o777);q.replace(c);f.clear('pause-snapshot');out,err=p.communicate(timeout=120);self.assertNotEqual(0,p.returncode,(out,err));self.assertIn(b'newer inode',c.read_bytes());self.assertFalse(f.state.exists())
  finally:
   if p.poll() is None:f.kill(p)
 def test_40_native_pre_rename_install_retry(self):
  self.stop_commit();f=self.f;pending=list((f.root/'etc/config').glob('.firewall.uci-*'));self.assertEqual(1,len(pending));a=next((f.state/'native/commits').glob('firewall.*/data'));self.assertEqual(a.stat().st_ino,pending[0].stat().st_ino)
  f.action();self.assertFalse(list((f.root/'etc/config').glob('.*.uci-*')));self.assertFalse(list((f.state/'native/commits').iterdir()));f.action('rollback');self.restored()
 def test_41_native_pre_rename_rollback_retry(self):
  self.stop_commit();f=self.f;f.action('rollback');self.restored();self.assertFalse(list((f.root/'etc/config').glob('.*.uci-*')));f.action('rollback')
 def test_42_private_anchor_before_alias_interrupt_retry(self):
  self.stop_commit('pause-before-link');self.assertFalse(list((self.f.root/'etc/config').glob('.firewall.uci-*')));self.f.action();self.f.action('rollback');self.restored()
 def test_43_alias_created_before_return_interrupt_retry(self):
  self.stop_commit('pause-after-link');self.assertTrue(list((self.f.root/'etc/config').glob('.firewall.uci-*')));self.f.action();self.f.action('rollback');self.restored()
 def test_44_foreign_alias_not_removed(self):
  self.stop_commit();f=self.f;p=next((f.root/'etc/config').glob('.firewall.uci-*'));p.unlink();p.write_text('foreign writer\n');db=(f.root/'lib/apk/db/installed').read_bytes()
  f.action(ok=False);f.action('rollback',ok=False);self.assertEqual('foreign writer\n',p.read_text());self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes());p.unlink();f.action('rollback');self.restored()
 def test_45_replaced_anchor_refused(self):
  self.stop_commit();f=self.f;a=next((f.state/'native/commits').glob('firewall.*/data'));p=next((f.root/'etc/config').glob('.firewall.uci-*'));data=p.read_bytes();a.unlink();a.write_bytes(data);f.action('rollback',ok=False);self.assertEqual(data,p.read_bytes());self.assertNotEqual(p.stat().st_ino,a.stat().st_ino)
 def test_46_live_native_writer_prevents_cleanup(self):
  f=self.f;self.fault();f.flag('pause-rename');p=f.start()
  try:
   f.barrier(p);files=list((f.root/'etc/config').glob('.firewall.uci-*'));self.assertTrue(files);f.cmd('/kit/fs-safe','native-clean',ok=False);self.assertTrue(all(x.exists() for x in files));self.assertEqual(75,f.action('rollback',ok=False).returncode)
  finally:f.kill(p);f.clear('pause-rename')
  f.action('rollback');self.restored()
 def test_47_cleanup_interrupt_after_alias_unlink_retry(self):
  self.stop_commit();f=self.f;p=f.kit/'fs-safe';p.rename(f.kit/'fs-safe-real');f.write('kit/fs-safe','#!/bin/sh\nLD_PRELOAD=/fixture/commit-fault.so exec /kit/fs-safe-real "$@"\n',0o755);self.rebind();f.flag('pause-clean');p=f.start('rollback')
  try:f.barrier(p)
  finally:f.kill(p);f.clear('pause-clean')
  self.assertFalse(list((f.root/'etc/config').glob('.firewall.uci-*')));f.action('rollback');self.restored()
 def test_48_empty_owned_attempt_recovers(self):
  self.stop_commit('pause-before-link');f=self.f;d=f.state/'native/commits/dhcp.Abc123';d.mkdir(mode=0o700);f.action('rollback');self.restored();self.assertFalse(d.exists())
 def test_49_unknown_record_preserved_and_refused(self):
  self.stop_commit();f=self.f;d=f.state/'native/commits/foreign.Abc123';d.mkdir(mode=0o700);pending=list((f.root/'etc/config').glob('.firewall.uci-*'));f.action('rollback',ok=False);self.assertTrue(d.exists());self.assertTrue(all(p.exists() for p in pending))
