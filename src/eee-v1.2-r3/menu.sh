#!/bin/sh
set -eu
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
STATE=/etc/mt3600be-wan-eee
CLI=/usr/sbin/mt3600be-wan-eee
usage() {
 cat <<'EOF'
MT3600BE 有线稳定工具 v1.2（离线候选）
仅适用于原厂 4.9.1-op25 / OpenWrt 25.12.5 / Linux 6.12.94。
无参数：中文菜单；status：只读查看；install：首次安装；rollback：回滚；enable：重新启用。
check：只验证离线包；archive-incomplete：归档不完整事务；help：使用帮助。
更改操作会再次确认；脚本自动调用时可显式附加 --yes。
不刷机、不重启、不更改 DNS、VPN、无线或插件配置。
安装中断留下不完整事务时安全拒绝覆盖，需要人工检查，不能删除原始备份后强装。
归档保留旧快照；再次安装使用当时新采集状态作为回滚基线，不能冒充旧快照。
EOF
}
fail() { echo "$*" >&2; exit 1; }
platform() {
 [ "$(id -u)" = 0 ] || fail '请在路由器上用 root 运行。'
 [ "$(cat /tmp/sysinfo/board_name)" = glinet,gl-mt3600be ] &&
 [ "$(uname -r)" = 6.12.94 ] &&
 [ "$(cat /etc/glversion)" = 4.9.1-op25 ] &&
 grep -q '^DRIVER=RTL8221B-VB-CG 2.5Gbps PHY (C45)$' /sys/class/net/eth0/phydev/uevent || fail '型号、固件或 PHY 不匹配，未执行。'
}
verify_installed() {
 [ -d "$STATE" ] && [ ! -L "$STATE" ] && [ -f "$STATE/installed" ] || fail '没有完整安装记录；不覆盖旧事务，请人工检查。'
 current=1; legacy=1; legacy2=1
 for pair in 'eee-state:/usr/libexec/mt3600be-eee-state' 'mt3600be-wan-eee:/usr/sbin/mt3600be-wan-eee' 'init:/etc/init.d/mt3600be-wan-eee' 'hotplug:/etc/hotplug.d/iface/98-mt3600be-wan-eee'; do
  src=${pair%%:*}; dest=${pair#*:}
  [ -f "$dest" ] && [ ! -L "$dest" ] || fail '已安装文件缺失或类型异常，安全拒绝。'
  cmp -s "$DIR/patch/$src" "$dest" || current=0
  case "$src" in
   eee-state) expected=4ef35d27bddc4755898e3461fca572ee28302eb050483919567fc29839bfd12f;;
   mt3600be-wan-eee) expected=a7a802584d6b74bd88802a809c5756e28fb5f8fc3c338358b3fb165ea246e36b;;
   init) expected=197997e67408205b74aab003105d250839c5f7a304fd6ec8d77a7f429a30d2bb;;
   hotplug) expected=ff0f064ff7efc5ec9d2ecc36d8fcf935a71a1e449859c445e52016499066b0d4;;
  esac
  actual=$(sha256sum "$dest") || fail '无法校验已安装文件。'
  [ "${actual%% *}" = "$expected" ] || legacy=0
  case "$src" in
   eee-state) expected=d54c179fa995a16bef220a2571e2c3a106a31f51ea5044d85aab34669a244378;;
  esac
  [ "${actual%% *}" = "$expected" ] || legacy2=0
 done
 [ "$current" = 1 ] || [ "$legacy" = 1 ] || [ "$legacy2" = 1 ] || fail '已安装版本不受支持或文件损坏，安全拒绝。'
 (cd /; sha256sum -c "$STATE/files.sha256" >/dev/null) || fail '安装文件校验失败。'
 (cd "$STATE"; sha256sum -c original.sha256 >/dev/null) || fail '原始备份校验失败。'
 "$DIR/patch/eee-state" validate "$STATE/original.bin" >/dev/null || fail '原始备份格式或权限异常。'
}
legacy_rollback() {
 exec 9>/var/lock/mt3600be-wan-eee.lock
 flock -n 9 || return 75
 verify_installed
 [ -f "$STATE/original.sha256" ] && [ ! -L "$STATE/original.sha256" ] || return 1
 IFS=' ' read -r hash name extra < "$STATE/original.sha256" || return 1
 [ "${#hash}" = 64 ] && [ "$name" = original.bin ] && [ -z "$extra" ] || return 1
 case "$hash" in *[!0-9a-f]*) return 1;; esac
 : > "$STATE/disabled" || return 1
 /etc/init.d/mt3600be-wan-eee disable || return 1
 /etc/init.d/mt3600be-wan-eee stop || return 1
 "$DIR/patch/eee-state" restore-checked "$STATE/original.bin" "$hash" || return $?
 : > "$STATE/rolled-back" || return 1
 flock -u 9 || return 1
}
status() {
 if [ ! -e "$STATE" ] && [ ! -L "$STATE" ]; then
  echo '尚未安装；未修改任何设置。'; return 0
 fi
 verify_installed
 "$CLI" status
 if /etc/init.d/mt3600be-wan-eee enabled; then echo '开机启动：已启用'; else echo '开机启动：已关闭'; fi
 if /etc/init.d/mt3600be-wan-eee running; then echo '后台服务：运行中'; else echo '后台服务：未运行'; fi
 echo '正常启用应显示 mode=enabled、eee_active=0、tx_lpi_enabled=0、advertised=0x0、phy7_mmd7_003c=0x0000。'
}
confirm() {
 [ "$YES" = 1 ] && return 0
 printf '输入 YES 确认，其他输入取消：'
 IFS= read -r answer || return 1
 [ "$answer" = YES ]
}
[ "$#" -le 2 ] || { usage; exit 2; }
ACTION=${1:-menu}; YES=0
if [ "$#" = 2 ]; then [ "$2" = --yes ] || { usage; exit 2; }; YES=1; fi
case "$ACTION" in help|--help) usage; exit 0;; esac
(cd "$DIR/patch"; sha256sum -c SHA256SUMS >/dev/null) || fail '离线包校验失败。'
[ "$ACTION" != check ] || { echo '离线包校验通过；未安装或更改设置。'; exit 0; }
if [ "$ACTION" = menu ]; then
 usage
 printf '\n1 查看状态（只读）\n2 安装补丁\n3 回滚至原始 EEE\n4 重新启用补丁\n5 归档不完整事务\n0 退出\n请选择：'
 IFS= read -r answer || exit 0
 case "$answer" in 1) ACTION=status;; 2) ACTION=install;; 3) ACTION=rollback;; 4) ACTION=enable;; 5) ACTION=archive-incomplete;; 0|'') exit 0;; *) echo '无效选择，未执行。'; exit 2;; esac
