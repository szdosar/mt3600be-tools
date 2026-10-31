from native_fixture import *
import unittest
R3_PAYLOAD=W/'mt3600be-run-native-high-r3-20261025/payload01'
R3_SOURCE=W/'mt3600be-plugin-kit/experimental/passwall2-run-native-v3'
PIN='524eb3afeae27e966fc42cebbdf1d9d3f38672d77de907e756f895cc11b65a14'
class Predecessor(unittest.TestCase):
 def setUp(self):self.f=Fixture()
 def tearDown(self):self.f.close()
 def old(self,rollback=True):
  f=self.f;new=f.root/'kit-v4';f.kit.rename(new);shutil.copytree(R3_PAYLOAD,f.kit)
  for name in ['target-apk.sha256','target-runtime.tsv']:shutil.copyfile(new/name,f.kit/name)
  for name in ['fs-safe','apk-db-guard','native-uci']:
   args=['cc','-O2']
   if name!='fs-safe':args+=['-shared','-fPIC','-I/home/dosar/lede/staging_dir/target-aarch64_cortex-a53_musl/usr/include']
   args += [R3_SOURCE/(name+'.c')]
   if name!='fs-safe':args+=['-ldl']
   args+=['-o',f.kit/(name+('.so' if name!='fs-safe' else ''))];run(args)
  shutil.copyfile(R3_PAYLOAD/'native-uci.so',f.kit/'native-uci.arm.so')
  (f.kit/'uci-plan').rename(f.kit/'uci-plan.arm');f.write('kit/uci-plan','#!/bin/sh\nexec /bin/qemu -L / /kit/uci-plan.arm "$@"\n',0o755)
  f.freeze();oldid=sha(f.kit/'SHA256SUMS')
  f.action()
  if rollback:f.action('rollback')
  f.kit.rename(f.root/'kit-v3');new.rename(f.kit)
  p=f.kit/'native-config.sh';p.write_text(p.read_text().replace(PIN,oldid));f.freeze()
  self.r3=f.root/'root/mt3600be-passwall2-run-v3/transaction'
  self.history=self.tree()
 def tree(self):
  return {str(p.relative_to(self.r3)):(p.stat().st_mode&0o777, p.read_bytes() if p.is_file() else None) for p in self.r3.rglob('*')}
 def unchanged(self):self.assertEqual(self.history,self.tree())
 def deny(self):
  f=self.f;db=(f.root/'lib/apk/db/installed').read_bytes();p=f.action(ok=False);self.assertFalse(f.state.exists());self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes());return p
 def test_68_real_r3_rollback_then_r4_repeat_rollback(self):
  self.old();f=self.f;f.action();self.unchanged();f.action();f.action('rollback');f.action('rollback');self.unchanged()
  for n,b in f.before.items():self.assertEqual(b,(f.root/'etc/config'/n).read_bytes(),n)
 def test_69_r3_installed_is_not_adopted(self):
  self.old(False);self.deny();self.unchanged()
 def test_70_r3_partial_rollback_is_not_adopted(self):
  self.old();(self.r3/'phase').write_text('cleaning\n');self.deny()
 def test_71_r3_bad_seal_refuses_before_mutation(self):
  self.old();(self.r3/'additions').write_text('xray-core=26.10.21-r2\n');self.deny()
 def test_72_r3_missing_record_refuses(self):
  self.old();(self.r3/'native/meta').unlink();self.deny()
 def test_73_r3_shared_config_difference_not_overwritten(self):
  self.old();f=self.f;p=f.root/'etc/config/firewall';p.write_bytes(p.read_bytes()+b'\n# user change\n');saved=p.read_bytes();self.deny();self.assertEqual(saved,p.read_bytes());self.unchanged()
 def test_74_r3_commits_residue_not_removed(self):
  self.old();p=self.r3/'native/commits/dhcp.AbC123';p.mkdir(mode=0o700);(p/'data').write_text('synthetic foreign residue');self.deny();self.assertTrue((p/'data').exists())
 def test_75_r4_interrupted_add_resumes_without_r3_package_absence_gate(self):
  self.old();f=self.f;f.flag('after-add');p=f.start()
  try:f.barrier(p)
  finally:f.kill(p);f.clear('after-add')
  f.action();f.action('rollback');self.unchanged()
 def test_76_r4_interrupted_remove_retries(self):
  self.old();f=self.f;f.action();f.flag('after-del');p=f.start('rollback')
  try:f.barrier(p)
  finally:f.kill(p);f.clear('after-del')
  f.action('rollback');self.unchanged()
 def test_77_r3_and_r4_share_global_lock(self):
  self.old();f=self.f;f.flag('before-add');p=f.start()
  try:
   f.barrier(p);self.assertEqual(75,f.cmd('/bin/sh','/kit-v3/controller.sh','rollback','--apply',ok=False).returncode);self.assertEqual(75,f.action(ok=False).returncode)
  finally:f.kill(p);f.clear('before-add')
  f.action();f.action('rollback');self.unchanged()
 def test_78_changed_old_history_blocks_r4_retry(self):
  self.old();f=self.f;f.flag('before-add');p=f.start()
  try:f.barrier(p)
  finally:f.kill(p);f.clear('before-add')
  (self.r3/'phase').write_text('installed\n');db=(f.root/'lib/apk/db/installed').read_bytes();f.action(ok=False);self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes())
 def test_79_r3_transaction_symlink_refuses(self):
  self.old();target=self.r3.with_name('history');self.r3.rename(target);self.r3.symlink_to(target.name);self.deny()
 def test_80_deleted_predecessor_record_not_inferred(self):
  self.old();f=self.f;f.flag('before-add');p=f.start()
  try:f.barrier(p)
  finally:f.kill(p);f.clear('before-add')
  (f.state/'predecessor').unlink();db=(f.root/'lib/apk/db/installed').read_bytes();f.action(ok=False);self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes())
 def test_81_forged_rolled_back_phase_with_packages_refuses(self):
  self.old(False);(self.r3/'phase').write_text('rolled-back\n');self.deny()
 def test_82_foreign_r3_identity_refuses(self):
  self.old();(self.r3/'identity').write_text('run-native-v3|foreign\n');self.deny()
 def test_83_old_history_changes_before_publish_refuses(self):
  self.old();f=self.f;real=f.kit/'fs-safe';real.rename(f.kit/'fs-safe-real');f.write('kit/fs-safe',r'''#!/bin/sh
/kit/fs-safe-real "$@" || exit $?
if [ "$1" = sync-tree ];then
 printf 'installed\n' > /root/mt3600be-passwall2-run-v3/transaction/phase
fi
''',0o755);f.freeze();self.deny()
 def test_84_failed_apk_retry_keeps_old_history(self):
  self.old();f=self.f;f.flag('fail-add');f.action(ok=False);self.unchanged();f.clear('fail-add');f.action();f.action('rollback');self.unchanged()
if __name__=='__main__':unittest.main(verbosity=2)
