#!/bin/sh
# MT3600BE online tools v1.2. Fixed releases; no remote shell evaluation.
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin; export PATH
unset ENV BASH_ENV LD_PRELOAD LD_LIBRARY_PATH CURL_HOME
ROOT=/root/mt3600be-tools
LOCK=/var/lock/mt3600be-tools-online.lock
REPO=https://github.com/szdosar/mt3600be-tools/releases/download
WORK=''; STAGE=''; child=''; interrupted=0
fail() { echo "停止：$*" >&2; exit 1; }
cleanup() {
 [ -z "$STAGE" ] || rm -f -- "$STAGE"
 [ -z "$WORK" ] || rm -rf -- "$WORK"
}
signal_stop() { interrupted=1; [ -n "$child" ] || exit 130; }
trap cleanup EXIT
trap signal_stop INT TERM
trap '' HUP
usage() {
 echo 'MT3600BE 工具：安装、查询、回滚；不刷机、不自动重启。'
 echo '用法：sh install.sh [eee-official|passwall2] [install|status|rollback|download|check]'
 echo 'EEE 另支持 enable 和 archive-incomplete。更改操作必须手动输入 YES。'
}
[ "$#" -le 2 ] || { usage; exit 2; }
case "${1:-}" in --help|help) usage; exit 0;; esac
[ "$(id -u)" = 0 ] || fail '请在路由器 SSH 内以 root 执行。'
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null)" = glinet,gl-mt3600be ] || fail '仅支持 GL-MT3600BE；未执行。'
for cmd in flock sha256sum mktemp ln; do command -v "$cmd" >/dev/null 2>&1 || fail "缺少 $cmd；未安装任何软件。"; done
# Use the firmware's fs API when its BusyBox lacks the stat applet.
# Backend failures are fatal: never replace a failed check with guessed metadata.
if command -v stat >/dev/null 2>&1; then META_BACKEND=stat
elif command -v ucode >/dev/null 2>&1; then META_BACKEND=ucode
else fail '缺少 stat 和 ucode，无法安全检查文件；未安装任何软件。'
fi
read_meta() {
 if [ "$META_BACKEND" = stat ]; then
  case "$1" in
   mode) stat -c '%u:%g:%a' "$2";;
   size) stat -c '%s' "$2";;
   identity) stat -c '%d:%i' "$2";;
   identity-follow) stat -Lc '%d:%i' "$2";;
   *) return 2;;
  esac
 else
  ucode -e '
import { stat, lstat } from "fs";
let op = ARGV[0], path = ARGV[1];
if (length(ARGV) != 2) exit(2);
let s = (op == "identity-follow") ? stat(path) : lstat(path);
if (!s) exit(1);
if (op == "mode") print(sprintf("%d:%d:%o\n", s.uid, s.gid, s.mode & 4095));
else if (op == "size") print(sprintf("%d\n", s.size));
else if (op == "identity" || op == "identity-follow")
 print(sprintf("%d,%d:%d\n", s.dev.major, s.dev.minor, s.inode));
else exit(2);
' "$1" "$2"
 fi
}
meta() {
 metadata=$(read_meta "$@") || return 1
 [ -n "$metadata" ] || return 1
 printf '%s\n' "$metadata"
}
# Check the selected API before creating a lock/cache, including the follow mode.
meta mode / >/dev/null && meta size / >/dev/null &&
meta identity / >/dev/null && meta identity-follow / >/dev/null || fail '文件元数据读取失败；未安装任何软件。'
TOOL=${1:-}; ACTION=${2:-}
if [ -z "$TOOL" ]; then
 usage
 printf '\n1 原厂 WAN EEE v1.2-r3（4.9.1-op25 / 6.12.94）\n2 原厂 Passwall2 native-r4.2（先安装 LuCI）\n0 退出\n请选择：'
 IFS= read -r answer || exit 0
 case "$answer" in 1) TOOL=eee-official;; 2) TOOL=passwall2;; 0|'') exit 0;; *) fail '无效选择';; esac
