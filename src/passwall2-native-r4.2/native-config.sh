# Sourced by controller. Runtime snapshots stay ONLY on the router, under 0700.
NATIVE_CONFIGS='dhcp firewall uhttpd ucitrack luci'
native_prepare() {
 mkdir -m 700 "$PLAN/native" "$PLAN/native/before" "$PLAN/native/expected"
 mkdir -m 700 "$PLAN/native/delta" "$PLAN/native/commits"
 : > "$PLAN/native/commit.lock"
 mkdir -m 700 "$PLAN/native/expected/.delta" "$PLAN/native/expected/.override"
 : > "$PLAN/native/variants"; : > "$PLAN/native/meta"
 for c in $NATIVE_CONFIGS; do
  p=/etc/config/$c;safe_parents "$p"
  if [ -e "$p" ] || [ -L "$p" ]; then
   regular "$p";"$KIT/fs-safe" snapshot "$p" "$PLAN/native/before/$c" "$PLAN/native/expected/$c" || fail "配置快照竞争或失败：$c"
   printf '%s|%s|%s\n' "$c" "$(hash "$PLAN/native/before/$c")" "$(meta "$PLAN/native/before/$c")" >> "$PLAN/native/meta"
   printf '%s|%s\n' "$c" "$(hash "$PLAN/native/before/$c")" >> "$PLAN/native/variants"
  else
   [ "$c" = ucitrack ] || fail "原厂配置缺失：$c"
   printf '%s|absent|-\n' "$c" >> "$PLAN/native/meta"
   printf '%s|absent\n' "$c" >> "$PLAN/native/variants"
  fi
 done
 # Project the unchanged native hooks against the captured restored baseline.
 "$KIT/uci-plan" "$PLAN/native/expected" validate-existing || fail '旧接入记录不符合原生结构，保留现场待核对'
 for step in ucitrack1 dhcp uhttpd firewall1 ucitrack2 luci; do
  c=${step%1};c=${c%2}
  [ -f "$PLAN/native/expected/$c" ] || continue
  "$KIT/uci-plan" "$PLAN/native/expected" "$step" || fail '原生配置变更预演失败，未安装'
  printf '%s|%s\n' "$c" "$(hash "$PLAN/native/expected/$c")" >> "$PLAN/native/variants"
 done
 uci_clean
}
native_validate() {
 for c in $NATIVE_CONFIGS;do
  p=/etc/config/$c;safe_parents "$p"
  if [ -e "$p" ] || [ -L "$p" ];then regular "$p";v=$(hash "$p");else v=absent;fi
  original=$(awk -F'|' -v c="$c" '$1==c{print $3}' "$STATE/native/meta")
  if [ "$original" != - ];then
   [ "$(meta "$STATE/native/before/$c")" = "$original" ] || fail '配置快照权限记录损坏'
   now=$(meta "$p");rootmeta="0:0:$(printf '%s' "$original" | cut -d: -f3-)"
   [ "$now" = "$original" ] || [ "$now" = "$rootmeta" ] || fail "共享配置权限已变化：$c"
  fi
  grep -Fxq "$c|$v" "$STATE/native/variants" || fail "共享配置出现计划外修改：$c；拒绝自动覆盖或卸载"
 done
}
native_complete() {
 for c in $NATIVE_CONFIGS;do
  [ -f "$STATE/native/expected/$c" ] || continue
  [ "$(hash "/etc/config/$c")" = "$(hash "$STATE/native/expected/$c")" ] || fail "原生初始化尚未完成：$c"
 done
}
native_restore() {
 native_validate
 # Freeze each authorized current version before any restore helper starts.
 : > "$WORK/restore-authorized"
 for c in $NATIVE_CONFIGS;do
  [ ! -f "$STATE/native/before/$c" ] || printf "%s|%s|%s\n" "$c" "$(hash /etc/config/$c)" "$(meta /etc/config/$c)" >> "$WORK/restore-authorized"
 done
 native_validate
 while IFS="|" read -r c authorized_digest authorized_meta;do
  if [ -f "$STATE/native/before/$c" ];then
   "$KIT/fs-safe" restore "$STATE/native/before/$c" "/etc/config/$c" "$WORK" "$authorized_digest" "$authorized_meta" || fail "恢复配置失败：$c；可以重试"
  fi
 done < "$WORK/restore-authorized"
 for c in $NATIVE_CONFIGS;do
  [ -f "$STATE/native/before/$c" ] || continue
  [ "$(hash "/etc/config/$c")" = "$(hash "$STATE/native/before/$c")" ] || fail '配置恢复核验失败'
  expect=$(awk -F'|' -v c="$c" '$1==c{print $3}' "$STATE/native/meta")
  [ "$(meta "/etc/config/$c")" = "$expect" ] || fail '配置权限恢复核验失败'
 done
}

