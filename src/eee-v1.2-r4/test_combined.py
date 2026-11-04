from pathlib import Path
import subprocess,tempfile,hashlib,os,time,concurrent.futures,shutil,json
P=Path(__file__).resolve().parent
SOURCE=P
results=[]
def mk():
 r=Path(tempfile.mkdtemp(prefix='combined-',dir=P));d=r/'bundle';(d/'patch').mkdir(parents=True)
 for n in ['etc/init.d','etc/hotplug.d/iface','etc/rc.d','usr/sbin','usr/libexec','var/lock','tmp/sysinfo','sys/class/net/eth0/phydev','bin','etc/config']:(r/n).mkdir(parents=True,exist_ok=True)
 (r/'tmp/sysinfo/board_name').write_text('glinet,gl-mt3600be\n');(r/'etc/glversion').write_text('4.9.1-op25\n');(r/'sys/class/net/eth0/phydev/uevent').write_text('DRIVER=RTL8221B-VB-CG 2.5Gbps PHY (C45)\n')
 for n in ['network','wireless','dhcp','firewall','passwall2','vpn']:
  f=r/'etc/config'/n;f.write_text('synthetic '+n+' preserved\n');f.chmod(0o600)
 for n in ['id','uname','logger']:
  body={'id':'echo 0','uname':'echo 6.12.94','logger':':'}[n];f=r/'bin'/n;f.write_text('#!/bin/sh\n'+body+'\n');f.chmod(0o755)
 for src,dest in [(SOURCE/'tool/menu.sh',d/'menu.sh')]+[(SOURCE/'patch-v1'/n,d/'patch'/n) for n in ['install.sh','mt3600be-wan-eee','hotplug']]:
  s=src.read_text()
  for pre in ['/etc/','/usr/','/var/','/tmp/sysinfo/','/sys/']:s=s.replace(pre,str(r)+pre)
  dest.write_text(s);dest.chmod(0o755)
 (d/'patch/init').write_text('''#!/bin/sh
set -eu
case "$1" in
 enable) : > "$FIX/enabled";; disable) rm -f "$FIX/enabled";;
 start) : > "$FIX/running";; stop) rm -f "$FIX/running";;
 enabled) [ -e "$FIX/enabled" ];; running) [ -e "$FIX/running" ];;
esac
''')
 (d/'patch/eee-state').write_text('''#!/bin/sh
set -eu
case "$1" in
 save) echo save >> "$FIX/actions"; printf original > "$2"; if [ -e "$FIX/pause-save" ]; then : > "$FIX/save-ready"; while [ ! -e "$FIX/release" ]; do sleep .02; done; fi;;
 validate) [ "$(cat "$2")" = original ];;
 read) if [ "$(cat "$FIX/phy")" = off ]; then echo 'eee_enabled=0 eee_active=0 tx_lpi_enabled=0 tx_lpi_timer=1000 supported=0x28 advertised=0x0 lp_advertised=0x28 phy7_mmd7_003c=0x0000'; else echo on; fi;;
 disable) echo disable >> "$FIX/actions"; echo off > "$FIX/phy";;
 restore-checked) echo restore >> "$FIX/actions"; echo on > "$FIX/phy";;
esac
''')
 (d/'patch/eee-state').chmod(0o755)
 (d/'patch/SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in (d/'patch').iterdir()))
 (r/'actions').touch();(r/'phy').write_text('on\n')
 e=dict(os.environ,FIX=str(r),PATH=str(r/'bin')+':'+os.environ['PATH'])
 return r,d,e

def call(d,e,*a,inp=''):
 return subprocess.run(['sh',str(d/'menu.sh'),*a],input=inp,text=True,env=e,capture_output=True)
def baseline(r):return {f.name:(f.read_bytes(),f.stat().st_mode&0o777) for f in (r/'etc/config').iterdir()}
def record(n):results.append('PASS '+n)
for answer in ['', '\n','yes\n','NO\n']:
 r,d,e=mk();before=baseline(r);q=call(d,e,'install',inp=answer);assert q.returncode==0 and not (r/'etc/mt3600be-wan-eee').exists() and baseline(r)==before
record('install EOF/blank/lowercase/NO do not confirm')
r,d,e=mk();before=baseline(r);assert call(d,e,'install',inp='YES\n').returncode==0
orig=(r/'etc/mt3600be-wan-eee/original.bin').read_bytes();assert (r/'actions').read_text().splitlines()==['save','disable']
assert call(d,e,'install','--yes').returncode==0 and (r/'actions').read_text().splitlines()==['save','disable']
for answer in ['', '\n','yes\n','NO\n']:
 assert call(d,e,'rollback',inp=answer).returncode==0 and (r/'phy').read_text().strip()=='off'
assert call(d,e,'rollback',inp='YES\n').returncode==0
assert call(d,e,'install','--yes').returncode==0 and (r/'phy').read_text().strip()=='on'
assert call(d,e,'rollback','--yes').returncode==0
assert (r/'etc/mt3600be-wan-eee/original.bin').read_bytes()==orig and baseline(r)==before
record('real menu+installer YES, repeated install/rollback preserve baseline/config/modes')
r,d,e=mk();before=baseline(r);(r/'pause-save').touch()
a=subprocess.Popen(['sh',str(d/'menu.sh'),'install','--yes'],env=e,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
for _ in range(200):
 if (r/'save-ready').exists():break
 time.sleep(.01)
else:raise AssertionError('no saved baseline checkpoint')
b=call(d,e,'install','--yes');assert b.returncode!=0
assert (r/'actions').read_text().splitlines()==['save']
(r/'release').touch();out,err=a.communicate(timeout=5);assert a.returncode==0,(out,err)
assert call(d,e,'install','--yes').returncode==0
assert (r/'actions').read_text().splitlines()==['save','disable'] and baseline(r)==before
record('two first installers serialize; loser retry never replaces backup')
# Terminal race after both users have opened the install confirmation, before either creates state.
r,d,e=mk();qs=[subprocess.Popen(['sh',str(d/'menu.sh'),'install'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=e) for _ in range(2)]
time.sleep(.1)
with concurrent.futures.ThreadPoolExecutor() as pool:rr=list(pool.map(lambda q:q.communicate('YES\n',timeout=5),qs))
assert sum(q.returncode==0 for q in qs)>=1 and (r/'actions').read_text().splitlines()==['save','disable']
assert call(d,e,'install','--yes').returncode==0;record('two pending YES prompts still yield one saved baseline')
# Installation disk failure -> no operation on synthetic configuration; explicit incomplete state refuses retry.
r,d,e=mk();before=baseline(r);ln=r/'bin/ln';ln.write_text('#!/bin/sh\ncase "$2" in */etc/init.d/*) exit 1;; esac\nexec /usr/bin/ln "$@"\n');ln.chmod(0o755)
q=call(d,e,'install','--yes');assert q.returncode!=0
orig=(r/'etc/mt3600be-wan-eee/original.bin').read_bytes()
ln.unlink();q=call(d,e,'install','--yes');assert q.returncode!=0
assert (r/'etc/mt3600be-wan-eee/original.bin').read_bytes()==orig and baseline(r)==before
assert not (r/'enabled').exists() and not (r/'running').exists()
record('failed first install retry refuses incomplete transaction and keeps backup/config')
# Exact documented upload gate against partial files; only execute a marker after checksum success.
src=SOURCE/'release/mt3600be-eee-tool-v1.2-r4.run';raw=src.read_bytes();u=Path(tempfile.mkdtemp(prefix='upload-',dir=P));target=u/src.name;manifest=u/'mt3600be-eee-tool-v1.2-r4.sha256';manifest.write_text(hashlib.sha256(raw).hexdigest()+'  '+src.name+'\n')
for n in [0,1,100,len(raw)//2,len(raw)-1]:
 target.write_bytes(raw[:n]);q=subprocess.run(['sh','-c','sha256sum -c mt3600be-eee-tool-v1.2-r4.sha256 && touch executed'],cwd=u,capture_output=True);assert q.returncode!=0 and not (u/'executed').exists()
target.write_bytes(raw);q=subprocess.run(['sh','-c','sha256sum -c mt3600be-eee-tool-v1.2-r4.sha256 && touch executed'],cwd=u,capture_output=True);assert q.returncode==0 and (u/'executed').exists()
record('five upload truncation points reject execution; full retransmission succeeds')
# mkdir first in upload instructions must stop on a previous directory, not overwrite its contents.
u=Path(tempfile.mkdtemp(prefix='upload-dir-',dir=P));(u/'old').mkdir();(u/'old/backup').write_text('keep')
q=subprocess.run(['sh','-c','mkdir -m 700 old && touch overwrite'],cwd=u,capture_output=True)
assert q.returncode!=0 and not (u/'overwrite').exists() and (u/'old/backup').read_text()=='keep'
record('existing upload directory halts command chain')
(P/'combined-results.txt').write_text('\n'.join(results)+'\n');print('\n'.join(results))