fi
case "$TOOL" in
 eee-official)
  TAG=eee-v1.2-r3; ASSET=mt3600be-eee-tool-v1.2-r3.run
  SHA=baaeaafb216f845270bb477605ffa3889c166758e953454dfabee3403738efbb; SIZE=46000
  [ "$(uname -r)" = 6.12.94 ] && [ "$(cat /etc/glversion 2>/dev/null)" = 4.9.1-op25 ] || fail '原厂 EEE 版本不匹配。';;
 passwall2)
  TAG=passwall2-native-r4.2; ASSET=passwall2-high-native-r4.2.run
  SHA=628edf81254ae180c5a0cb168db9bc31341a2a6cbbf63ee58e5be86ab9b472ad; SIZE=41489241
  [ "$(uname -r)" = 6.12.94 ] && grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail '原厂 Passwall2 版本不匹配。';;
 *) fail '未知工具';;
esac
# Both public tools target this exact tested official op25 beta build.
[ "$(cat /etc/glversion 2>/dev/null)" = 4.9.1-op25 ] && [ "$(uname -r)" = 6.12.94 ] || fail '仅支持已测试的官方 4.9.1-op25 测试版。'
for expected in "DISTRIB_RELEASE='25.12.5'" "DISTRIB_REVISION='r33051-f5dae5ece4'" "DISTRIB_TARGET='mediatek/filogic'" "DISTRIB_ARCH='aarch64_cortex-a53'"; do
 grep -Fxq "$expected" /etc/openwrt_release || fail 'OpenWrt 测试版构建或架构不匹配；其他官方固件不能直接使用。'
done
if [ -z "$ACTION" ]; then
 printf '\n1 安装\n2 查询状态\n3 回滚\n4 仅下载保留\n5 校验工具\n0 退出\n请选择：'
 IFS= read -r answer || exit 0
 case "$answer" in 1) ACTION=install;; 2) ACTION=status;; 3) ACTION=rollback;; 4) ACTION=download;; 5) ACTION=check;; 0|'') exit 0;; *) fail '无效选择';; esac
fi
case "$ACTION" in install|status|rollback|download|check) ;; enable|archive-incomplete) [ "$TOOL" != passwall2 ] || fail '该操作仅适用于 EEE';; *) fail '未知操作';; esac
# Stable lock inode is never deleted. Refuse unsafe existing files.
[ ! -L "$LOCK" ] || fail '锁路径是链接。'
if [ ! -e "$LOCK" ]; then (set -C; : > "$LOCK") 2>/dev/null || :; fi
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ "$(meta mode "$LOCK")" = 0:0:600 ] || fail '锁归属或权限异常。'
exec 8<>"$LOCK"
flock -n 8 || { echo '另一个在线工具操作正在执行；未接管，请稍后重试。' >&2; exit 75; }
fd_identity=$(meta identity-follow /proc/$$/fd/8) || fail '无法读取已打开锁身份。'
path_identity=$(meta identity "$LOCK") || fail '无法读取锁路径身份。'
[ -n "$fd_identity" ] && [ "$fd_identity" = "$path_identity" ] || fail '锁文件被替换。'
case "$ACTION" in install|rollback|enable|archive-incomplete)
 echo "工具：$TOOL；固定版本：$TAG；操作：$ACTION"
 if [ "$TOOL" = passwall2 ]; then
  echo '保留原生安装行为：可能更新 DHCP localuse、防火墙 include、uhttpd 和 ucitrack；旧主开关开启时可能启动代理。'
  echo '回滚仅删除本次新增包并按事务恢复接入；配置冲突会停止。安装前请备份，并先从原厂页面安装 LuCI。'
 else
  echo '仅处理 WAN EEE，可能短暂重新协商链路；建议通过 LAN 管理。回滚恢复已保存的原始 EEE。'
  [ "$ACTION" != archive-incomplete ] || echo '归档保留旧快照；以后重新安装会采集新的回滚基线。'
 fi
 printf '输入 YES 确认，其他输入取消：'; IFS= read -r answer || exit 0
 [ "$answer" = YES ] || { echo '已取消，未执行。'; exit 0; };;