native_ready() {
 for c in $NATIVE_CONFIGS;do
  [ -f "$STATE/native/expected/$c" ] || continue
  [ -f "/etc/config/$c" ] && cmp -s "$STATE/native/expected/$c" "/etc/config/$c" || return 1
 done
 [ -f /etc/config/passwall2 ] || return 1
 for f in /etc/rc.d/S99passwall2 /etc/rc.d/K15passwall2;do
  [ -L "$f" ] && [ "$(readlink "$f")" = ../init.d/passwall2 ] || return 1
 done
 return 0
}

# Only this transaction's private delta; never flush unrelated user changes.
native_delta_clean() {
 pending=$(MT3600BE_NATIVE_DELTA="$STATE/native/delta" LD_PRELOAD="$KIT/native-uci.so" uci changes) || fail '私有 UCI 暂存查询失败'
 [ -z "$pending" ] || fail '原生脚本仍有未完成的私有暂存，可重试安装或回滚'
}

# Baseline hashes come only from the captured snapshot, never a later live file.
native_plan_current() {
 for c in $NATIVE_CONFIGS;do
  if [ -f "$PLAN/native/before/$c" ];then
   regular "/etc/config/$c"
   [ "$(hash /etc/config/$c)" = "$(hash "$PLAN/native/before/$c")" ] && [ "$(meta /etc/config/$c)" = "$(meta "$PLAN/native/before/$c")" ] || fail "快照后配置发生变化：$c；未发布事务"
  else
   [ ! -e "/etc/config/$c" ] && [ ! -L "/etc/config/$c" ] || fail '快照后配置出现'
  fi
 done
 uci_clean
}