fi
case "$ACTION" in status|install|rollback|enable|archive-incomplete) platform;; *) usage; exit 2;; esac
case "$ACTION" in
 status) status;;
 install)
  if [ -e "$STATE" ] || [ -L "$STATE" ]; then verify_installed; echo '已安装同版，保留原始备份；未重复安装或重新启用。'; status; exit 0; fi
  echo '将保存安装前 EEE 状态，并安装开机关闭 WAN EEE 的补丁。可能短暂重新协商 WAN；建议从 LAN 管理。'
  confirm || { echo '已取消。'; exit 0; }
  sh "$DIR/patch/install.sh"
  status;;
 archive-incomplete)
  echo '将保留并归档不完整事务；之后重新安装会采集新的回滚基线，不会恢复或替代旧快照。'
  confirm || { echo '已取消。'; exit 0; }
  exec 9>/var/lock/mt3600be-wan-eee.lock
  flock -n 9 || { echo '另一个操作正在执行，请稍后重试。' >&2; exit 75; }
  [ -d "$STATE" ] && [ ! -L "$STATE" ] || fail '不完整事务目录不存在或类型异常，安全拒绝。'
  [ ! -e "$STATE/installed" ] && [ ! -L "$STATE/installed" ] || fail '发现安装记录，不执行归档。'
  for target in /usr/libexec/mt3600be-eee-state /usr/sbin/mt3600be-wan-eee /etc/init.d/mt3600be-wan-eee /etc/hotplug.d/iface/98-mt3600be-wan-eee /etc/rc.d/S99mt3600be-wan-eee /etc/rc.d/K10mt3600be-wan-eee; do
   [ ! -e "$target" ] && [ ! -L "$target" ] || fail '存在补丁文件或启动链接，不能自动归档；请人工检查。'
  done
  umask 077
  archive=$(mktemp -d /etc/mt3600be-wan-eee-incomplete.XXXXXXXX) || fail '无法创建归档目录；旧事务未移动。'
  "$DIR/patch/eee-state" archive "$STATE" "$archive/transaction" || fail "归档未完成，请检查 $archive 和原事务；不要删除快照。"
  echo "已归档至 $archive/transaction；旧快照原样保留。重新安装会采集新的回滚基线。";;
 rollback|enable)
  verify_installed
  if [ "$ACTION" = rollback ]; then echo '将关闭补丁并恢复原始 EEE；原有丢包可能恢复。保留工具和备份。'; else echo '将重新启用开机关闭 EEE 的补丁。'; fi
  confirm || { echo '已取消。'; exit 0; }
  rc=0
  if [ "$ACTION" = rollback ] && [ "$current" != 1 ]; then
   legacy_rollback || rc=$?
  else
   "$CLI" "$ACTION" || rc=$?
  fi
  if [ "$rc" = 75 ]; then echo '另一个操作正在执行，请稍后重试；没有抢占锁。' >&2; exit 75; fi
  [ "$rc" = 0 ] || { echo '操作未完成，请保留原状态，先查询；回滚中断后可再次选择回滚。' >&2; exit "$rc"; }
  status;;
esac