esac
safe_dir() { [ -d "$1" ] && [ ! -L "$1" ] && [ "$(meta mode "$1")" = 0:0:700 ] || fail "缓存目录异常：$1"; }
make_dir() { if [ ! -e "$1" ] && [ ! -L "$1" ]; then mkdir -m 700 "$1" || fail '创建缓存目录失败'; fi; safe_dir "$1"; }
verify() {
 [ -f "$1" ] && [ ! -L "$1" ] && [ "$(meta mode "$1")" = 0:0:600 ] || fail '下载或缓存文件类型、归属、权限异常。'
 [ "$(meta size "$1")" = "$SIZE" ] || fail '文件大小不符；未执行。'
 digest=$(sha256sum "$1") || fail '读取摘要失败。'
 [ "${digest%% *}" = "$SHA" ] || fail 'SHA-256 不符；未执行，不覆盖旧文件。'
}
# Refuse linked parents; never chmod or delete an old cache to force installation.
[ -d /root ] && [ ! -L /root ] || fail '/root 类型异常。'
for d in "$ROOT" "$ROOT/$TOOL" "$ROOT/$TOOL/$TAG"; do
 if [ -e "$d" ] || [ -L "$d" ]; then safe_dir "$d"; fi
done
WORK=$(mktemp -d /tmp/mt3600be-online.XXXXXXXX) || fail '无法创建独立临时目录。'
CACHE=$ROOT/$TOOL/$TAG/$ASSET
if [ -e "$CACHE" ] || [ -L "$CACHE" ]; then
 verify "$CACHE"
 cp "$CACHE" "$WORK/tool.run" || fail '缓存复制失败。'
 echo "使用已校验的固定版本缓存：$CACHE"
else
 command -v curl >/dev/null 2>&1 || fail '缺少 curl，请先通过原厂软件包管理安装 curl，或手动下载离线包。'
 echo "下载 $TAG …"
 curl -q --fail --location --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 300 --retry 2 --retry-delay 1 --max-filesize "$SIZE" --output "$WORK/tool.run" "$REPO/$TAG/$ASSET" || fail '下载失败；未执行旧脚本，可重试。'
 chmod 600 "$WORK/tool.run"
fi
verify "$WORK/tool.run"
# Publish a copy only after validation; no overwrite. Execution uses WORK, not CACHE.
if [ ! -e "$CACHE" ] && [ ! -L "$CACHE" ]; then
 make_dir "$ROOT"; make_dir "$ROOT/$TOOL"; make_dir "$ROOT/$TOOL/$TAG"
 # /tmp may be a separate filesystem: stage on the cache filesystem and link atomically.
 STAGE=$(mktemp "$ROOT/$TOOL/$TAG/.download.XXXXXXXX") || fail '缓存暂存失败。'
 if ! cp "$WORK/tool.run" "$STAGE"; then rm -f -- "$STAGE"; fail '缓存复制失败'; fi
 chmod 600 "$STAGE"
 verify "$STAGE"
 if ! ln "$STAGE" "$CACHE"; then rm -f -- "$STAGE"; fail '缓存目标已出现，未覆盖；请重新查询'; fi
 rm -f -- "$STAGE"; STAGE=''
fi
verify "$CACHE"
echo "已保留离线包：$CACHE"
[ "$ACTION" != download ] || { echo '仅下载完成，尚未安装。'; exit 0; }
verify "$WORK/tool.run"
case "$TOOL:$ACTION" in
 passwall2:install|passwall2:rollback) set -- "$ACTION" --apply;;
 passwall2:check) set -- --check;;
 passwall2:status) set -- status;;
 *:install|*:rollback|*:enable|*:archive-incomplete) set -- "$ACTION" --yes;;
 *:check) set -- check;;
 *:status) set -- status;;
esac
# Do not hand the wrapper lock FD to services launched by the native installer.
sh "$WORK/tool.run" "$@" 8>&- & child=$!
rc=0
while :; do
 wait "$child" && rc=0 || rc=$?
 kill -0 "$child" 2>/dev/null || break
done
child=''
[ "$rc" = 0 ] || { echo "工具返回 $rc；保留事务，不删除备份或强装。可查询后重试同版。" >&2; exit "$rc"; }
[ "$interrupted" = 0 ] || echo '收到中断请求后已等待工具结束，未删除事务。'
echo '操作结束；安装成功不代表节点或网络已通过实际连通测试。'