# Restored plugin configuration is user data, never proof of an installed APK.
retained_prepare() {
 mkdir -m 700 "$PLAN/retained" "$PLAN/retained/before" "$PLAN/retained/expected"
 : > "$PLAN/retained-files"
 for p in /etc/config/passwall2 /etc/config/passwall2_server;do
  safe_parents "$p"
  [ ! -e "$p.apk-new" ] && [ ! -L "$p.apk-new" ] || fail "已有未归属的 APK 配置残留：$p.apk-new"
  [ -e "$p" ] || [ -L "$p" ] || continue
  regular "$p"; [ -s "$p" ] || fail "恢复的插件配置为空，请先核对：$p"
  file_meta=$(meta "$p") || fail "无法读取恢复配置元数据：$p"
  case "$file_meta" in 0:0:600:f|0:0:640:f|0:0:644:f|0:0:664:f) ;;*)fail "恢复配置归属或权限异常：$p ($file_meta)；仅接受 root:root 600/640/644/664 普通文件";;esac
  uci -q show "${p##*/}" > /dev/null || fail "恢复的插件配置无法解析：$p"
  "$KIT/fs-safe" snapshot "$p" "$PLAN/retained/before/${p##*/}" "$PLAN/retained/expected/${p##*/}" || fail '插件配置快照失败'
  printf '%s\n' "$p" >> "$PLAN/retained-files"
 done
}
retained_validate_record() {
 awk '($0!="/etc/config/passwall2" && $0!="/etc/config/passwall2_server") || seen[$0]++ {bad=1} END{exit bad}' "$STATE/retained-files" || fail '保留文件记录越界'
 for p in /etc/config/passwall2 /etc/config/passwall2_server;do
  if grep -Fxq "$p" "$STATE/retained-files";then
   regular "$STATE/retained/before/${p##*/}";regular "$STATE/retained/expected/${p##*/}"
   cmp -s "$STATE/retained/before/${p##*/}" "$STATE/retained/expected/${p##*/}" || fail '保留快照不一致'
  else
   [ ! -e "$STATE/retained/before/${p##*/}" ] && [ ! -e "$STATE/retained/expected/${p##*/}" ] || fail '保留快照清单缺项'
  fi
 done
 awk -F'|' 'NF!=2 || ($1!="/etc/rc.d/S99passwall2" && $1!="/etc/rc.d/K15passwall2" && $1!="/etc/rc.d/S99passwall2_server") || ($1~/server$/ ? $2!="../init.d/passwall2_server" : $2!="../init.d/passwall2") || seen[$1]++ {bad=1} END{exit bad}' "$STATE/retained-links" || fail '保留启动链接记录异常'
}
retained_plan_current() {
 while IFS= read -r p;do
  regular "$p"
  cmp -s "$p" "$PLAN/retained/before/${p##*/}" && [ "$(meta "$p")" = "$(meta "$PLAN/retained/before/${p##*/}")" ] || fail '插件配置在准备期间已变化'
 done < "$PLAN/retained-files"
 while IFS='|' read -r p t;do
  [ -L "$p" ] && [ "$(readlink "$p")" = "$t" ] || fail '旧启动链接在准备期间已变化'
 done < "$PLAN/retained-links"
}
retained_validate_live() {
 while IFS= read -r p;do
  safe_parents "$p";regular "$p"
  if [ "$ACTION" = install ];then
   cmp -s "$p" "$STATE/retained/before/${p##*/}" && [ "$(meta "$p")" = "$(meta "$STATE/retained/before/${p##*/}")" ] || fail '补装中已有插件配置变化，拒绝覆盖'
  fi
 done < "$STATE/retained-files"
}
retained_links_prepare() {
 : > "$PLAN/retained-links"
 for p in /etc/rc.d/*passwall2*;do
  [ -e "$p" ] || [ -L "$p" ] || continue
  case "$p" in /etc/rc.d/S99passwall2|/etc/rc.d/K15passwall2) want=../init.d/passwall2;;/etc/rc.d/S99passwall2_server) want=../init.d/passwall2_server;;*)fail '非原生启动链接，拒绝接管';;esac
  [ -L "$p" ] && [ "$(readlink "$p")" = "$want" ] || fail '原生启动链接内容异常'
  printf '%s|%s\n' "$p" "$want" >> "$PLAN/retained-links"
 done
}
retained_links_restore() {
 while IFS='|' read -r p t;do
  if [ -e "$p" ] || [ -L "$p" ];then
   [ -L "$p" ] && [ "$(readlink "$p")" = "$t" ] || fail '启动链接出现新内容，不覆盖'
  else
   ln -s "$t" "$p" || fail '恢复启动链接失败，可重试'
  fi
 done < "$STATE/retained-links"
}


# Read-only handover from the frozen r3 release. A retained history directory is
# not an installed package. No old journal is deleted, renamed, sourced or edited.
R3=/root/mt3600be-passwall2-run-v3/transaction
R3_ID=524eb3afeae27e966fc42cebbdf1d9d3f38672d77de907e756f895cc11b65a14
predecessor_read() {
 PREDECESSOR=none
 if [ ! -e "$R3" ] && [ ! -L "$R3" ];then return;fi
 private_dir /root/mt3600be-passwall2-run-v3;private_dir "$R3"
 for n in identity phase versions world protected additions files integration service-links SEAL;do private_file "$R3/$n";done
 find "$R3" ! -type f ! -type d | grep . >/dev/null && fail '旧 r3 记录含链接或特殊文件'
 # Bound traversal and hashing to ordinary canonical journal names.
 (cd "$R3";find .) | awk '$0 !~ /^\.[A-Za-z0-9_.\/-]*$/ {bad=1} END{exit bad}' || fail '旧 r3 记录路径异常'
 [ "$(cat "$R3/identity")" = "run-native-v3|$R3_ID" ] || fail '旧 r3 归属不明，请使用原包检查'
 [ "$(cat "$R3/phase")" = rolled-back ] || fail '旧 r3 尚未完成回滚，请使用原包 rollback --apply'
 prior_seal=$(cd "$R3";find . -type f ! -name SEAL ! -name phase ! -path './native/delta/*' ! -path './native/commits/*' | sort | while IFS= read -r f;do sha256sum "$f";done)
 [ "$prior_seal" = "$(cat "$R3/SEAL")" ] || fail '旧 r3 原始记录损坏，不接管'
 for d in native native/before native/expected native/delta native/commits;do private_dir "$R3/$d";done
 for n in native/meta native/variants native/commit.lock;do private_file "$R3/$n";done
 # Do not clean an old release's leases or pending work. It must finish itself.
 [ -z "$(find "$R3/native/commits" -mindepth 1 -print)" ] || fail '旧 r3 提交残留未清理，请先用原包回滚'
 (exec 7<"$R3/native/commit.lock";flock -xn 7) || fail '旧 r3 提交仍在运行，请稍后重试'
 for f in "$R3/native/delta"/*;do
  [ -e "$f" ] || continue
  case "${f##*/}" in dhcp|firewall|uhttpd|ucitrack|luci|passwall2|passwall2_server) ;;*)fail '旧 r3 私有暂存越界';;esac
  private_file "$f"
 done
 awk -F= 'NF!=2 || $1!~/^[a-z0-9][a-z0-9+_.-]*$/ || $2!~/^[A-Za-z0-9+_.~-]+$/ || seen[$1]++ {bad=1} END{exit bad || NR==0}' "$R3/additions" || fail '旧 r3 新增包记录异常'
 awk -F'|' 'NF!=3 || $1!~/^(dhcp|firewall|uhttpd|ucitrack|luci)$/ || seen[$1]++ || ($2!="absent" && (length($2)!=64 || $2~/[^0-9a-f]/)) {bad=1} END{exit bad || NR!=5}' "$R3/native/meta" || fail '旧 r3 配置记录不完整'
 # Fingerprint all files AND metadata, including normally mutable phase/deltas.
 # This becomes sealed provenance for r4 retries, never an installation marker.
 prior_tree=$(cd "$R3";find . | sort | while IFS= read -r f;do
  printf '%s|%s\n' "$f" "$(meta "$f")" || exit 1
  [ -d "$f" ] || sha256sum "$f" || exit 1
 done) || fail '旧 r3 历史摘要读取失败'
 PREDECESSOR="r3|$(printf '%s\n' "$prior_tree" | sha256sum | awk '{print $1}')"
}
predecessor_match() {
 private_file "$1"
 saved_predecessor=$(cat "$1")
 case "$saved_predecessor" in none) ;;r3\|*)
  printf '%s\n' "$saved_predecessor" | awk -F'|' 'NF!=2 || $1!="r3" || length($2)!=64 || $2~/[^0-9a-f]/ {exit 1}' || fail '前序事务记录异常';;
 *) fail '前序事务记录异常';;esac
 predecessor_read
 [ "$PREDECESSOR" = "$saved_predecessor" ] || fail '旧 r3 记录在接续后发生变化；保留现场，不覆盖'
}
predecessor_live() {
 [ "$PREDECESSOR" != none ] || return 0
 # Only before a new transaction: after r4 installs these packages, its own
 # sealed additions and baseline govern resume/rollback instead of r3's list.
 versions > "$WORK/predecessor-live"
 while IFS='=' read -r n v;do
  awk -F'|' -v n="$n" -v v="$v" '$1==n && $2==v{found=1} END{exit !found}' "$KIT/packages.tsv" || fail '旧 r3 新增包超出已知组合'
  if awk -F= -v n="$n" '$1==n{found=1} END{exit !found}' "$WORK/predecessor-live";then fail '旧 r3 新增包仍在，不能视作已回滚';fi
 done < "$R3/additions"
 while IFS='|' read -r c digest original_meta;do
  p=/etc/config/$c
  if [ "$digest" = absent ];then
   [ "$c" = ucitrack ] && [ "$original_meta" = - ] || fail '旧 r3 基线异常'
   # Native r3 may create this file. Let the current strict native planner
   # validate the now-existing standard records; never overwrite from history.
   continue
  fi
  regular "$R3/native/before/$c";regular "$p"
  [ "$(hash "$R3/native/before/$c")" = "$digest" ] && [ "$(meta "$R3/native/before/$c")" = "$original_meta" ] || fail '旧 r3 快照与记录不符'
  [ "$(hash "$p")" = "$digest" ] && [ "$(meta "$p")" = "$original_meta" ] || fail "旧 r3 回滚后的共享配置不符：$c；不自动覆盖，请先核对"
 done < "$R3/native/meta"
 # Installed-file checks and live r4 planning independently reject orphaned
 # binaries, nonstandard includes or incompatible retained configurations.
}

