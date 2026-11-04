from pathlib import Path
import os,tempfile,subprocess,hashlib
P=Path(__file__).resolve().parent;PKG=P/'patch-v1'
def setup():
 r=Path(tempfile.mkdtemp(prefix='install-test-',dir=P));d=r/'package';d.mkdir()
 for n in ['etc/init.d','etc/hotplug.d/iface','usr/sbin','usr/libexec','var/lock','tmp/sysinfo','sys/class/net/eth0/phydev','bin']:(r/n).mkdir(parents=True,exist_ok=True)
 (r/'tmp/sysinfo/board_name').write_text('glinet,gl-mt3600be\n');(r/'etc/glversion').write_text('4.9.1-op25');(r/'sys/class/net/eth0/phydev/uevent').write_text('DRIVER=RTL8221B-VB-CG 2.5Gbps PHY (C45)\n')
 s=(PKG/'install.sh').read_text()
 for prefix in ['/etc/','/usr/','/var/','/tmp/sysinfo/','/sys/']:s=s.replace(prefix,str(r)+prefix)
 (d/'install.sh').write_text(s)
 for n in ['init','hotplug','mt3600be-wan-eee']:(d/n).write_text('#!/bin/sh\nexit 0\n')
 (d/'eee-state').write_text('''#!/bin/sh
case "$1" in
 assess) exit 0;;
 save) printf original > "$2";;
 import) [ "$(cat "$2")" = original ] || exit 4; cp "$2" "$3";;
 validate) [ "$(cat "$2")" = original ];;
 *) exit 2;;
esac
''');(d/'eee-state').chmod(0o755)
 (r/'bin/uname').write_text('#!/bin/sh\necho 6.12.94\n');(r/'bin/uname').chmod(0o755)
 (d/'SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in sorted(d.iterdir())))
 e=dict(os.environ,PATH=str(r/'bin')+':'+os.environ['PATH'])
 return r,d,e
passed=[]
def record(n):passed.append(n);print('PASS '+n)
def run(d,e,*args):return subprocess.run(['sh',str(d/'install.sh'),*args],env=e,capture_output=True,text=True)
r,d,e=setup();assert run(d,e).returncode==0;orig=(r/'etc/mt3600be-wan-eee/original.bin').read_bytes();assert run(d,e).returncode!=0;assert (r/'etc/mt3600be-wan-eee/original.bin').read_bytes()==orig;record('正常安装且重复安装拒绝覆盖原状态')
r,d,e=setup();t=r/'usr/sbin/mt3600be-wan-eee';t.write_text('existing');assert run(d,e).returncode!=0;assert t.read_text()=='existing';assert not (r/'etc/mt3600be-wan-eee').exists();record('已有目标文件安装前安全拒绝')
r,d,e=setup();(d/'hotplug').write_text('corrupted');assert run(d,e).returncode!=0;assert not (r/'etc/mt3600be-wan-eee').exists();record('包校验失败不创建事务')
r,d,e=setup();bad=r/'bad-baseline';bad.write_text('bad');assert run(d,e,str(bad)).returncode!=0;assert not (r/'etc/mt3600be-wan-eee/original.bin').exists();assert not (r/'usr/sbin/mt3600be-wan-eee').exists();record('原始状态验证失败保留不完整事务且不安装')
r,d,e=setup();ln=r/'bin/ln';ln.write_text('#!/bin/sh\ncase "$2" in */etc/init.d/*) exit 1;; esac\nexec /usr/bin/ln "$@"\n');ln.chmod(0o755);assert run(d,e).returncode!=0;assert (r/'etc/mt3600be-wan-eee/original.bin').read_text()=='original';assert (r/'etc/mt3600be-wan-eee/disabled').exists();assert not (r/'usr/sbin/mt3600be-wan-eee').exists();assert not (r/'usr/libexec/mt3600be-eee-state').exists();record('写入故障清理本次已登记文件并保留备份，启动保持禁用')
(P/'installer-test-results.txt').write_text('\n'.join('PASS '+n for n in passed)+'\n')
