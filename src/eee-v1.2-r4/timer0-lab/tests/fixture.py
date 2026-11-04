from pathlib import Path
import subprocess,tempfile,hashlib,os,time,concurrent.futures,shutil,json
P=Path(__file__).resolve().parent
SOURCE=P.parent.parent
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