# Public default templates are separate from restored user configuration.
# Only the sealed receipt is immutable; user edits to templates are preserved.
templates_prepare() {
 mkdir -m 700 "$PLAN/defaults"
 : > "$PLAN/default-templates"
 for name in passwall2 passwall2_server;do
  regular "$KIT/default-templates/$name"
  expected=$(awk -F'|' -v n="$name" '$1==n{print $2}' "$KIT/template-files.tsv")
  [ "$(hash "$KIT/default-templates/$name")" = "$expected" ] || fail '默认模板摘要不符'
  (set -C; cat "$KIT/default-templates/$name" > "$PLAN/defaults/$name") || fail '默认模板保存失败；未发布事务'
  chmod 600 "$PLAN/defaults/$name"
  [ "$(hash "$PLAN/defaults/$name")" = "$expected" ] || fail '默认模板复制校验失败'
  printf '%s|%s\n' "$name" "$expected" >> "$PLAN/default-templates"
 done
}
templates_validate() {
 private_dir "$STATE/defaults"
 private_file "$STATE/default-templates"
 cmp -s "$STATE/default-templates" "$KIT/template-files.tsv" || fail '默认模板归属记录异常；不卸载或覆盖'
 # Missing templates can be a completed step of interrupted rollback.
 for name in passwall2 passwall2_server;do
  p="$STATE/defaults/$name"
  if [ ! -e "$p" ] && [ ! -L "$p" ];then
   case "$(cat "$STATE/phase")" in cleaning|rolled-back) continue;;*)fail '默认模板缺失；不覆盖或误报安装完成';;esac
  fi
  regular "$p"
 done
}
templates_cleanup() {
 templates_validate
 while IFS='|' read -r name expected;do
  p="$STATE/defaults/$name"
  [ -e "$p" ] || [ -L "$p" ] || continue
  regular "$p"
  if [ "$(hash "$p")" = "$expected" ] && [ "$(meta "$p")" = 0:0:600:f ];then
   "$KIT/fs-safe" remove "$p" "$expected" 0:0:600:f f || fail '模板清理发生竞争或中断；保留现场，可重试回滚'
  else
   echo "保留用户修改的默认模板：$p"
  fi
 done < "$STATE/default-templates"
}
