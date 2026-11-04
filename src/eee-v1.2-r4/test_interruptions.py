from pathlib import Path
import os,sys,subprocess,hashlib,signal,time,concurrent.futures
P=Path(__file__).resolve().parent
ns={'__file__':str(P/'test_patch.py')}
exec((P/'test_patch.py').read_text().split('passed=[]')[0],ns)
fixture=ns['fixture'];results=[]
def run(w,e,cmd):return subprocess.run([str(w),cmd],env=e,capture_output=True,text=True)
def rehash(r,s):
 fs=[r/'usr/sbin/mt3600be-wan-eee',r/'usr/libexec/mt3600be-eee-state',r/'etc/init.d/mt3600be-wan-eee']
 (s/'files.sha256').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f)+'\n' for f in fs))
def wait_ready(r,p):
 for _ in range(300):
  if (r/'ready').exists():return
  if p.poll() is not None:raise AssertionError('exited before interruption point')
  time.sleep(.01)
 raise AssertionError('checkpoint timeout')
checkpoint='''checkpoint() { if [ "${POINT:-}" = "$1" ]; then : > "$FIX/ready"; while [ ! -e "$FIX/release" ]; do sleep 0.02; done; fi; }
'''
def enhanced():
 r,s,w,e=fixture()
 svc=r/'etc/init.d/mt3600be-wan-eee'
 svc.write_text('''#!/bin/sh
set -eu
'''+checkpoint+'''case "$1" in
 disable) rm -f "$FIX/boot-enabled"; checkpoint after-disable;;
 stop) rm -f "$FIX/service-running"; checkpoint after-stop;;
 enable) touch "$FIX/boot-enabled";;
 start) touch "$FIX/service-running";;
esac
echo service:$1 >> "$FIX/actions"
''')
 h=r/'usr/libexec/mt3600be-eee-state'
 s1=h.read_text().replace('set -eu\n','set -eu\n'+checkpoint).replace('restore-checked) echo restore','restore-checked) checkpoint before-restore; echo restore').replace('echo on > "$FIX/state";;','echo on > "$FIX/state"; checkpoint after-restore;;')
 h.write_text(s1)
 for f in ['boot-enabled','service-running']:(r/f).touch()
 rehash(r,s);return r,s,w,e
for point in ['after-disable','after-stop','before-restore','after-restore']:
 r,s,w,e=enhanced();assert run(w,e,'apply').returncode==0
 baseline=(s/'original.bin').read_bytes()
 child=subprocess.Popen([str(w),'rollback'],env=dict(e,POINT=point),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,start_new_session=True)
 wait_ready(r,child);os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 assert (s/'disabled').exists() and not (s/'rolled-back').exists()
 acts=(r/'actions').read_bytes();assert run(w,e,'apply').returncode==0 and acts==(r/'actions').read_bytes()
 assert run(w,e,'rollback').returncode==0
 assert (r/'state').read_text().strip()=='on' and (s/'rolled-back').exists()
 assert not (r/'boot-enabled').exists() and not (r/'service-running').exists()
 assert (s/'original.bin').read_bytes()==baseline
 results.append('PASS SIGKILL rollback '+point+'; retry restores baseline without overwrite')
r,s,w,e=enhanced();run(w,e,'apply')
child=subprocess.Popen([str(w),'rollback'],env=dict(e,POINT='before-restore'),stdout=subprocess.DEVNULL,start_new_session=True)
wait_ready(r,child)
assert run(w,e,'apply').returncode==75 and run(w,e,'enable').returncode==75 and run(w,e,'rollback').returncode==75
(r/'release').touch();assert child.wait(timeout=5)==0
assert run(w,e,'apply').returncode==0 and (r/'state').read_text().strip()=='on'
results.append('PASS rollback excludes apply/enable/second rollback concurrently')
# Killing only the shell must not release its lock while its helper still owns fd 9.
r,s,w,e=enhanced();run(w,e,'apply')
child=subprocess.Popen([str(w),'rollback'],env=dict(e,POINT='before-restore'),stdout=subprocess.DEVNULL,start_new_session=True)
wait_ready(r,child);os.kill(child.pid,signal.SIGKILL);child.wait(timeout=5)
assert run(w,e,'rollback').returncode==75
(r/'release').touch()
for _ in range(100):
 res=run(w,e,'rollback')
 if res.returncode==0:break
 assert res.returncode==75;time.sleep(.02)
else:raise AssertionError('inherited lock not released')
assert (r/'state').read_text().strip()=='on'
results.append('PASS orphan helper retains lock; later retry succeeds')
# Execute the actual init start function with procd API substituted only for the test.
for disabled,installed,expected in [(False,True,True),(True,True,False),(False,False,False)]:
 r,s,w,e=enhanced()
 if disabled:(s/'disabled').touch()
 if not installed:(s/'installed').unlink()
 script=(P/'patch-v1/init').read_text().replace('/etc/',str(r)+'/etc/').replace('/usr/',str(r)+'/usr/')
 init=r/'init-test';init.write_text(script+'''\nprocd_open_instance() { echo open >> "$FIX/boot-actions"; }
procd_set_param() { echo "$*" >> "$FIX/boot-actions"; }
procd_close_instance() { :; }
start_service
''')
 assert subprocess.run(['sh',str(init)],env=e).returncode==0
 assert (r/'boot-actions').exists()==expected
 results.append('PASS init gate disabled='+str(disabled)+' installed='+str(installed))
(P/'interruption-results.txt').write_text('\n'.join(results)+'\n');print('\n'.join(results))
