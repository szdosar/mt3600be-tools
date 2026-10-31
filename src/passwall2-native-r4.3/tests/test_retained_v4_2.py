from native_fixture import *
from test_retained_v4 import Retained
import unittest
class Restored42(unittest.TestCase):
 def setUp(self):self.f=Fixture()
 def tearDown(self):self.f.close()
 setup_restored=Retained.setup_restored
 preserved=Retained.preserved
 restored=Retained.restored
 interrupt=Retained.interrupt
 def setup664(self,links=False):
  self.setup_restored(server_default=True,links=links)
  for n in self.saved:
   p=self.f.root/'etc/config'/n;p.chmod(0o664)
   self.saved[n]=(p.read_bytes(),0o664)
 def templates(self):
  for n in self.saved:
   p=self.f.state/'defaults'/n
   self.assertEqual(p.read_bytes(),(PAYLOAD/'default-templates'/n).read_bytes())
   self.assertEqual(p.stat().st_mode&0o777,0o600)
 def absent(self):
  for n in ['passwall2','passwall2_server']:self.assertFalse((self.f.state/'defaults'/n).exists())
 def test_85_both_664_install_repeat_rollback(self):
  self.setup664();f=self.f;f.action();self.preserved();self.templates();f.action();self.templates();self.preserved();f.action('rollback');self.restored();self.absent();f.action('rollback');self.restored()
 def test_86_664_add_interruption_retry(self):
  self.setup664();self.interrupt('after-add');self.templates();self.f.action();self.preserved();self.f.action('rollback');self.restored();self.absent()
 def test_87_664_native_commit_interruption_retry(self):
  self.setup664();self.interrupt('after-native-firewall');self.f.action();self.preserved();self.f.action('rollback');self.restored()
 def test_88_664_uninstall_interruption_retry(self):
  self.setup664();self.f.action();self.interrupt('after-native-unlink','rollback');self.preserved();self.f.action('rollback');self.restored();self.absent()
 def test_89_modified_template_kept(self):
  self.setup664();f=self.f;f.action();p=f.state/'defaults/passwall2_server';p.write_bytes(p.read_bytes()+b'\n# user template change\n');saved=p.read_bytes();f.action();self.assertEqual(saved,p.read_bytes());f.action('rollback');self.restored();self.assertEqual(saved,p.read_bytes());self.assertFalse((f.state/'defaults/passwall2').exists());f.action('rollback');self.assertEqual(saved,p.read_bytes())
 def test_90_template_mode_change_kept(self):
  self.setup664();f=self.f;f.action();p=f.state/'defaults/passwall2';p.chmod(0o640);f.action('rollback');self.restored();self.assertTrue(p.exists());self.assertEqual(p.stat().st_mode&0o777,0o640)
 def test_91_missing_receipt_refuses_before_uninstall(self):
  self.setup664();f=self.f;f.action();(f.state/'default-templates').unlink();db=(f.root/'lib/apk/db/installed').read_bytes();f.action('rollback',ok=False);self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes());self.preserved()
 def test_92_template_symlink_refuses_before_uninstall(self):
  self.setup664();f=self.f;f.action();p=f.state/'defaults/passwall2';p.unlink();p.symlink_to('/etc/config/passwall2');db=(f.root/'lib/apk/db/installed').read_bytes();f.action('rollback',ok=False);self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes());self.preserved()
 def test_93_missing_template_not_completed(self):
  self.setup664();f=self.f;f.action();(f.state/'defaults/passwall2').unlink();f.action(ok=False);self.preserved()
 def test_94_template_remove_interruption_retry(self):
  self.setup664();f=self.f;real=f.kit/'fs-safe';real.rename(f.kit/'fs-safe-real')
  f.write('kit/fs-safe',r'''#!/bin/sh
/kit/fs-safe-real "$@" || exit $?
if [ "$1" = remove ] && [ "$2" = /root/mt3600be-passwall2-run-v4/transaction/defaults/passwall2 ] && [ -e /fixture/after-template-remove ];then
 touch /fixture/barrier
 while :;do sleep .05;done
fi
''',0o755);f.freeze();f.action();self.interrupt('after-template-remove','rollback');self.assertFalse((f.state/'defaults/passwall2').exists());self.assertTrue((f.state/'defaults/passwall2_server').exists());f.action('rollback');self.restored();self.absent();f.action('rollback')
 def test_95_prepare_interruption_keeps_old_plan_and_retries(self):
  self.setup664();f=self.f;real=f.kit/'fs-safe';real.rename(f.kit/'fs-safe-real')
  f.write('kit/fs-safe',r'''#!/bin/sh
/kit/fs-safe-real "$@" || exit $?
if [ "$1" = sync-tree ] && [ -e /fixture/before-template-publish ];then
 touch /fixture/barrier
 while :;do sleep .05;done
fi
''',0o755);f.freeze();self.interrupt('before-template-publish');self.assertFalse(f.state.exists());self.preserved();old=list(f.state.parent.glob('.prepare.*'));self.assertTrue(old);before={str(p):sha(p) for d in old for p in (d/'defaults').iterdir()};f.action();self.assertEqual(before,{str(p):sha(p) for d in old for p in (d/'defaults').iterdir()});self.templates();f.action('rollback');self.restored()
 def test_96_world_write_and_special_modes_refuse(self):
  self.setup664();f=self.f;p=f.root/'etc/config/passwall2_server';db=(f.root/'lib/apk/db/installed').read_bytes()
  for mode in [0o666,0o777,0o1664,0o4664]:
   p.chmod(mode);q=f.action(ok=False);self.assertIn('归属或权限异常',q.stdout+q.stderr);self.assertFalse(f.state.exists());self.assertEqual(db,(f.root/'lib/apk/db/installed').read_bytes());self.assertEqual(p.stat().st_mode&0o7777,mode)
 def test_97_shared_configuration_664_preserved(self):
  self.setup664();f=self.f
  for n in ['dhcp','firewall','uhttpd','ucitrack','luci']:
   (f.root/'etc/config'/n).chmod(0o664);f.before_modes[n]=0o664
  f.action();f.action();f.action('rollback');self.restored()
 def test_98_foreign_apk_new_not_overwritten(self):
  self.setup664();f=self.f;p=f.root/'etc/config/passwall2_server.apk-new';p.write_text('foreign placeholder\n');f.action(ok=False);self.assertFalse(f.state.exists());self.assertEqual(p.read_text(),'foreign placeholder\n');self.preserved()
 def test_99_template_race_rejects_without_deleting_edit(self):
  self.setup664();f=self.f;real=f.kit/'fs-safe';real.rename(f.kit/'fs-safe-real')
  f.write('kit/fs-safe',r'''#!/bin/sh
if [ "$1" = remove ] && [ "$2" = /root/mt3600be-passwall2-run-v4/transaction/defaults/passwall2 ];then
 printf '\n# concurrent edit\n' >> "$2"
fi
exec /kit/fs-safe-real "$@"
''',0o755);f.freeze();f.action();f.action('rollback',ok=False);p=f.state/'defaults/passwall2';self.assertIn(b'concurrent edit',p.read_bytes());self.assertNotEqual((f.state/'phase').read_text().strip(),'rolled-back');f.action('rollback');self.assertIn(b'concurrent edit',p.read_bytes());self.restored()
if __name__=='__main__':unittest.main(verbosity=2)
