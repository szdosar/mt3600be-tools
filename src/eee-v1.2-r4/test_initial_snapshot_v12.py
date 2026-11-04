from pathlib import Path
import fcntl,hashlib,os,struct,subprocess,tempfile,unittest

P=Path(__file__).resolve().parent
ns={'__file__':str(P/'test_combined.py')}
exec((P/'test_combined.py').read_text().split('for answer in')[0],ns)
mk,call=ns['mk'],ns['call']

def rehash(d):
    (d/'patch/SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in (d/'patch').iterdir() if f.name!='SHA256SUMS'))

class InitialSnapshotTests(unittest.TestCase):
    def test_timer_zero_compiled_helper_refuses_without_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp)
            blob=struct.pack('=12I',0x45454531,0,0x28,0x28,0x28,1,0,1,0,0,0,6)
            state=tmp/'state';state.write_bytes(blob);state.chmod(0o600)
            model=tmp/'model';model.write_bytes(blob+struct.pack('II',0,0))
            q=subprocess.run([str(P/'helper-test'),'validate',str(state)],env=dict(os.environ,MODEL=str(model)),capture_output=True)
            self.assertEqual(q.returncode,4);self.assertEqual(state.read_bytes(),blob)
            self.assertEqual(model.read_bytes(),blob+struct.pack('II',0,0))

    def test_invalid_snapshot_retained_and_clear_diagnostic(self):
        r,d,e=mk();h=d/'patch/eee-state'
        h.write_text(h.read_text().replace('printf original > "$2"','printf invalid > "$2"').replace('validate) [ "$(cat "$2")" = original ];;','validate) [ "$(cat "$2")" = original ] || exit 4;;'))
        rehash(d);q=call(d,e,'install','--yes');s=r/'etc/mt3600be-wan-eee'
        self.assertEqual(q.returncode,4);self.assertIn('超出已验证范围',q.stderr)
        self.assertEqual((s/'original.bin').read_bytes(),b'invalid')
        self.assertFalse((r/'enabled').exists());self.assertFalse((r/'running').exists())
        self.assertNotEqual(call(d,e,'install','--yes').returncode,0)
        self.assertEqual((s/'original.bin').read_bytes(),b'invalid')

    def test_save_io_failure_reports_and_preserves_partial(self):
        r,d,e=mk();h=d/'patch/eee-state'
        h.write_text(h.read_text().replace('printf original > "$2"','printf partial > "$2"; exit 1'))
        rehash(d);q=call(d,e,'install','--yes')
        self.assertNotEqual(q.returncode,0);self.assertIn('采集原始状态失败',q.stderr)
        self.assertEqual((r/'etc/mt3600be-wan-eee/original.bin').read_bytes(),b'partial')

    def test_kill_at_each_early_checkpoint_preserves_existing_record(self):
        for needle in ['mkdir "$STATE"','"$DIR/eee-state" save "$STATE/original.bin"',
                       '"$DIR/eee-state" validate "$STATE/original.bin"',
                       '(cd "$STATE"; sha256sum original.bin > original.sha256)', ': > "$STATE/disabled"']:
            with self.subTest(point=needle):
                r,d,e=mk();f=d/'patch/install.sh';s=f.read_text()
                self.assertIn(needle,s);f.write_text(s.replace(needle,needle+'; kill -KILL $$',1));rehash(d)
                q=call(d,e,'install','--yes');self.assertNotEqual(q.returncode,0)
                state=r/'etc/mt3600be-wan-eee';self.assertTrue(state.is_dir())
                old=(state/'original.bin').read_bytes() if (state/'original.bin').exists() else None
                self.assertNotEqual(call(d,e,'install','--yes').returncode,0)
                self.assertEqual((state/'original.bin').read_bytes() if (state/'original.bin').exists() else None,old)
                self.assertFalse((r/'enabled').exists());self.assertFalse((r/'running').exists())

    def test_archive_confirmation_lock_and_preserved_snapshot(self):
        r,d,e=mk();state=r/'etc/mt3600be-wan-eee';state.mkdir();(state/'original.bin').write_bytes(b'old')
        h=d/'patch/eee-state';h.write_text(h.read_text().replace('case "$1" in','case "$1" in\n archive) mv "$2" "$3";;',1));rehash(d)
        self.assertEqual(call(d,e,'archive-incomplete',inp='no\n').returncode,0);self.assertTrue(state.exists())
        with (r/'var/lock/mt3600be-wan-eee.lock').open('w') as f:
            fcntl.flock(f,fcntl.LOCK_EX)
            self.assertEqual(call(d,e,'archive-incomplete','--yes').returncode,75)
        q=call(d,e,'archive-incomplete','--yes');self.assertEqual(q.returncode,0,q.stderr)
        archives=list((r/'etc').glob('mt3600be-wan-eee-incomplete.*/transaction/original.bin'))
        self.assertEqual(len(archives),1);self.assertEqual(archives[0].read_bytes(),b'old');self.assertFalse(state.exists())
        self.assertEqual(call(d,e,'install','--yes').returncode,0)
        self.assertEqual(archives[0].read_bytes(),b'old');self.assertEqual((state/'original.bin').read_bytes(),b'original')

    def test_archive_refuses_installed_or_foreign_files(self):
        for path in ('etc/mt3600be-wan-eee/installed','usr/sbin/mt3600be-wan-eee'):
            with self.subTest(path=path):
                r,d,e=mk();state=r/'etc/mt3600be-wan-eee';state.mkdir();(state/'original.bin').write_bytes(b'old')
                (r/path).touch();q=call(d,e,'archive-incomplete','--yes')
                self.assertNotEqual(q.returncode,0);self.assertEqual((state/'original.bin').read_bytes(),b'old')

    def test_compiled_archive_preserves_source_on_existing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'source';src.mkdir();(src/'original.bin').write_bytes(b'old')
            dst=root/'dest';dst.mkdir();(dst/'keep').write_bytes(b'keep')
            q=subprocess.run([str(P/'helper-test'),'archive',str(src),str(dst)],capture_output=True)
            self.assertNotEqual(q.returncode,0);self.assertEqual((src/'original.bin').read_bytes(),b'old')
            self.assertEqual((dst/'keep').read_bytes(),b'keep')
            dst2=root/'new';q=subprocess.run([str(P/'helper-test'),'archive',str(src),str(dst2)],capture_output=True)
            self.assertEqual(q.returncode,0);self.assertEqual((dst2/'original.bin').read_bytes(),b'old')

if __name__=='__main__':unittest.main(verbosity=2)
