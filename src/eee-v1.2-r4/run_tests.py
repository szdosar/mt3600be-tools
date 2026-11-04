from pathlib import Path
import subprocess,sys,os,json,hashlib,tarfile,io,base64
P=Path(__file__).resolve().parent
(P/'validation.json').unlink(missing_ok=True)  # Never retain a stale PASS after a failed run.
subprocess.run([sys.executable,str(P/'build_tool.py')],check=True,cwd=P)
for name in ['test_patch.py','test_install.py','test_interruptions.py','test_helper.py','test_tool.py','test_combined.py','test_decoder.py']:
 subprocess.run([sys.executable,str(P/name)],check=True,cwd=P)
b=P/'busybox-bin';b.mkdir(exist_ok=True)
for n in ['sh','awk','base64','sha256sum','mktemp','mkdir','tar','rm','dirname','cmp','cat','id','uname','grep']:
 if not (b/n).exists():(b/n).symlink_to('/usr/bin/busybox')
e=dict(os.environ,PATH=str(b)+':/usr/bin:/bin')
f=P/'release/mt3600be-eee-tool-v1.2-r4.run'
for args,inp in [(['check'],''),([], '0\n')]:
 subprocess.run(['/usr/bin/busybox','sh',str(f),*args],env=e,input=inp,text=True,capture_output=True,check=True)
checks=[]
for n in ['local-test-results.txt','installer-test-results.txt','interruption-results.txt','helper-results.txt','tool-results.txt','combined-results.txt','decoder-results.txt']:
 checks.extend((P/n).read_text().splitlines())
checks.extend(['PASS BusyBox extractor and checksums','PASS BusyBox interactive menu exit'])
assert len(checks)==69 and all(x.startswith('PASS ') for x in checks)
payload=base64.decodebytes(f.read_bytes().split(b'\n__MT3600BE_EEE_PAYLOAD__\n',1)[1])
allowed={'menu.sh','SHA256SUMS'}|{'patch/'+n for n in ['eee-state','eee-state.c','mt3600be-wan-eee','init','hotplug','install.sh','README.md','SHA256SUMS']}
with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as t:
 assert set(t.getnames())==allowed
 for entry in t:
  assert entry.isfile() and not entry.issym() and not entry.islnk()
 for n in ['eee-state','mt3600be-wan-eee','init','hotplug']:
  assert t.extractfile('patch/'+n).read()==(P/'patch-v1'/n).read_bytes()
# Check delivered run, checksum companion and original ZIP agree; don't silently repackage discrepancies.
import zipfile
with zipfile.ZipFile(P/'release/mt3600be-eee-tool-v1.2-r4.zip') as z:
 assert set(z.namelist())=={'mt3600be-eee-tool-v1.2-r4.run','mt3600be-eee-tool-v1.2-r4.sha256','小白使用说明.md'}
 for n in z.namelist():assert z.read(n)==(P/'release'/n).read_bytes()
subprocess.run(['sha256sum','-c','mt3600be-eee-tool-v1.2-r4.sha256'],cwd=P/'release',check=True)
subprocess.run(['sha256sum','-c','mt3600be-eee-tool-v1.2-r4.zip.sha256'],cwd=P/'release',check=True)
subprocess.run([sys.executable,str(P/'test_initial_snapshot_v12.py')],check=True,cwd=P)
subprocess.run([sys.executable,str(P/'test-review-r2.py')],check=True,cwd=P)
subprocess.run([sys.executable,str(P/'test-rollback-r3.py')],check=True,cwd=P)
result={'scope':'local isolation only; no router connection','passed':len(checks),'checks':checks,'additional_snapshot_test_methods':7,'additional_review_test_methods':6,'additional_rollback_test_methods':3,'runtime_payload':'v1.2-r4 candidate; checked rollback','run_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'archive_allowlist_verified':True,'device_backups_included':False}
(P/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('OFFLINE CANDIDATE GATE PASS: 69 existing checks, 7 snapshot, 6 review, 3 rollback methods; no router validation')
