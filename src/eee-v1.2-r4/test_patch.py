from pathlib import Path
import os,subprocess,tempfile,hashlib,concurrent.futures,fcntl,time
P=Path(__file__).resolve().parent; PKG=P/'patch-v1'
def fixture():
 r=Path(tempfile.mkdtemp(prefix='eee-test-',dir=P))
 for n in ['etc/mt3600be-wan-eee','etc/init.d','usr/sbin','usr/libexec','var/lock','tmp/sysinfo','sys/class/net/eth0/phydev','bin']:(r/n).mkdir(parents=True,exist_ok=True)
 (r/'tmp/sysinfo/board_name').write_text('glinet,gl-mt3600be\n');(r/'etc/glversion').write_text('4.9.1-op25');(r/'sys/class/net/eth0/phydev/uevent').write_text('DRIVER=RTL8221B-VB-CG 2.5Gbps PHY (C45)\n')
 s=(PKG/'mt3600be-wan-eee').read_text()
 for prefix in ['/etc/','/usr/','/var/','/tmp/sysinfo/','/sys/']:s=s.replace(prefix,str(r)+prefix)
 wrapper=r/'usr/sbin/mt3600be-wan-eee';wrapper.write_text(s);wrapper.chmod(0o755)
 helper=r/'usr/libexec/mt3600be-eee-state'
 helper.write_text('''#!/bin/sh
set -eu
case "$1" in
 read) if [ "$(cat "$FIX/state")" = off ]; then echo 'eee_enabled=0 eee_active=0 tx_lpi_enabled=0 tx_lpi_timer=1000 supported=0x28 advertised=0x0 lp_advertised=0x28 phy7_mmd7_003c=0x0000'; else echo 'eee_enabled=0 eee_active=1 tx_lpi_enabled=1 tx_lpi_timer=1000 supported=0x28 advertised=0x28 lp_advertised=0x28 phy7_mmd7_003c=0x0006'; fi;;
 disable) sleep 0.1; echo disable >> "$FIX/actions"; echo off > "$FIX/state";;
 restore-checked) echo restore >> "$FIX/actions"; if [ -e "$FIX/fail-restore" ]; then exit 7; fi; echo on > "$FIX/state";;
 *) exit 2;;
esac
''');helper.chmod(0o755)
 service=r/'etc/init.d/mt3600be-wan-eee';service.write_text('#!/bin/sh\necho "service:$1" >> "$FIX/actions"\n');service.chmod(0o755)
 for n,body in [('uname','echo 6.12.94'),('logger',':')]:
  f=r/'bin'/n;f.write_text('#!/bin/sh\n'+body+'\n');f.chmod(0o755)
 st=r/'etc/mt3600be-wan-eee';(st/'original.bin').write_bytes(b'original');(st/'original.bin').chmod(0o600)
 (st/'original.sha256').write_text(hashlib.sha256(b'original').hexdigest()+'  original.bin\n');(st/'installed').touch()
 (st/'files.sha256').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f)+'\n' for f in [wrapper,helper,service]))
 (r/'state').write_text('on\n');(r/'actions').write_text('')
 env=dict(os.environ,FIX=str(r),PATH=str(r/'bin')+':'+os.environ['PATH'])
 return r,st,wrapper,env
passed=[]
def run(w,e,cmd):return subprocess.run([str(w),cmd],env=e,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
def record(n):passed.append(n);print('PASS '+n,flush=True)
r,s,w,e=fixture();assert run(w,e,'apply').returncode==0;assert run(w,e,'apply').returncode==0;assert (r/'actions').read_text().splitlines()==['disable'];record('重复 apply 不重复修改已关闭 EEE')
r,s,w,e=fixture()
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda _:run(w,e,'apply'),range(8)))
assert all(x.returncode in (0,75) for x in results);assert run(w,e,'apply').returncode==0;assert (r/'actions').read_text().splitlines()==['disable'];record('8 个并发 apply 仅设置一次')
r,s,w,e=fixture();(s/'original.bin').write_bytes(b'bad');assert run(w,e,'apply').returncode!=0;assert (r/'actions').read_text()=='';record('原始状态摘要损坏在修改前拒绝')
r,s,w,e=fixture();(r/'etc/glversion').write_text('other');assert run(w,e,'apply').returncode!=0;assert (r/'actions').read_text()=='';record('固件不匹配在修改前拒绝')
r,s,w,e=fixture();assert run(w,e,'apply').returncode==0;assert run(w,e,'rollback').returncode==0;assert (s/'disabled').exists() and (s/'rolled-back').exists();assert (r/'state').read_text().strip()=='on';a=(r/'actions').read_text();assert run(w,e,'apply').returncode==0 and (r/'actions').read_text()==a;record('回滚恢复原状态并阻止后续自动 apply')
r,s,w,e=fixture();run(w,e,'apply');(r/'fail-restore').touch();assert run(w,e,'rollback').returncode!=0;assert (s/'disabled').exists() and not (s/'rolled-back').exists();a=(r/'actions').read_text();run(w,e,'apply');assert (r/'actions').read_text()==a;(r/'fail-restore').unlink();assert run(w,e,'rollback').returncode==0;assert (r/'state').read_text().strip()=='on';record('恢复中断后保持禁用并可重试回滚')
r,s,w,e=fixture();run(w,e,'rollback');assert run(w,e,'enable').returncode==0;assert not (s/'disabled').exists();assert (r/'state').read_text().strip()=='off';record('回滚后重新 enable 可恢复补丁')
r,s,w,e=fixture();assert run(w,e,'status').returncode==0;assert (r/'actions').read_text()=='';record('status 只读')
r,s,w,e=fixture();(s/'disabled').touch();assert run(w,e,'apply').returncode==0;assert (r/'actions').read_text()=='';record('回滚标记存在时热插拔和轮询安全跳过')
r,s,w,e=fixture();f=(r/'var/lock/mt3600be-wan-eee.lock').open('w');fcntl.flock(f,fcntl.LOCK_EX);assert run(w,e,'apply').returncode==75;assert (r/'actions').read_text()=='';f.close();assert run(w,e,'apply').returncode==0;record('锁忙安全退出，释放后可重试')
r,s,w,e=fixture();h=(PKG/'hotplug').read_text().replace('/etc/',str(r)+'/etc/').replace('/usr/',str(r)+'/usr/');hp=r/'hook';hp.write_text(h)
for act,dev in [('ifdown','eth0'),('ifup','wlan0'),('ifupdate','eth1')]:assert subprocess.run(['sh',str(hp)],env=dict(e,ACTION=act,DEVICE=dev)).returncode==0
assert (r/'actions').read_text()=='';assert subprocess.run(['sh',str(hp)],env=dict(e,ACTION='ifup',DEVICE='eth0')).returncode==0;assert (r/'actions').read_text().splitlines()==['disable'];record('热插拔仅接受 eth0 的 ifup/ifupdate')
(P/'local-test-results.txt').write_text('\n'.join('PASS '+n for n in passed)+'\n')
print(str(len(passed))+' isolated tests passed')
