#!/bin/sh
set -eu
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
STATE=/etc/mt3600be-wan-eee
exec 9>/var/lock/mt3600be-wan-eee.lock
flock -n 9 || exit 75
[ "$(cat /tmp/sysinfo/board_name)" = glinet,gl-mt3600be ]
[ "$(uname -r)" = 6.12.94 ]
[ "$(cat /etc/glversion)" = 4.9.1-op25 ]
grep -q '^DRIVER=RTL8221B-VB-CG 2.5Gbps PHY (C45)$' /sys/class/net/eth0/phydev/uevent
(cd "$DIR"; sha256sum -c SHA256SUMS)
if [ -e "$STATE" ] || [ -L "$STATE" ]; then
 echo 'Existing state found; refusing to replace it. Use status/enable/rollback.' >&2
 exit 1
fi
for target in /usr/libexec/mt3600be-eee-state /usr/sbin/mt3600be-wan-eee /etc/init.d/mt3600be-wan-eee /etc/hotplug.d/iface/98-mt3600be-wan-eee /etc/rc.d/S99mt3600be-wan-eee /etc/rc.d/K10mt3600be-wan-eee; do
 [ ! -e "$target" ] && [ ! -L "$target" ] || { echo "检测到残留补丁文件或启动链接：$target；可能由恢复配置带回，拒绝覆盖。请先执行 status。" >&2; exit 1; }
done
if [ "$#" -gt 1 ]; then exit 2; fi
# Assess BEFORE creating a new transaction. Saving again still validates below,
# and disable rechecks current state to close a normal link-state change window.
# This release deliberately does not treat timer zero as restore-compatible.
rc=0; "$DIR/eee-state" assess || rc=$?
if [ "$rc" != 0 ]; then
 echo "安装前只读检查未通过（状态码 $rc）；未创建新事务、未修改 EEE。timer=0 原样恢复尚未验证；请保留旧记录，接通 WAN 后重新检查，不要强改计时器。" >&2
 exit "$rc"
fi
umask 077
early_failure() {
 rc=$?
 trap - EXIT HUP INT TERM
 echo "首次安装未完成（状态码 $rc）；如有原始快照及事务目录均已保留，未启用补丁。请先检查状态，再使用归档不完整事务功能；新快照将成为新的回滚基线。" >&2
 exit "$rc"
}
trap early_failure EXIT
trap 'exit 130' HUP INT TERM
mkdir "$STATE"
# In this acceptance run the supplied baseline was captured before disabling EEE.
if [ "$#" -eq 1 ]; then
 rc=0; "$DIR/eee-state" import "$1" "$STATE/original.bin" || rc=$?
 [ "$rc" = 0 ] || { echo "导入快照失败（状态码 $rc）；未修改 EEE，原记录保留。" >&2; exit "$rc"; }
else
 rc=0; "$DIR/eee-state" save "$STATE/original.bin" || rc=$?
 [ "$rc" = 0 ] || { echo "采集原始状态失败（状态码 $rc）；请检查设备访问或 I/O。" >&2; exit "$rc"; }
fi
rc=0; "$DIR/eee-state" validate "$STATE/original.bin" || rc=$?
if [ "$rc" != 0 ]; then
 case "$rc" in
  4) echo '原始 EEE 状态超出已验证范围（包括 timer 非 1000）；安全拒绝，不能强装。' >&2;;
  3) echo '原始状态文件格式、权限或长度无效；安全拒绝。' >&2;;
  *) echo "原始状态校验或 I/O 失败（状态码 $rc）；安全拒绝。" >&2;;
 esac
 exit "$rc"
fi
(cd "$STATE"; sha256sum original.bin > original.sha256)
: > "$STATE/disabled"
# Roll back only files this invocation successfully created if installation fails.
created=''
pending_tmp=''
committed=0
cleanup_install() {
 rc=$?
 trap - EXIT HUP INT TERM
 if [ "$committed" = 0 ]; then
  [ -z "$pending_tmp" ] || rm -f "$pending_tmp"
  for dest in $created; do rm -f "$dest"; done
  rm -f "$STATE/installed" "$STATE/files.sha256"
  # Retain the original snapshot and disabled marker for manual recovery.
  echo 'Installation incomplete; original EEE snapshot retained, startup not enabled.' >&2
 fi
 exit "$rc"
}
trap cleanup_install EXIT
trap 'exit 130' HUP INT TERM
put() {
 src=$1
 dest=$2
 tmp=$(mktemp "$dest.new.XXXXXX")
 pending_tmp=$tmp
 cat "$src" > "$tmp"
 chmod 755 "$tmp"
 ln "$tmp" "$dest" || { rm -f "$tmp"; return 1; }
 created="$created $dest"
 rm "$tmp"
 pending_tmp=''
}
mkdir -p /usr/libexec
put "$DIR/eee-state" /usr/libexec/mt3600be-eee-state
put "$DIR/mt3600be-wan-eee" /usr/sbin/mt3600be-wan-eee
put "$DIR/init" /etc/init.d/mt3600be-wan-eee
put "$DIR/hotplug" /etc/hotplug.d/iface/98-mt3600be-wan-eee
sha256sum /usr/libexec/mt3600be-eee-state /usr/sbin/mt3600be-wan-eee /etc/init.d/mt3600be-wan-eee /etc/hotplug.d/iface/98-mt3600be-wan-eee > "$STATE/files.sha256"
: > "$STATE/installed"
committed=1
flock -u 9
/usr/sbin/mt3600be-wan-eee enable
