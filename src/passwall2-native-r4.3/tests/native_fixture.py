#!/usr/bin/env python3
"""Real signed ARM APKs + native hooks and ARM libuci; services are fixtures.
Host APK executes original scripts in bwrap without networking. No router/VM.
"""
from pathlib import Path
import subprocess,shutil,json,tempfile,hashlib,os,time,signal
S=Path(__file__).resolve().parents[1]
W=Path('/home/dosar/Projects/openclaw/work')
PUBLIC=W/'mt3600be-image-v11-luci-repair-r3-build01-20261025/base-root'
PAYLOAD=W/'mt3600be-run-native-high-r4.3-20261031/payload01'
BOOT=W/'mt3600be-v11-luci-repair-r4-candidate03/kits/luci-bootstrap'
A='/home/dosar/immortalwrt/staging_dir/host/bin/apk'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd,**kw):
 p=subprocess.run(list(map(str,cmd)),capture_output=True,text=True,**kw)
 if p.returncode:raise RuntimeError(p.stdout+p.stderr)
 return p.stdout
class Fixture:
 def __init__(self,path=None):
  self.tmp=Path(path or tempfile.mkdtemp(prefix='pw-native-test-'));self.root=self.tmp/'root'
  shutil.copytree(PUBLIC,self.root,symlinks=True)
  # Official LuCI bootstrap, no lifecycle here: prepare the prerequisite fixture.
  run([A,'--root',self.root,'--arch','aarch64_cortex-a53','--no-network','--repositories-file','/dev/null','--keys-dir',BOOT/'keys','add','--no-scripts','--no-commit-hooks','--usermode',*[BOOT/r['file'] for r in json.loads((BOOT/'manifest.json').read_text())]])
  self.kit=self.root/'kit';shutil.copytree(PAYLOAD,self.kit)
  for n in ['controller.sh','native-config.sh','components.txt']:shutil.copyfile(S/n,self.kit/n)
  # Host shell/tools; actual target UCI and libuci run under user-mode QEMU.
  for d in ['overlay','tmp/.uci','tmp/sysinfo','root','proc','dev','lib64','lib/x86_64-linux-gnu','fixture','usr/sbin','var/lock']:(self.root/d).mkdir(parents=True,exist_ok=True)
  for d in ['var','var/lock']:
   pass
  shutil.copyfile('/usr/bin/busybox',self.root/'bin/busybox');(self.root/'bin/busybox').chmod(0o755)
  for n in ['awk','sort','sha256sum','find','dirname','id','mktemp','head','tail','cmp','grep','sed','cp','rm','ln','readlink','cat','mkdir','chmod','sleep','sync','wc','cut','tr','stat','touch','mv','tar','base64','df','du']:
   p=self.root/'bin'/n;p.unlink(missing_ok=True);p.symlink_to('busybox')
  p=self.root/'bin/sh';p.unlink(missing_ok=True);p.symlink_to('busybox')
  # Avoid a qemu binary being mistaken for a running proxy by /proc checks.
  shutil.copyfile('/usr/bin/qemu-aarch64-static',self.root/'bin/qemu');(self.root/'bin/qemu').chmod(0o755)
  for f in ['/lib/x86_64-linux-gnu/libc.so.6','/lib64/ld-linux-x86-64.so.2']:
   shutil.copyfile(f,self.root/f.lstrip('/'));(self.root/f.lstrip('/')).chmod(0o755)
  (self.root/'usr/bin/flock').unlink(missing_ok=True);shutil.copyfile('/usr/bin/flock',self.root/'usr/bin/flock');(self.root/'usr/bin/flock').chmod(0o755)
  shutil.copyfile(A,self.root/'usr/bin/apk-real');(self.root/'usr/bin/apk-real').chmod(0o755)
  self.write('usr/bin/apk',r'''#!/bin/sh
set -eu
case " $* " in *"--simulate"*) /usr/bin/apk-real "$@";exit $?;;esac
case " $* " in *" add "*) op=add;;*" del "*) op=del;;*)exec /usr/bin/apk-real "$@";;esac
if [ -e /fixture/before-$op ];then touch /fixture/barrier;while :;do sleep .05;done;fi
if [ -e /fixture/fail-$op ];then exit 93;fi
if [ -e /fixture/after-native-unlink ];then
 LD_PRELOAD="${LD_PRELOAD:+$LD_PRELOAD:}/fixture/apk-fault.so" /usr/bin/apk-real "$@" || exit $?
else /usr/bin/apk-real "$@" || exit $?;fi
if [ -e /fixture/after-$op ];then touch /fixture/barrier;while :;do sleep .05;done;fi
''',0o755)
  run(['cc','-O2','-shared','-fPIC',S/'tests/apk_fault.c','-ldl','-o',self.root/'fixture/apk-fault.so'])
  # Invoke the exact firmware UCI executable through the emulator.
  p=self.root/'sbin/uci';p.rename(self.root/'sbin/uci.arm')
  self.write('sbin/uci',r'''#!/bin/sh
[ ! -e /fixture/fail-uci ] || exit 1
preload=
[ -z "${MT3600BE_NATIVE_DELTA:-}" ] || preload=/kit/native-uci.arm.so
if [ -e /fixture/after-native-firewall ];then preload="${preload:+$preload:}/fixture/uci-fault.so";fi
exec /bin/qemu -L / -E LD_PRELOAD="$preload" /sbin/uci.arm "$@"
''',0o755)
  cc='/home/dosar/immortalwrt/staging_dir/toolchain-aarch64_cortex-a53_gcc-14.3.0_musl/bin/aarch64-openwrt-linux-musl-gcc'
  run([cc,'-O2','-shared','-fPIC',S/'tests/uci_fault.c','-ldl','-o',self.root/'fixture/uci-fault.so'])
  p=self.kit/'uci-plan';p.rename(self.kit/'uci-plan.arm')
  self.write('kit/uci-plan','#!/bin/sh\nexec /bin/qemu -L / /kit/uci-plan.arm "$@"\n',0o755)
  run(['cc','-O2','-Wall','-Werror',S/'fs-safe.c','-o',self.kit/'fs-safe'])
  shutil.copyfile(self.kit/'native-uci.so',self.kit/'native-uci.arm.so')
  run(['cc','-O2','-shared','-fPIC','-I/home/dosar/lede/staging_dir/target-aarch64_cortex-a53_musl/usr/include',S/'native-uci.c','-ldl','-o',self.kit/'native-uci.so'])
  run(['cc','-O2','-shared','-fPIC',S/'apk-db-guard.c','-ldl','-o',self.kit/'apk-db-guard.so'])
  self.write('bin/uname','#!/bin/sh\necho 6.12.94\n',0o755,unlink=True)
  self.write('tmp/sysinfo/board_name','glinet,gl-mt3600be\n')
  self.write('etc/config/dhcp',"config dnsmasq\n option localuse '0'\n option domain 'fixture.lan'\n",0o640)
  self.write('etc/config/uhttpd',"config uhttpd 'main'\n option max_requests '3'\n option inited '1'\n option enabled '1'\n",0o640)
  self.write('etc/config/firewall',"config defaults\n option input 'ACCEPT'\nconfig zone\n option name 'lan'\n",0o600)
  self.write('etc/config/ucitrack',"config network\n option init 'network'\n",0o600)
  self.write('etc/config/luci',"config core 'main'\n option lang 'auto'\nconfig internal 'languages'\n",0o644)
  self.write('etc/config/network',"config interface 'lan'\n option proto 'static'\n",0o640)
  self.write('etc/config/wireless',"config wifi-device 'fixture'\n option disabled '1'\n",0o600)
  self.write('etc/config/vpn',"config fixture\n option enabled '0'\n",0o600)
  # Lifecycle service fixture: records original calls and implements only links.
  # Actual procd / wireless / netfilter operations are deliberately not emulated.
  self.write('etc/rc.common',r'''#!/bin/sh
initscript=$1;action=$2
. "$initscript"
echo "$initscript $action" >> /fixture/service-calls
case "$action" in
 enable) [ -z "${START:-}" ] || ln -sf ../init.d/$(basename "$initscript") /etc/rc.d/S${START}$(basename "$initscript");[ -z "${STOP:-}" ] || ln -sf ../init.d/$(basename "$initscript") /etc/rc.d/K${STOP}$(basename "$initscript");;
 disable) rm -f /etc/rc.d/*$(basename "$initscript");;
 *) :;;esac
exit 0
''',0o755)
  self.write('etc/init.d/rpcd','#!/bin/sh\nexit 0\n',0o755)
  self.write('etc/init.d/ucitrack','#!/bin/sh\n[ ! -e /fixture/fail-trigger ]\n',0o755)
  self.write('sbin/kmodloader','#!/bin/sh\nexit 0\n',0o755)
  self.write('bin/killall','#!/bin/sh\nexit 0\n',0o755,unlink=True)
  self.write('kit/target-apk.sha256',sha(self.root/'usr/bin/apk')+'\n')
  self.write('kit/target-runtime.tsv',''.join(sha(self.root/n.lstrip('/'))+'  '+n+'\n' for n in [l.split()[1] for l in (self.kit/'target-runtime.tsv').read_text().splitlines()]))
  self.write('kit/release.ready','pw261020-xray261021-native-v4\n');self.freeze()
  self.before={c:(self.root/'etc/config'/c).read_bytes() for c in ['dhcp','uhttpd','firewall','ucitrack','luci','network','wireless','vpn']}
  self.before_modes={c:(self.root/'etc/config'/c).stat().st_mode&0o777 for c in self.before}
 def write(self,p,s,mode=0o644,unlink=False):
  p=self.root/p;p.parent.mkdir(parents=True,exist_ok=True)
  if unlink:p.unlink(missing_ok=True)
  p.write_text(s);p.chmod(mode)
 def freeze(self):
  (self.kit/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(self.kit).as_posix()+'\n' for p in sorted(self.kit.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
 def prefix(self):return ['bwrap','--unshare-all','--uid','0','--gid','0','--die-with-parent','--bind',str(self.root),'/','--proc','/proc','--dev','/dev','--clearenv','--setenv','PATH','/usr/sbin:/usr/bin:/sbin:/bin','--chdir','/']
 def cmd(self,*args,ok=True):
  p=subprocess.run(self.prefix()+list(args),capture_output=True,text=True,timeout=150)
  if ok and p.returncode:raise AssertionError(p.stdout+p.stderr)
  if ok is False and not p.returncode:raise AssertionError('unexpected success '+p.stdout)
  return p
 def action(self,a='install',ok=True):return self.cmd('/bin/sh','/kit/controller.sh',a,*(['--apply'] if a in ['install','rollback'] else []),ok=ok)
 @property
 def state(self):return self.root/'root/mt3600be-passwall2-run-v4/transaction'
 def flag(self,n):(self.root/'fixture'/n).touch()
 def clear(self,n):(self.root/'fixture'/n).unlink(missing_ok=True)
 def start(self,a='install'):
  return subprocess.Popen(self.prefix()+['/bin/sh','/kit/controller.sh',a,'--apply'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
 def barrier(self,p):
  for _ in range(2400):
   if (self.root/'fixture/barrier').exists():return
   if p.poll() is not None:raise AssertionError(p.communicate())
   time.sleep(.025)
  raise AssertionError('barrier timeout')
 def kill(self,p):
  os.killpg(p.pid,signal.SIGKILL);p.communicate(timeout=10)
  self.clear('barrier')
 def close(self):shutil.rmtree(self.tmp)
if __name__=='__main__':
 f=Fixture();print('fixture',f.tmp,flush=True)
 try:
  print(f.action().stdout,flush=True);print(f.action().stdout,flush=True);print(f.action('rollback').stdout,flush=True)
  for c,b in f.before.items():assert (f.root/'etc/config'/c).read_bytes()==b,c
  print('PASS real signed packages native hooks private UCI and rollback')
 except Exception:
  print('retained fixture',f.tmp,flush=True);raise
 else:f.close()
