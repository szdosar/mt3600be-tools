from pathlib import Path
import os,sys,hashlib,subprocess,shutil,concurrent.futures,tempfile,signal,time
P=Path(__file__).resolve().parent
ns={'__file__':str(P/'test_patch.py')};exec((P/'test_patch.py').read_text().split('passed=[]')[0],ns)
results=[]
def fixture():
 r,s,w,e=ns['fixture']();d=r/'tool';(d/'patch').mkdir(parents=True)
 svc=r/'etc/init.d/mt3600be-wan-eee'
 svc.write_text('#!/bin/sh\ncase "$1" in enabled|running) exit 0;; *) echo "service:$1" >> "$FIX/actions";; esac\n')
 helper=r/'usr/libexec/mt3600be-eee-state';helper.write_text(helper.read_text().replace(' *) exit 2;;',' validate) [ "$(cat "$2")" = original ];;\n *) exit 2;;'))
 hp=r/'etc/hotplug.d/iface/98-mt3600be-wan-eee';hp.parent.mkdir(parents=True);hp.write_text('#!/bin/sh\nexit 0\n')
 pairs=[(helper,'eee-state'),(w,'mt3600be-wan-eee'),(svc,'init'),(hp,'hotplug')]
 for f,n in pairs:shutil.copy2(f,d/'patch'/n)
 (s/'files.sha256').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f)+'\n' for f,n in pairs))
 (d/'patch/install.sh').write_text('#!/bin/sh\necho install >> "$FIX/actions"\n')
 (d/'patch/SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in (d/'patch').iterdir()))
 menu=(P/'tool/menu.sh').read_text()
 for pref in ['/etc/','/usr/','/tmp/sysinfo/','/sys/']:menu=menu.replace(pref,str(r)+pref)
 (d/'menu.sh').write_text(menu)
 (r/'bin/id').write_text('#!/bin/sh\necho 0\n');(r/'bin/id').chmod(0o755)
 return r,s,d,e

def call(d,e,*a,inp=''):
 return subprocess.run(['sh',str(d/'menu.sh'),*a],env=e,input=inp,text=True,capture_output=True)
def record(n):results.append('PASS '+n)
r,s,d,e=fixture();assert call(d,e,'status').returncode==0 and not (r/'actions').read_text();record('status read-only')
r,s,d,e=fixture();before=(s/'original.bin').read_bytes();assert call(d,e,'install','--yes').returncode==0;assert not (r/'actions').read_text() and (s/'original.bin').read_bytes()==before;record('already installed preserves baseline and does not reenable')
r,s,d,e=fixture();shutil.rmtree(s);assert call(d,e,'install',inp='no\n').returncode==0 and not (r/'actions').read_text();record('install cancellation no mutation')
r,s,d,e=fixture();(r/'etc/glversion').write_text('other');assert call(d,e,'rollback','--yes').returncode!=0 and not (r/'actions').read_text();record('wrong firmware refusal')
r,s,d,e=fixture();(r/'usr/libexec/mt3600be-eee-state').write_text('corrupt');assert call(d,e,'rollback','--yes').returncode!=0 and not (r/'actions').read_text();record('damaged installed file refusal')
r,s,d,e=fixture();(s/'installed').unlink();assert call(d,e,'install','--yes').returncode!=0 and not (r/'actions').read_text();record('incomplete old transaction refuses overwrite')
r,s,d,e=fixture();assert call(d,e,'rollback',inp='no\n').returncode==0 and not (r/'actions').read_text();record('rollback cancellation')
r,s,d,e=fixture();(s/'disabled').touch();before=(s/'original.bin').read_bytes();assert call(d,e,'rollback','--yes').returncode==0;assert (s/'rolled-back').exists() and before==(s/'original.bin').read_bytes();record('rollback pending retry via tool')
r,s,d,e=fixture();import fcntl
with (r/'var/lock/mt3600be-wan-eee.lock').open('w') as f:
 fcntl.flock(f,fcntl.LOCK_EX);assert call(d,e,'enable','--yes').returncode==75
assert not (r/'actions').read_text();record('busy lock refusal')
r,s,d,e=fixture();assert call(d,e,inp='1\n').returncode==0 and not (r/'actions').read_text();record('menu status read-only')
# Run self-extractor on dt only in check/menu-exit mode (never router install).
run=P/'release/mt3600be-eee-tool-v1.2-r4.run';before=set(Path('/tmp').glob('mt3600be-eee-tool.*'))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as x:
 rr=list(x.map(lambda _:subprocess.run(['sh',str(run),'check'],capture_output=True),range(2)))
assert all(r.returncode==0 for r in rr) and set(Path('/tmp').glob('mt3600be-eee-tool.*'))==before;record('two extractors isolated and clean up')
for label,data in [('empty',b''),('truncated',run.read_bytes()[:-100]),('corrupt',run.read_bytes().replace(b'H4sI',b'H5sI',1))]:
 f=P/('bad-'+label+'.run');f.write_bytes(data);r=subprocess.run(['sh',str(f),'check'],capture_output=True)
 if label=='empty':assert not r.stdout # empty shell script has no installation code; external sha check required
 else:assert r.returncode!=0
 assert set(Path('/tmp').glob('mt3600be-eee-tool.*'))==before
 record(label+' file does not execute package')
# Pause at the menu, replace source; already-checked independent payload remains in use.
f=P/'replace-test.run';shutil.copy2(run,f)
q=subprocess.Popen(['sh',str(f)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
for _ in range(300):
 active=set(Path('/tmp').glob('mt3600be-eee-tool.*'))-before
 if active and all((x/'run/menu.sh').exists() for x in active):break
 time.sleep(.01)
else:raise AssertionError('extract timeout')
time.sleep(.1);assert q.poll() is None;f.write_text('echo BAD_REPLACED_SCRIPT\n')
out,err=q.communicate('0\n',timeout=5);assert q.returncode==0 and 'BAD_REPLACED_SCRIPT' not in out
assert set(Path('/tmp').glob('mt3600be-eee-tool.*'))==before;record('replaced source does not replace executing independent copy')
q=subprocess.Popen(['sh',str(run)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
for _ in range(300):
 active=set(Path('/tmp').glob('mt3600be-eee-tool.*'))-before
 if active and all((x/'run/menu.sh').exists() for x in active):break
 time.sleep(.01)
time.sleep(.1);assert q.poll() is None;q.terminate();q.communicate(timeout=5)
assert q.returncode==130 and set(Path('/tmp').glob('mt3600be-eee-tool.*'))==before;record('TERM at menu cleans only own temporary directory')
assert subprocess.run(['sh',str(run),'check'],capture_output=True).returncode==0;record('retry after interruption succeeds')
(P/'tool-results.txt').write_text('\n'.join(results)+'\n');print('\n'.join(results))
