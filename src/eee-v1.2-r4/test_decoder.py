from pathlib import Path
import base64,concurrent.futures,gzip,hashlib,io,os,shutil,subprocess,tarfile,tempfile,time
P=Path(__file__).resolve().parent
run=P/'release/mt3600be-eee-tool-v1.2-r4.run'
raw=run.read_bytes(); marker=b'\n__MT3600BE_EEE_PAYLOAD__\n'; header,encoded=raw.split(marker,1)
checks=[]
before=set(Path('/tmp').glob('mt3600be-eee-tool.*'))
with tempfile.TemporaryDirectory(prefix='eee-decode-test-') as td:
 root=Path(td); bindir=root/'bin';bindir.mkdir()
 # No inherited /usr/bin or /bin: host base64 must not hide a missing-router dependency.
 for name in ['awk','mktemp','mkdir','tar','gzip','rm','sha256sum','sh','dirname','cat']:
  (bindir/name).symlink_to(shutil.which(name))
 env=dict(os.environ,PATH=str(bindir))
 def script(name,body):
  f=bindir/name;f.unlink(missing_ok=True);f.write_text('#!/bin/sh\n'+body+'\n');f.chmod(0o755)
 def call(data=None):
  target=run
  if data is not None:target=root/'input.run';target.write_bytes(data)
  return subprocess.run(['/bin/sh',str(target),'check'],env=env,capture_output=True,text=True)
 def result(name,q,ok):
  assert (q.returncode==0)==ok,(name,q.stdout,q.stderr)
  assert ('离线包校验通过' in q.stdout)==ok,(name,q.stdout)
  assert set(Path('/tmp').glob('mt3600be-eee-tool.*'))==before
  checks.append('PASS '+name)
 openssl=shutil.which('openssl');b64=shutil.which('base64');assert openssl and b64
 (bindir/'openssl').symlink_to(openssl)
 result('missing base64 uses real OpenSSL and verifies full payload',call(),True)
 (bindir/'base64').symlink_to(b64)
 script('openssl','exit 99')
 result('base64 is preferred when both tools exist',call(),True)
 (bindir/'base64').unlink();(bindir/'openssl').unlink()
 result('both decoders missing refuse before menu and clean up',call(),False)
 (bindir/'openssl').symlink_to(openssl)
 result('retry after installing available decoder succeeds',call(),True)
 script('base64','exit 9')
 result('present but failing base64 does not fall back',call(),False)
 (bindir/'base64').unlink();script('openssl','exit 8')
 result('OpenSSL failure refuses and cleans up',call(),False)
 script('openssl','exit 0')
 result('OpenSSL success with empty output fails digest',call(),False)
 (bindir/'openssl').unlink();(bindir/'openssl').symlink_to(openssl)
 result('truncated payload under OpenSSL refuses',call(raw[:-100]),False)
 result('corrupt payload under OpenSSL refuses',call(raw.replace(b'H4sI',b'H5sI',1)),False)
 # Change an inner file, recompute only outer digest. Full inner manifest must still reject.
 payload=base64.decodebytes(encoded);buf=io.BytesIO()
 with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as old,tarfile.open(fileobj=buf,mode='w') as new:
  for info in old:
   data=old.extractfile(info).read()
   if info.name=='menu.sh':data+=b'\n# tampered\n';info.size=len(data)
   new.addfile(info,io.BytesIO(data))
 altered=gzip.compress(buf.getvalue(),mtime=0)
 changed=header.replace(hashlib.sha256(payload).hexdigest().encode(),hashlib.sha256(altered).hexdigest().encode())+marker+base64.encodebytes(altered)
 result('OpenSSL retains inner file manifest verification',call(changed),False)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:rr=list(pool.map(lambda _:call(),range(2)))
 assert all(q.returncode==0 for q in rr)
 assert set(Path('/tmp').glob('mt3600be-eee-tool.*'))==before
 checks.append('PASS simultaneous OpenSSL extractors remain isolated and clean up')
 # Decoder signals its parent; no unpacked menu may run and own temporary directory is removed.
 script('openssl','kill -TERM "$PPID"; exit 1')
 result('TERM during OpenSSL decoding fails closed and cleans up',call(),False)
 (bindir/'openssl').unlink();(bindir/'openssl').symlink_to(openssl)
 result('retry after decoder interruption succeeds',call(),True)
 # BusyBox ash with the same missing-base64 PATH and real OpenSSL.
 q=subprocess.run([shutil.which('busybox'),'sh',str(run),'check'],env=env,capture_output=True,text=True)
 result('BusyBox ash plus OpenSSL missing-base64 path works',q,True)
(P/'decoder-results.txt').write_text('\n'.join(checks)+'\n');print('\n'.join(checks))
