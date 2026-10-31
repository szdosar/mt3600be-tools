#!/bin/sh
# Native Passwall2 offline installer. Explicit install, status and rollback only.
set -eu
export LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin; export PATH
umask 077
unset MT3600BE_NATIVE_DELTA IPKG_INSTROOT IPKG_NO_SCRIPT PKG_UPGRADE LD_PRELOAD LD_LIBRARY_PATH ENV BASH_ENV
KIT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BASE=/root/mt3600be-passwall2-run-v4
STATE=$BASE/transaction
ACTION=${1:-status}
fail() { echo "停止：$*" >&2; exit 1; }
hash() { sha256sum "$1" | awk '{print $1}'; }
regular() { [ -f "$1" ] && [ ! -L "$1" ] || fail "文件缺失或类型异常：$1"; }
meta() { "$KIT/fs-safe" meta "$1"; }
private_dir() { [ "$(meta "$1")" = 0:0:700:d ] || fail '事务目录权限或类型异常'; }
private_file() { [ "$(meta "$1")" = 0:0:600:f ] || fail '事务记录权限或类型异常'; }
phase() { "$KIT/fs-safe" record "$STATE/phase" "$1" "$WORK"; }
seal() { (cd "$1"; find . -type f ! -name SEAL ! -name phase ! -path "./native/delta/*" ! -path "./native/commits/*" ! -path "./defaults/*" | sort | while IFS= read -r f;do sha256sum "$f";done) > "$1/SEAL"; }
validate_state() {
 private_dir "$STATE"; private_file "$STATE/phase"
 for n in identity versions world protected additions files integration service-links retained-files retained-links predecessor default-templates SEAL; do private_file "$STATE/$n"; done
 find "$STATE" ! -type f ! -type d | grep . >/dev/null && fail '事务中含链接或特殊文件'
 saved=$(cd "$STATE"; find . -type f ! -name SEAL ! -name phase ! -path "./native/delta/*" ! -path "./native/commits/*" ! -path "./defaults/*" | sort | while IFS= read -r f;do sha256sum "$f";done)
 [ "$saved" = "$(cat "$STATE/SEAL")" ] || fail '事务原始记录损坏，拒绝接管'
 [ "$(cat "$STATE/identity")" = "run-native-v4|$ID" ] || fail '其他版本的事务，禁止覆盖'
 retained_validate_record
 templates_validate
 predecessor_match "$STATE/predecessor"
 private_dir "$STATE/native/delta"
 private_dir "$STATE/native/commits"
 private_file "$STATE/native/commit.lock"
 for f in "$STATE/native/delta"/*;do
  [ -e "$f" ] || [ -L "$f" ] || continue
  case "${f##*/}" in dhcp|firewall|uhttpd|ucitrack|luci|passwall2|passwall2_server) ;;*) fail "私有 UCI 暂存记录越界";;esac
  private_file "$f"
 done
 PHASE=$(cat "$STATE/phase")
 case "$PHASE" in prepared|installing|integrating|installed|removing|cleaning|rolled-back) ;; *) fail '事务阶段无效';; esac
}
readonly_status() {
 if [ ! -e "$STATE" ] && [ ! -L "$STATE" ]; then
  echo '状态：尚无专用 run 安装事务。'
  [ -f "$KIT/release.ready" ] || echo '当前仅为脚本准备版；编译产物未确认，不能安装。'
  return
 fi
 regular "$KIT/fs-safe"; regular "$KIT/SHA256SUMS"
 ID=$(hash "$KIT/SHA256SUMS")
 . "$KIT/native-config.sh"
 private_dir "$BASE"; validate_state
 echo "状态：$PHASE；事务原始记录完整。"
 echo '此结果仅表示事务阶段，不代表代理节点连通；查询未获取锁或改写文件。'
}
case "$ACTION:$#" in
 status:0|status:1) readonly_status; exit 0;;
 check:1|install:2|rollback:2) ;;
 *) fail '用法：status | check | install --apply | rollback --apply';;
