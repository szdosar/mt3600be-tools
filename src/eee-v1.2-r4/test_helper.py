from pathlib import Path
import subprocess,struct,os,signal,hashlib
P=Path(__file__).resolve().parent
subprocess.run(['cc','-Wall','-Wextra','-Dioctl=test_ioctl','-Dsocket=test_socket','-Dfstat=test_fstat','-c',str(P/'patch-v1/eee-state.c'),'-o',str(P/'helper-test.o')],check=True)
subprocess.run(['cc',str(P/'helper-test.o'),str(P/'mock_ioctl.c'),'-o',str(P/'helper-test')],check=True)
# Synthetic standard EEE fields; no saved router record is used.
original=struct.pack('=12I',0x45454531,0,0x28,0x28,0x28,1,0,1,1000,0,0,6)
base=P/'helper-baseline.bin';base.write_bytes(original);base.chmod(0o600)
results=[]
for phase in ['after-seteee','after-miiwrite','after-nway']:
 model=P/('model-'+phase);model.write_bytes(original+struct.pack('II',0,0))
 env=dict(os.environ,MODEL=str(model));cmd=[str(P/'helper-test')]
 assert subprocess.run(cmd+['disable'],env=env,capture_output=True).returncode==0
 r=subprocess.run(cmd+['restore-checked',str(base),hashlib.sha256(original).hexdigest()],env=dict(env,CRASH=phase),capture_output=True)
 assert r.returncode==-signal.SIGKILL
 r=subprocess.run(cmd+['restore-checked',str(base),hashlib.sha256(original).hexdigest()],env=env,capture_output=True)
 assert r.returncode==0,r.stderr
 state=model.read_bytes();assert state[:4]==original[:4] and state[8:48]==original[8:48] and struct.unpack('I',state[48:52])[0]==0
 assert base.read_bytes()==original
 results.append('PASS compiled helper SIGKILL '+phase+'; retry restores fields and negotiation')
# Corrupt input must not touch emulated hardware even with the correct outer digest.
model=P/'model-bad';model.write_bytes(original+struct.pack('II',0,0));bad=P/'helper-bad.bin';bad.write_bytes(b'x'*len(original));bad.chmod(0o600)
before=model.read_bytes();r=subprocess.run([str(P/'helper-test'),'restore',str(bad)],env=dict(os.environ,MODEL=str(model)),capture_output=True)
assert r.returncode!=0 and model.read_bytes()==before
results.append('PASS compiled helper invalid record refuses before ioctl mutation')
(P/'helper-results.txt').write_text('\n'.join(results)+'\n');print('\n'.join(results))
