from native_fixture import *
from test_transaction_v3 import Transaction
import unittest
class Retained(unittest.TestCase):
 def setUp(self):self.f=Fixture()
 def tearDown(self):self.f.close()
 def setup_restored(self,enabled='0',server_default=False,links=False):
  f=self.f
  f.write('etc/config/passwall2',"# synthetic restored configuration\nconfig global\n option enabled '"+enabled+"'\nconfig nodes 'saved'\n option type 'Xray'\n option address 'example.invalid'\n",0o640)
  f.write('etc/config/passwall2_server',"\nconfig global 'global'\n\toption enable '0'\n" if server_default else "# restored server\nconfig global 'global'\n option enable '0'\n option test_note 'synthetic'\n",0o600)
  p=f.root/'etc/config/firewall';p.write_text(p.read_text()+"\nconfig include 'passwall2'\n option type 'script'\n option path '/var/etc/passwall2.include'\n option reload '1'\nconfig include 'passwall2_server'\n option type 'script'\n option path '/var/etc/passwall2_server.include'\n option reload '1'\nconfig rule 'user_rule'\n option name 'preserve-me'\n")
  p=f.root/'etc/config/ucitrack';p.write_text(p.read_text()+"\nconfig passwall2\n option init 'passwall2'\nconfig passwall2_server\n option init 'passwall2_server'\n")
  if links:
   for name in ['S99passwall2','K15passwall2','S99passwall2_server']:(f.root/'etc/rc.d'/name).symlink_to('../init.d/'+('passwall2_server' if name.endswith('server') else 'passwall2'))
  self.saved={n:((f.root/'etc/config'/n).read_bytes(),(f.root/'etc/config'/n).stat().st_mode&0o777) for n in ['passwall2','passwall2_server']}
  for n in ['firewall','ucitrack']:f.before[n]=(f.root/'etc/config'/n).read_bytes()
 def preserved(self):
  for n,(b,m) in self.saved.items():
   p=self.f.root/'etc/config'/n;self.assertEqual(b,p.read_bytes(),n);self.assertEqual(m,p.stat().st_mode&0o777,n)
 def restored(self):
  self.preserved()
  for n,b in self.f.before.items():
   p=self.f.root/'etc/config'/n;self.assertEqual(b,p.read_bytes(),n);self.assertEqual(self.f.before_modes[n],p.stat().st_mode&0o777,n)
 def interrupt(self,flag,action='install'):
  f=self.f;f.flag(flag);p=f.start(action)
  try:f.barrier(p)
  finally:f.kill(p);f.clear(flag)
 def test_50_restored_config_rules_repeat_and_rollback(self):
  self.setup_restored();f=self.f;f.action();self.preserved();f.action();self.preserved();f.action('rollback');self.restored();f.action('rollback');self.restored()
 def test_51_original_default_server_must_survive_uninstall(self):
  self.setup_restored(server_default=True);f=self.f;f.action();self.preserved();f.action('rollback');self.restored()
 def test_52_restored_enabled_switch_preserved(self):
  self.setup_restored(enabled='1');f=self.f;f.action();self.preserved();self.assertIn('/etc/init.d/passwall2 start',(f.root/'fixture/service-calls').read_text());f.action('rollback');self.restored()
 def test_53_old_native_start_links_restored_after_rollback(self):
  self.setup_restored(links=True);f=self.f;old={p.name:os.readlink(p) for p in (f.root/'etc/rc.d').glob('*passwall2*')};f.action();f.action('rollback');self.restored();f.action('rollback');self.assertEqual(old,{p.name:os.readlink(p) for p in (f.root/'etc/rc.d').glob('*passwall2*')})
 def test_54_rules_only_after_user_moved_configs(self):
  self.setup_restored();f=self.f
  for n in self.saved:(f.root/'etc/config'/n).unlink()
  f.action();f.action('rollback')
  for n,b in f.before.items():self.assertEqual(b,(f.root/'etc/config'/n).read_bytes(),n)
 def test_55_changed_plugin_config_after_install_kept_on_rollback(self):
  self.setup_restored();f=self.f;f.action()
  for n in self.saved:
   p=f.root/'etc/config'/n;p.write_bytes(p.read_bytes()+b'\n# later user change\n');self.saved[n]=(p.read_bytes(),p.stat().st_mode&0o777)
  f.action('rollback');self.restored()
 def test_56_unknown_include_refuses_before_install(self):
  self.setup_restored();f=self.f;p=f.root/'etc/config/firewall';p.write_text(p.read_text().replace('/var/etc/passwall2.include','/etc/custom-script'));db=(f.root/'lib/apk/db/installed').read_bytes();f.action(ok=False);self.assertFalse(f.state.exists());self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes());self.preserved()
 def test_57_config_symlink_refuses(self):
  self.setup_restored();f=self.f;p=f.root/'etc/config/passwall2';p.unlink();p.symlink_to('/etc/config/network');f.action(ok=False);self.assertFalse(f.state.exists());self.assertEqual(f.before['network'],(f.root/'etc/config/network').read_bytes())
 def test_58_restored_uci_commit_interrupt_install_retry(self):
  self.setup_restored();self.interrupt('after-native-firewall');f=self.f;f.action();self.preserved();f.action('rollback');self.restored()
 def test_59_restored_uci_commit_interrupt_rollback(self):
  self.setup_restored();self.interrupt('after-native-firewall');self.f.action('rollback');self.restored()
 def test_60_restored_apk_commit_interrupt_install_retry(self):
  self.setup_restored();self.interrupt('after-add');self.f.action();self.preserved();self.f.action('rollback');self.restored()
 def test_61_uninstall_file_delete_interrupt_then_retry(self):
  self.setup_restored(server_default=True,links=True);f=self.f;f.action();self.interrupt('after-native-unlink','rollback');self.preserved();f.action('rollback');self.restored()
 def test_62_concurrent_install_and_rollback_refuse(self):
  self.setup_restored();f=self.f;f.flag('before-add');p=f.start()
  try:
   f.barrier(p);self.assertEqual(75,f.action(ok=False).returncode);self.assertEqual(75,f.action('rollback',ok=False).returncode);f.action('status');self.preserved()
  finally:f.kill(p);f.clear('before-add')
  f.action();f.action('rollback');self.restored()
 def test_63_old_r3_failed_preflight_does_not_block(self):
  f=self.f;f.write('root/mt3600be-passwall2-run-v3/.prepare.old/identity','old failed plan\n',0o600);f.action();f.action('rollback');self.assertEqual('old failed plan\n',(f.root/'root/mt3600be-passwall2-run-v3/.prepare.old/identity').read_text())
 def test_64_old_r3_committed_transaction_refuses(self):
  f=self.f;f.write('root/mt3600be-passwall2-run-v3/transaction/identity','old committed transaction\n',0o600);db=(f.root/'lib/apk/db/installed').read_bytes();f.action(ok=False);self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes());self.assertFalse(f.state.exists())
 def test_65_retained_record_missing_refuses_before_uninstall(self):
  self.setup_restored();f=self.f;f.action();(f.state/'retained-files').unlink();db=(f.root/'lib/apk/db/installed').read_bytes();f.action('rollback',ok=False);self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes());self.preserved()
 def test_66_new_shared_rule_after_install_refuses_overwrite(self):
  self.setup_restored();f=self.f;f.action();p=f.root/'etc/config/firewall';p.write_text(p.read_text()+'\n# later rule\n');db=(f.root/'lib/apk/db/installed').read_bytes();f.action('rollback',ok=False);self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes());self.assertIn(b'later rule',p.read_bytes());self.preserved()
 def test_67_retained_snapshot_race_refuses(self):
  self.setup_restored();f=self.f;real=f.kit/'fs-safe';real.rename(f.kit/'fs-safe-real');f.write('kit/fs-safe',r'''#!/bin/sh
/kit/fs-safe-real "$@" || exit $?
if [ "$1" = snapshot ] && [ "$2" = /etc/config/passwall2 ];then
 printf '\n# user changed after capture\n' >> /etc/config/passwall2
fi
''',0o755);f.freeze();db=(f.root/'lib/apk/db/installed').read_bytes();f.action(ok=False);self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes());self.assertFalse(f.state.exists());self.assertIn(b'user changed after capture',(f.root/'etc/config/passwall2').read_bytes())
if __name__=='__main__':unittest.main(verbosity=2)