esac
[ "$ACTION" = check ] || [ "${2:-}" = --apply ] || fail '写操作需要 --apply'
[ "$(id -u)" = 0 ] || fail '需要 root'
# All paths are fixed. No root prefix, backend override, or lock bypass env var.
# Release gate is intentionally absent until the user confirms compilation.
regular "$KIT/release.ready"
[ "$(cat "$KIT/release.ready")" = 'pw261020-xray261021-native-v4' ] || fail '尚未冻结审核后的安装载荷'
regular "$KIT/fs-safe"; regular "$KIT/SHA256SUMS"
# Only canonical relative paths in the manifest; no links/special payload files.
awk 'NF!=2 || length($1)!=64 || $1~/[^0-9a-f]/ || $2!~/^[A-Za-z0-9_.+~\/-]+$/ || $2~/^\// || $2~/(^|\/)\.\.?($|\/)/ || seen[$2]++ {bad=1} END {exit bad || NR==0}' "$KIT/SHA256SUMS" || fail '载荷清单格式错误'
(cd "$KIT"; sha256sum -c SHA256SUMS >/dev/null) || fail '载荷摘要不符'
find "$KIT" ! -type f ! -type d | grep . >/dev/null && fail '载荷含链接或特殊文件'
listed=$(awk '{print $2}' "$KIT/SHA256SUMS" | sort)
actual=$(cd "$KIT"; find . -type f | sed 's|^./||' | grep -v '^SHA256SUMS$' | sort)
[ "$listed" = "$actual" ] || fail '载荷清单不完整'
ID=$(hash "$KIT/SHA256SUMS")
for n in packages.tsv files.tsv services.tsv defaults.tsv components.txt target-apk.sha256 keys repo; do [ -e "$KIT/$n" ] || fail "载荷不完整：$n"; done
# Audit-frozen schemas; never source package metadata as shell code.
awk -F'|' 'NF!=4 || $1!~/^[a-z0-9][a-z0-9+_.-]*$/ || $2!~/^[A-Za-z0-9+_.~-]+$/ || length($3)!=64 || $3~/[^0-9a-f]/ || $4!~/^repo\/[A-Za-z0-9+_.~-]+\.apk$/ || seen[$1]++ {bad=1} END {exit bad || NR==0}' "$KIT/packages.tsv" || fail '包清单格式异常'
while IFS= read -r n; do grep -q "^$n|" "$KIT/packages.tsv" || fail "缺少约定组件：$n"; done < "$KIT/components.txt"
grep -q '^luci-app-passwall2|26.10.20-r2|' "$KIT/packages.tsv" || fail 'Passwall2 版本错误'
grep -Eq '^xray-core\|26\.10\.21-r[0-9]+\|' "$KIT/packages.tsv" || fail 'Xray 版本错误'
[ "$(hash /usr/bin/apk)" = "$(cat "$KIT/target-apk.sha256")" ] || fail 'APK 工具不属于验证过的版本'
awk -F'|' 'NF!=5 || $1!~/^[a-z0-9][a-z0-9+_.-]*$/ || $2!~/^\/[A-Za-z0-9_+.,@\/-]+$/ || $2~/(^|\/)\.\.?($|\/)/ || $3!~/^[0-7][0-7][0-7]$/ || ($4!="f" && $4!="l") || ($4=="f" && (length($5)!=64 || $5~/[^0-9a-f]/)) || seen[$2]++ {bad=1} END {exit bad || NR==0}' "$KIT/files.tsv" || fail '文件清单异常'
while IFS='|' read -r n p m k v; do
 grep -q "^$n|" "$KIT/packages.tsv" || fail '文件归属不在组件清单'
 case "$p" in /etc/apk/*|/lib/apk/db/*|/etc/nginx/*|/etc/AdGuardHome/*|/root/*) fail 'APK 越过约定范围';; esac
done < "$KIT/files.tsv"
. "$KIT/native-config.sh"

# Stable inode locks. Never unlink locks, never accept an env-only held flag.
lock_one() {
 lp=$1; fd=$2
 if [ -e "$lp" ] || [ -L "$lp" ]; then
  lm=$(meta "$lp") || fail '锁文件无法读取'
  case "$fd:$lm" in 9:0:0:600:f|8:0:0:600:f|8:0:0:640:f|8:0:0:644:f) ;;*)fail '锁文件无效';;esac
 fi
 case "$fd" in 8) exec 8>>"$lp";; 9) exec 9>>"$lp";; esac
 [ /proc/self/fd/"$fd" -ef "$lp" ] || fail '锁被替换'
 if err=$(flock -xn "$fd" 2>&1); then
  [ -z "$err" ] || fail '锁工具返回异常'
 else
  rc=$?; [ "$rc" = 1 ] && [ -z "$err" ] || fail '锁工具不可用或异常'
  echo '已有安装或回滚正在执行，请稍后重试。' >&2; exit 75
 fi
}
lock_one /tmp/mt3600be-passwall2-run-v1.lock 9
# Do not adopt firmware-integrated controllers or historical transactions.
for p in /root/mt3600be-passwall2-run-v1 /root/mt3600be-passwall2-run-v2 /root/mt3600be-embedded-v10-state /root/mt3600be-passwall2-v2-state /usr/sbin/mt3600be-offline; do
 [ ! -e "$p" ] && [ ! -L "$p" ] || fail '发现旧套件或固件控制器，请先单独处理，不能混装'
done
if [ ! -e "$BASE" ] && [ ! -L "$BASE" ]; then mkdir -m 700 "$BASE"; fi
private_dir "$BASE"
WORK=$(mktemp -d "$BASE/.attempt.XXXXXX")
trap 'rm -rf -- "$WORK"' EXIT
trap 'exit 130' INT
trap 'exit 143' HUP TERM
versions() {
 regular /lib/apk/db/installed
 awk 'BEGIN{RS="";FS="\n"} {p="";v="";np=0;nv=0;for(i=1;i<=NF;i++){if($i~/^P:/){p=substr($i,3);np++} if($i~/^V:/){v=substr($i,3);nv++}}
 if(np!=1||nv!=1||p!~/^[a-z0-9][a-z0-9+_.-]*$/||v!~/^[A-Za-z0-9+_.~-]+$/||seen[p]++)bad=1;else print p"="v} END{exit bad || NR==0}' /lib/apk/db/installed > "$WORK/versions.raw" || fail '包数据库无法可靠读取'
 sort "$WORK/versions.raw"
}
uci_clean() {
 pending=$(uci changes) || fail 'UCI 查询失败'
 [ -z "$pending" ] || fail '存在未提交配置，请先自行完成保存'
}
identity() {
 sha256sum -c "$KIT/target-runtime.tsv" >/dev/null || fail '原厂 UCI 或生命周期实现不匹配'
 [ "$(cat /tmp/sysinfo/board_name)" = 'glinet,gl-mt3600be' ] || fail '型号不匹配'
 for pair in "DISTRIB_RELEASE='25.12.5'" "DISTRIB_REVISION='r33051-f5dae5ece4'" "DISTRIB_TARGET='mediatek/filogic'" "DISTRIB_ARCH='aarch64_cortex-a53'"; do
  grep -Fxq "$pair" /etc/openwrt_release || fail '固件版本或架构不匹配'
 done
 [ "$(/bin/uname -r)" = 6.12.94 ] || fail '内核版本不匹配'
 versions > "$WORK/live"
 grep -Fxq 'kernel=6.12.94~9469a6c8c449c47e503c05678ea1559d-r1' "$WORK/live" || fail '内核完整 ABI 不匹配'
 uci_clean
 [ "$(uci -q get uhttpd.main.inited)" = 1 ] && [ "$(uci -q get uhttpd.main.enabled)" = 1 ] || fail '请先从原厂入口安装并开启 LuCI'
 [ -f /www/cgi-bin/luci ] || [ -f /usr/share/ucode/luci/uhttpd.uc ] || fail 'LuCI 文件不完整'
 [ -x /etc/init.d/ucitrack ] || fail '缺少原生应用触发服务'
}
inactive() {
 # Conservative: never stop anyone's active proxy to make room for installation.
 for e in /proc/[0-9]*/exe; do
  t=$(readlink "$e" 2>/dev/null || true)
  case "$t" in */xray|*/sing-box|*/sslocal|*/haproxy|*/chinadns-ng|*/passwall2/*|*'/xray (deleted)'|*'/sing-box (deleted)') fail '代理进程仍在运行，请先在插件中正常关闭';; esac
 done
 if [ -e /var/lock/passwall2.lock ] || [ -L /var/lock/passwall2.lock ]; then
  lock_one /var/lock/passwall2.lock 8
  exec 8>&-
 fi
}
fingerprint() {
 fp=$1
 if [ -L "$fp" ]; then printf '%s|%s|%s\n' "$fp" "$(meta "$fp")" "$(readlink "$fp")"
 elif [ -e "$fp" ]; then regular "$fp"; printf '%s|%s|%s\n' "$fp" "$(meta "$fp")" "$(hash "$fp")"
 else printf '%s|absent|-\n' "$fp"; fi
}
protected() {
 for d in /etc/config /etc/nginx /etc/apk/keys; do
  [ -d "$d" ] && [ ! -L "$d" ] || fail '共享目录缺失或被替换'
  find "$d" -type f -o -type l
 done > "$WORK/protected.paths"
 baseline="$STATE/versions";[ -f "$baseline" ] || baseline="${PLAN:-$WORK}/versions"
 if [ -f "$baseline" ];then
  while IFS='|' read -r n p m k v;do
   grep -q "^$n=" "$baseline" || continue
   case "$p" in /etc/uci-defaults/*) continue;;esac
   printf '%s\n' "$p" >> "$WORK/protected.paths"
  done < "$KIT/files.tsv"
 fi
 printf '%s\n' /etc/AdGuardHome/config.yaml /etc/resolv.conf >> "$WORK/protected.paths"
 sort -u "$WORK/protected.paths" > "$WORK/protected.sorted"
 while IFS= read -r p; do
  case "$p" in /etc/config/passwall2|/etc/config/passwall2_server|/etc/config/dhcp|/etc/config/firewall|/etc/config/uhttpd|/etc/config/ucitrack|/etc/config/luci) continue;; esac
  fingerprint "$p"
 done < "$WORK/protected.sorted"
}
safe_parents() {
 sp=$(dirname "$1")
 while [ "$sp" != / ]; do [ ! -L "$sp" ] || fail '目标父目录含链接'; sp=$(dirname "$sp"); done
}
file_matches() {
 # Arguments: path mode type hash-or-link.
 safe_parents "$1"
 got=$(meta "$1" 2>/dev/null) || return 1
 if [ "$got" != "0:0:$2:$3" ];then
  [ "$3" = f ] || return 1
  native_mode=$(awk -F'|' -v p="$1" '$1==p{print $2}' "$KIT/native-file-modes.tsv")
  [ -n "$native_mode" ] && [ "$got" = "0:0:$native_mode:f" ] || return 1
 fi
 if [ "$3" = f ]; then [ "$(hash "$1")" = "$4" ]; else [ "$(readlink "$1")" = "$4" ]; fi
}
check_files() {
 while IFS='|' read -r n p m k v; do
  grep -q "^$n=" "$WORK/live" || continue
  case "$p" in /etc/config/*|/etc/uci-defaults/*) continue;; esac
  baseline="$STATE/versions";[ -f "$baseline" ] || baseline="${PLAN:-$WORK}/versions"
  if [ -f "$baseline" ] && grep -q "^$n=" "$baseline";then
   [ -e "$p" ] || [ -L "$p" ] || fail "已有包文件缺失：$n"
   continue
  fi
  [ "$ACTION" != rollback ] || continue
  file_matches "$p" "$m" "$k" "$v" || fail "包文件缺失或被修改：$n；不强制覆盖"
 done < "$KIT/files.tsv"
}
verify_packages() {
 apk --no-network --keys-dir "$KIT/keys" verify "$KIT/repo/packages.adb" > "$WORK/verify.log" 2>&1 || fail '离线索引验签失败'
 while IFS='|' read -r n v h p; do
  [ "$(hash "$KIT/$p")" = "$h" ] || fail 'APK 摘要错误'
  apk --no-network --keys-dir "$KIT/keys" verify "$KIT/$p" >> "$WORK/verify.log" 2>&1 || fail "APK 验签失败：$n"
 done < "$KIT/packages.tsv"
}
live_subset() {
 sha256sum /lib/apk/db/installed /etc/apk/world > "$WORK/validated-baseline"
 versions > "$WORK/live"
 awk -F= 'FILENAME==ARGV[1]{base[$1]=$0;next} FILENAME==ARGV[2]{add[$1]=$0;next}
 {if($1 in base){if(base[$1]!=$0)bad=1;found[$1]=1}else if(!($1 in add)||add[$1]!=$0)bad=1}
 END{for(n in base)if(!(n in found))bad=1;exit bad}' "$STATE/versions" "$STATE/additions" "$WORK/live" || fail '包集合出现计划外变化'
 # WORLD may gain only this transaction's exact new pins, never drop baseline.
 awk 'FILENAME==ARGV[1]{base[$0]=1;next} FILENAME==ARGV[2]{extra[$0]=1;next}
 {if(seen[$0]++ || (!( $0 in base) && !($0 in extra)))bad=1}
 END{for(n in base)if(!(n in seen))bad=1;exit bad}' "$STATE/world" "$STATE/additions" /etc/apk/world || fail 'world 出现计划外变化'
 native_validate
 retained_validate_live
 if [ "$ACTION" = install ];then
  # An APK interrupted before its database commit can leave orphaned payloads.
  # They may be reused only when still byte-identical to this signed release.
  while IFS='|' read -r n p m k v;do
   grep -q "^$n=" "$STATE/additions" || continue
   [ -e "$p" ] || [ -L "$p" ] || continue
   grep -Fxq "$p" "$STATE/retained-files" && continue
   case "$p" in /etc/uci-defaults/*) ;; /etc/config/passwall2_server) ;;esac
   file_matches "$p" "$m" "$k" "$v" || fail "中断遗留文件已变更：$n；拒绝覆盖"
  done < "$STATE/files"
  if ! grep -Fxq /etc/config/passwall2 "$STATE/retained-files" && { [ -e /etc/config/passwall2 ] || [ -L /etc/config/passwall2 ]; };then
   regular /etc/config/passwall2
   [ -f /usr/share/passwall2/0_default_config ] && cmp -s /etc/config/passwall2 /usr/share/passwall2/0_default_config || fail '尚未完成安装的插件配置已变化，拒绝重跑初始化'
  fi
 fi
 protected > "$WORK/protected"
 cmp -s "$STATE/protected" "$WORK/protected" || fail '原厂共享配置已变化，保留现场，禁止覆盖'
 check_files
 sha256sum -c "$WORK/validated-baseline" >/dev/null || fail '检查期间包数据库变化，请重试'
}
apk_command() {
 apk --no-network --keys-dir "$KIT/keys" --repositories-file /dev/null -X "$KIT/repo/packages.adb" "$@"
}
execute_apk() {
 # Race guard runs inside apk's native lock. A fresh receipt per invocation.
 g=$(mktemp -d "$BASE/.apk-attempt.XXXXXX")
 cp "$WORK/validated-baseline" "$g/baseline"
 # Guard includes the validated data snapshots, but never logs their contents.
 predecessor_match "$STATE/predecessor"
 for p in "$STATE/SEAL" "$STATE/phase" "$STATE/retained-files" "$STATE/predecessor"; do sha256sum "$p" >> "$g/baseline"; done
 while IFS= read -r p;do sha256sum "$p" >> "$g/baseline";done < "$STATE/retained-files"
 for c in $NATIVE_CONFIGS;do [ ! -f "/etc/config/$c" ] || sha256sum "/etc/config/$c" >> "$g/baseline";done
 while IFS='|' read -r p m v; do
  case "$m" in *:f) sha256sum "$p" >> "$g/baseline";; esac
 done < "$STATE/protected"
 chmod 600 "$g/baseline"
 # Caller simulates immediately before this point. Guard catches subsequent DB changes.
 if env -i PATH="$PATH" LC_ALL=C HOME=/root MT3600BE_NATIVE_DELTA="$STATE/native/delta" LD_PRELOAD="$KIT/apk-db-guard.so:$KIT/native-uci.so" MT3600BE_APK_BASELINE="$g/baseline" MT3600BE_APK_LOCK_RECEIPT="$g/receipt" apk --preserve-env --clean-protected --no-network --keys-dir "$KIT/keys" --repositories-file /dev/null -X "$KIT/repo/packages.adb" "$@" > "$g/apk.log" 2>&1; then
  [ "$(cat "$g/receipt")" = locked-and-checked ] || fail 'APK 锁内检查没有完成'
 else fail "APK 操作未完成，保留记录供重试：$g"; fi
 "$KIT/fs-safe" native-clean || fail '本事务 UCI 临时文件仍在使用或归属异常，保留现场'
}
make_plan() {
 PLAN=$(mktemp -d "$BASE/.prepare.XXXXXX")
 printf 'run-native-v4|%s\n' "$ID" > "$PLAN/identity"
 printf '%s\n' "$PREDECESSOR" > "$PLAN/predecessor"
 cp "$WORK/live" "$PLAN/versions"; cp /etc/apk/world "$PLAN/world"
 protected > "$PLAN/protected"
 : > "$PLAN/additions"; : > "$PLAN/files"; : > "$PLAN/integration"
 while IFS='|' read -r n v h p; do
  cur=$(awk -F= -v n="$n" '$1==n{print $2}' "$PLAN/versions")
  [ -z "$cur" ] || [ "$cur" = "$v" ] || fail "已有不同版本：$n；拒绝升级或降级"
  [ -n "$cur" ] || printf '%s=%s\n' "$n" "$v" >> "$PLAN/additions"
 done < "$KIT/packages.tsv"
 check_files
 retained_prepare
 templates_prepare
 while IFS='|' read -r n p m k v; do
  grep -q "^$n=" "$PLAN/additions" || continue
  safe_parents "$p"
  if ! grep -Fxq "$p" "$PLAN/retained-files";then
   [ ! -e "$p" ] && [ ! -L "$p" ] || fail "新包目标已有文件：$p"
  fi
  printf '%s|%s|%s|%s|%s\n' "$n" "$p" "$m" "$k" "$v" >> "$PLAN/files"
 done < "$KIT/files.tsv"
 grep -q '^luci-app-passwall2=' "$PLAN/additions" || fail '已有 Passwall2 安装，拒绝接管'
 # Record original alternatives links; native add/remove scripts may replace them.
 for f in /bin/base64 /usr/bin/nohup;do
  safe_parents "$f"
  if [ -e "$f" ] || [ -L "$f" ];then
   [ -L "$f" ] || fail 'alternatives 目标已有普通文件，拒绝替换'
   printf '%s|%s\n' "$f" "$(readlink "$f")"
  else printf '%s|absent\n' "$f";fi
 done > "$PLAN/integration"
 : > "$PLAN/service-links"
 retained_links_prepare
 for p in S99passwall2 K15passwall2 S99passwall2_server;do
  case "$p" in *passwall2_server) target=../init.d/passwall2_server;;*)target=../init.d/passwall2;;esac
  printf '/etc/rc.d/%s|%s\n' "$p" "$target" >> "$PLAN/service-links"
 done
 native_prepare
 native_plan_current
 retained_plan_current
 seal "$PLAN"
 printf 'prepared\n' > "$PLAN/phase"
 "$KIT/fs-safe" sync-tree "$PLAN"
 native_plan_current
 retained_plan_current
 predecessor_match "$PLAN/predecessor"
 predecessor_live
 "$KIT/fs-safe" publish "$PLAN" "$STATE"
}
integration_check() {
 while IFS='|' read -r p old;do
  case "$p" in /bin/base64) new=/usr/libexec/base64-coreutils;pkg=coreutils-base64;;/usr/bin/nohup) new=/usr/libexec/nohup-coreutils;pkg=coreutils-nohup;;*)fail '链接记录越界';;esac
  if [ -L "$p" ];then t=$(readlink "$p");else [ ! -e "$p" ] || fail '工具链接变为普通文件';t=absent;fi
  case "$t" in "$old"|"$new"|/bin/busybox) ;;*)fail '工具链接出现计划外修改';;esac
 done < "$STATE/integration"
}
orphan_check() {
 # Files unpacked before APK's database commit are not visible to apk del.
 while IFS='|' read -r n p m k v;do
  case "$p" in /etc/config/*) continue;;esac
  grep -q "^$n=" "$WORK/live" && continue
  [ -e "$p" ] || [ -L "$p" ] || continue
  file_matches "$p" "$m" "$k" "$v" || fail "未登记的中断遗留文件已被修改：$p；拒绝删除"
 done < "$STATE/files"
 while IFS='|' read -r p t;do
  [ -e "$p" ] || [ -L "$p" ] || continue
  file_matches "$p" 777 l "$t" || fail '启动链接已变化，拒绝删除'
 done < "$STATE/service-links"
}
orphan_remove() {
 orphan_check
 while IFS='|' read -r n p m k v;do
  case "$p" in /etc/config/*) continue;;esac
  grep -q "^$n=" "$WORK/live" && fail '包仍在数据库，不能清理文件'
  [ -e "$p" ] || [ -L "$p" ] || continue
  "$KIT/fs-safe" remove "$p" "$v" "$(meta "$p")" "$k" || fail '遗留文件清理被中断或发生变化，可重试'
 done < "$STATE/files"
 while IFS='|' read -r p t;do
  [ -e "$p" ] || [ -L "$p" ] || continue
  grep -Fqx "$p|$t" "$STATE/retained-links" && continue
  "$KIT/fs-safe" remove "$p" "$t" "$(meta "$p")" l || fail '启动链接清理失败，可重试'
 done < "$STATE/service-links"
}
replay_native_hooks() {
 # Native hooks are unchanged copies of the signed APK metadata. Replay only
 # packages added by this transaction. This finishes an interrupted first install.
 if ! native_ready;then
 while IFS='=' read -r n v;do
  [ -f "$KIT/hooks/$n.post-install" ] || continue
  env -i PATH="$PATH" LC_ALL=C HOME=/root MT3600BE_NATIVE_DELTA="$STATE/native/delta" LD_PRELOAD="$KIT/native-uci.so" "$KIT/fs-safe" run "$KIT/hooks/$n.post-install" > "$WORK/native-$n.log" 2>&1 || fail "原生初始化失败：$n；保留现场"
 "$KIT/fs-safe" native-clean || fail '原生提交清理未完成，可重试'
 done < "$STATE/additions"
 fi
 uci_clean;native_complete
 native_delta_clean
 if ! grep -Fxq /etc/config/passwall2 "$STATE/retained-files";then
  [ "$(uci -q get 'passwall2.@global[0].enabled')" = 0 ] || fail '初始化期间主开关已变化，拒绝继续'
 fi
 for f in /etc/rc.d/S99passwall2 /etc/rc.d/K15passwall2;do
  [ -L "$f" ] && [ "$(readlink "$f")" = ../init.d/passwall2 ] || fail '原生开机链接未建立'
 done
 /etc/init.d/ucitrack reload 8>&- 9>&- || fail '原生应用触发器加载失败，可重试'
}
# A previous parent may have exited while native APK hooks are still finishing.
# Probe the real APK lock BEFORE reading or preparing a replacement attempt.
[ ! -L /lib/apk/db/lock ] || fail 'APK 数据库锁异常'
(exec 7>>/lib/apk/db/lock;flock -xn 7) || { echo 'APK 操作尚未结束，请稍后重试。' >&2;exit 75; }
identity; echo '正在验证离线依赖与 APK 签名……'; verify_packages
if [ -e "$STATE" ] || [ -L "$STATE" ]; then validate_state; else
 [ "$ACTION" != rollback ] || fail '没有本工具事务，不能卸载其他安装'
 predecessor_read
 predecessor_live
 if [ "$ACTION" = check ]; then
  # Preflight uses disposable planning records; never publishes a transaction.
  echo '身份与签名检查通过；完整安装计划将在 install --apply 内建立。'; exit 0
 fi
 free_k=$(df -k /overlay | awk 'END{print $4}')
 case "$free_k" in ''|*[!0-9]*)fail '无法确认存储空间';;esac
 [ "$free_k" -ge 150000 ] || fail '需要至少 150000 KiB 可用存储；未安装'
 make_plan; validate_state
fi
# Validate transaction identity first; then reclaim only proven native aliases.
"$KIT/fs-safe" native-clean || fail 'UCI 提交仍在进行或残留归属不明；未继续安装或回滚'
# A successful repeat install is a no-op, including when the user runs a proxy.
if [ "$ACTION" = install ] && [ "$PHASE" = installed ];then
 echo '本事务此前已安装完成；本次没有重装或重启服务。';exit 0
fi
inactive
live_subset; integration_check
[ "$ACTION" != check ] || { echo "事务检查通过：$PHASE"; exit 0; }
if [ "$ACTION" = install ]; then
 case "$PHASE" in
 installed) echo '已安装；未重复安装、启动或重启代理。'; exit 0;;
 removing|cleaning|rolled-back) fail '该事务已进入回滚；禁止反向复用或覆盖旧记录';;
 esac
 echo '正在安装缺失组件并执行 Passwall2 原生初始化……'
 phase installing
 awk -F= 'FILENAME==ARGV[1]{live[$0]=1;next}!($0 in live){print}' "$WORK/live" "$STATE/additions" > "$WORK/missing"
 if [ -s "$WORK/missing" ]; then
  set -- $(cat "$WORK/missing")
  apk_command add --simulate "$@" > "$WORK/plan" 2>&1 || fail '离线依赖解析失败，未安装'
  awk '{for(i=1;i<NF;i++)if($i=="Installing")print $(i+1)}' "$WORK/plan" | sort > "$WORK/actual"
  cut -d= -f1 "$WORK/missing" | sort > "$WORK/expected"
  cmp -s "$WORK/actual" "$WORK/expected" || fail '安装计划包含缺失或额外包'
  grep -Eq 'Upgrading|Downgrading|Reinstalling|Purging' "$WORK/plan" && fail '安装计划会改动已有包'
  execute_apk add "$@"
 fi
 live_subset
 while IFS= read -r pin; do grep -Fxq "$pin" "$WORK/live" || fail '包安装未完成'; done < "$STATE/additions"
 phase integrating; replay_native_hooks; live_subset; integration_check
 phase installed
 echo '安装完成；已有插件配置及主开关保留，新配置默认关闭。请在 LuCI 核对并保存应用。'
 exit 0
fi
# Rollback is monotonic. Restore only journaled native changes with exact guards.
if [ "$PHASE" = rolled-back ]; then
 while IFS='=' read -r n v; do grep -q "^$n=" "$WORK/live" && fail '已回滚包重新出现'; done < "$STATE/additions"
 echo '此前已回滚，不重复删除。'; exit 0
fi
echo '正在卸载本次新增包……'
orphan_check
phase removing
awk -F= 'FILENAME==ARGV[1]{live[$0]=1;next}$0 in live {print $1}' "$WORK/live" "$STATE/additions" > "$WORK/remove"
if [ -s "$WORK/remove" ]; then
 set -- $(cat "$WORK/remove")
 apk_command del --simulate "$@" > "$WORK/plan" 2>&1 || fail '卸载依赖检查失败'
 awk '{for(i=1;i<NF;i++)if($i=="Purging")print $(i+1)}' "$WORK/plan" | sort > "$WORK/actual"
 sort "$WORK/remove" > "$WORK/expected"
 cmp -s "$WORK/actual" "$WORK/expected" || fail '卸载会影响原有包，或新增包被其他包使用'
 grep -Eq 'Installing|Upgrading|Downgrading|Reinstalling' "$WORK/plan" && fail '卸载计划包含额外操作'
 execute_apk del "$@"
fi
live_subset
while IFS='=' read -r n v; do grep -q "^$n=" "$WORK/live" && fail '新增包尚未全部卸载'; done < "$STATE/additions"
echo '正在恢复原生接入改动……'
phase cleaning
orphan_remove
integration_check
native_restore
retained_links_restore
retained_validate_live
while IFS='|' read -r p old;do
 case "$p" in /bin/base64) pkg=coreutils-base64;;/usr/bin/nohup) pkg=coreutils-nohup;;*)fail '链接记录越界';;esac
 grep -q "^$pkg=" "$STATE/additions" || continue
 if [ "$old" = absent ];then [ ! -L "$p" ] || rm "$p"
 else
  t=$(mktemp -u "$(dirname "$p")/.pw-native-link.XXXXXX")
  ln -s "$old" "$t" || fail '链接暂存失败'
  "$KIT/fs-safe" link-restore "$t" "$p" || fail '链接恢复失败，可重试'
 fi
done < "$STATE/integration"
/etc/init.d/ucitrack reload 8>&- 9>&- || fail '卸载后触发器刷新失败，可重试'
cmp -s "$STATE/world" /etc/apk/world || fail 'world 未恢复原始内容；不强制覆盖'
templates_cleanup
phase rolled-back
echo '已卸载本次新增包并恢复记录的原生接入修改；原有包、用户插件配置和事务记录保留。'
