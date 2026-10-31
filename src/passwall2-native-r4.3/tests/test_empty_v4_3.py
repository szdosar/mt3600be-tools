from native_fixture import *
from test_retained_v4_2 import Restored42
from test_retained_v4 import Retained
import unittest
class Empty43(unittest.TestCase):
 def setUp(self):self.f=Fixture()
 def tearDown(self):
  for n in ['network','wireless','vpn']:self.assertEqual(self.f.before[n],(self.f.root/'etc/config'/n).read_bytes())
  self.f.close()
 setup_restored=Retained.setup_restored
 setup664=Restored42.setup664
 preserved=Retained.preserved
 restored=Retained.restored
 def empty(self):
  base=self.f.state.parent;base.mkdir(mode=0o700,exist_ok=True)
  for n in ['', 'native','native/expected','native/expected/dhcp']:(self.f.state/n).mkdir(mode=0o700,exist_ok=True)
  self.original_inode=self.f.state.stat().st_ino
 def archives(self):return list(self.f.state.parent.glob('empty-transaction-archive.*'))
 def fault(self):
  f=self.f;(f.kit/'fs-safe').rename(f.kit/'fs-safe-real')
  f.write('kit/fs-safe',r'''#!/bin/sh
if [ "$1" = publish ] && [ "$2" = /root/mt3600be-passwall2-run-v4/transaction ]; then
 if [ -e /fixture/archive-before ]; then touch /fixture/barrier; while :; do sleep .05; done; fi
 if [ -e /fixture/archive-file-before ]; then echo 'concurrent synthetic record' > "$2/phase"; chmod 600 "$2/phase"; fi
 if [ -e /fixture/archive-occupied ]; then mkdir -m700 "$3"; echo 'competitor' > "$3/keep"; exit 1; fi
 if [ -e /fixture/archive-exdev ]; then exit 18; fi
 /kit/fs-safe-real "$@" || exit $?
 if [ -e /fixture/archive-after ]; then touch /fixture/barrier; while :; do sleep .05; done; fi
 exit 0
fi
exec /kit/fs-safe-real "$@"
''',0o755);f.freeze()
 def interrupted(self,flag):
  self.f.flag(flag);p=self.f.start()
  try:self.f.barrier(p)
  finally:self.f.kill(p);self.f.clear(flag)
 def test_100_restored_empty_archive_repeat_rollback(self):
  self.setup664();self.empty();backup=self.f.state.parent/'old-backup';backup.write_text('synthetic protected backup');self.f.action();self.preserved()
  a=self.archives();self.assertEqual(1,len(a));self.assertEqual(self.original_inode,(a[0]/'transaction').stat().st_ino);self.assertFalse(any(p.is_file() for p in a[0].rglob('*')))
  self.f.action();self.assertEqual(a,self.archives());self.f.action('rollback');self.restored();self.assertEqual('synthetic protected backup',backup.read_text());self.assertTrue((a[0]/'transaction').exists())
 def test_101_empty_record_is_not_empty_transaction(self):
  self.setup664();self.empty();p=self.f.state/'phase';p.touch(mode=0o600);db=(self.f.root/'lib/apk/db/installed').read_bytes();self.f.action(ok=False);self.assertTrue(p.exists());self.assertFalse(self.archives());self.assertEqual(db,(self.f.root/'lib/apk/db/installed').read_bytes());self.preserved()
 def test_102_nested_record_refuses(self):
  self.setup664();self.empty();p=self.f.state/'native/expected/dhcp/data';p.write_text('synthetic');self.f.action(ok=False);self.assertEqual('synthetic',p.read_text());self.assertFalse(self.archives());self.preserved()
 def test_103_symlink_refuses(self):
  self.setup664();self.empty();p=self.f.state/'link';p.symlink_to('/etc/config/passwall2');self.f.action(ok=False);self.assertTrue(p.is_symlink());self.assertFalse(self.archives());self.preserved()
 def test_104_fifo_refuses(self):
  self.empty();os.mkfifo(self.f.state/'fifo',0o600);self.f.action(ok=False);self.assertFalse(self.archives());self.assertTrue((self.f.state/'fifo').exists())
 def test_105_bad_nested_directory_mode_refuses(self):
  self.empty();(self.f.state/'native').chmod(0o777);self.f.action(ok=False);self.assertFalse(self.archives());self.assertEqual(0o777,(self.f.state/'native').stat().st_mode&0o777)
 def test_106_before_rename_interrupt_concurrent_retry(self):
  self.setup664();self.empty();self.fault();self.f.flag('archive-before');p=self.f.start()
  try:
   self.f.barrier(p);self.assertEqual(75,self.f.action(ok=False).returncode);self.assertEqual(75,self.f.action('rollback',ok=False).returncode);self.assertEqual(self.original_inode,self.f.state.stat().st_ino)
  finally:self.f.kill(p);self.f.clear('archive-before')
  reserved=self.archives();self.assertEqual(1,len(reserved));self.f.action();self.preserved();self.assertTrue(reserved[0].exists());self.assertEqual(2,len(self.archives()));self.f.action('rollback');self.restored()
 def test_107_after_rename_interrupt_retry(self):
  self.setup664();self.empty();self.fault();self.interrupted('archive-after');a=self.archives();self.assertEqual(1,len(a));self.assertFalse(self.f.state.exists());self.assertEqual(self.original_inode,(a[0]/'transaction').stat().st_ino)
  self.f.action();self.preserved();self.assertEqual(a,self.archives());self.f.action('rollback');self.restored()
 def test_108_record_appears_during_archive_blocks_retry(self):
  self.setup664();self.empty();self.fault();self.f.flag('archive-file-before');self.f.action(ok=False);a=self.archives();self.assertEqual(1,len(a));p=a[0]/'transaction/phase';self.assertTrue(p.exists());b=p.read_bytes();self.f.clear('archive-file-before');self.f.action(ok=False);self.assertEqual(b,p.read_bytes());self.assertFalse(self.f.state.exists());self.preserved()
 def test_109_occupied_archive_never_overwritten(self):
  self.empty();self.fault();self.f.flag('archive-occupied');self.f.action(ok=False);p=self.archives()[0]/'transaction/keep';self.assertEqual('competitor\n',p.read_text());self.assertTrue(self.f.state.exists());self.f.clear('archive-occupied');self.f.action(ok=False);self.assertEqual('competitor\n',p.read_text())
 def test_110_rename_error_no_copy_retry(self):
  self.empty();self.fault();self.f.flag('archive-exdev');self.f.action(ok=False);self.assertEqual(self.original_inode,self.f.state.stat().st_ino);self.assertFalse((self.archives()[0]/'transaction').exists());self.f.clear('archive-exdev');self.f.action();self.f.action('rollback')
 def test_111_status_check_rollback_do_not_archive(self):
  self.empty()
  for action in ['status','check','rollback']:self.f.action(action,ok=False)
  self.assertFalse(self.archives());self.assertEqual(self.original_inode,self.f.state.stat().st_ino)
 def test_112_archived_then_add_interruption_retry(self):
  self.setup664();self.empty();self.interrupted('after-add');a=self.archives();self.f.action();self.preserved();self.assertEqual(a,self.archives());self.f.action('rollback');self.restored()
 def test_113_partial_formal_record_refuses(self):
  self.setup664();self.f.action();self.preserved();(self.f.state/'identity').unlink();db=(self.f.root/'lib/apk/db/installed').read_bytes();q=self.f.action(ok=False);self.assertIn('事务记录缺失',q.stdout+q.stderr);self.assertFalse(self.archives());self.assertEqual(db,(self.f.root/'lib/apk/db/installed').read_bytes());self.f.action('rollback',ok=False);self.preserved()
if __name__=='__main__':unittest.main(verbosity=2)
