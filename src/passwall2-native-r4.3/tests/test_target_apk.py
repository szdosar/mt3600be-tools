#!/usr/bin/env python3
from native_fixture import *
from test_retained_v4_2 import Restored42
HELPERS={n:sha(PAYLOAD/n) for n in ['fs-safe','uci-plan','apk-db-guard.so','native-uci.so']}
f=Fixture();result={'passed':False,'real_target_ARM_APK':True,'services':'fixtures','no_network_or_router_or_VM':True}
try:
 shutil.copyfile(PUBLIC/'usr/bin/apk',f.root/'fixture/apk.arm');(f.root/'fixture/apk.arm').chmod(0o755)
 shutil.copyfile(PAYLOAD/'apk-db-guard.so',f.root/'fixture/guard.arm.so')
 shutil.copyfile(PAYLOAD/'fs-safe',f.root/'fixture/fs-safe.arm');(f.root/'fixture/fs-safe.arm').chmod(0o755)
 f.write('usr/bin/apk-real',r'''#!/bin/sh
if [ -n "${MT3600BE_APK_BASELINE:-}" ];then
 exec /bin/qemu -L / -E LD_PRELOAD=/fixture/guard.arm.so:/kit/native-uci.arm.so /fixture/apk.arm "$@"
else
 exec /bin/qemu -L / -U LD_PRELOAD /fixture/apk.arm "$@"
fi
''',0o755)
 # Exercise new archival with the actual ARM helper, not only host compilation.
 f.write('kit/fs-safe','#!/bin/sh\nexec /bin/qemu -L / /fixture/fs-safe.arm "$@"\n',0o755);f.freeze()
 f.state.parent.mkdir(mode=0o700,exist_ok=True)
 for name in ['', 'native', 'native/expected']:(f.state/name).mkdir(mode=0o700,exist_ok=True)
 empty_inode=f.state.stat().st_ino
 checker=Restored42();checker.f=f;checker.setup664(links=True)
 print(f.action().stdout,flush=True);checker.preserved();checker.templates();print(f.action().stdout,flush=True);checker.preserved();print(f.action('rollback').stdout,flush=True);checker.restored();checker.absent()
 archives=list(f.state.parent.glob('empty-transaction-archive.*'))
 assert len(archives)==1 and (archives[0]/'transaction').stat().st_ino==empty_inode
 assert not any(p.is_file() for p in archives[0].rglob('*'))
 result.update(target_empty_archive_restored_configs=True)
 result.update(target_restored_configs_and_rules=True,target_default_server_retained=True,target_old_links_restored=True,target_root664_preserved=True,target_separate_templates=True)
 for c,b in f.before.items():assert (f.root/'etc/config'/c).read_bytes()==b,c
 # Real ARM helper atomic replacement and metadata preservation.
 d=f.root/'root/mt3600be-passwall2-run-v4/.attempt.arm';d.mkdir()
 (d/'source').write_text('public synthetic restore\n');(d/'source').chmod(0o640)
 (d/'dest').write_text('old\n');(d/'dest').chmod(0o644)
 f.cmd('/bin/qemu','-L','/','/fixture/fs-safe.arm','restore','/root/mt3600be-passwall2-run-v4/.attempt.arm/source','/root/mt3600be-passwall2-run-v4/.attempt.arm/dest','/root/mt3600be-passwall2-run-v4/.attempt.arm',sha(d/'dest'),'0:0:644:f')
 assert (d/'source').read_bytes()==(d/'dest').read_bytes() and (d/'dest').stat().st_mode&0o777==0o640
 # Real ARM targeted durability operation; reject links rather than following them.
 syncdir=f.root/'root/mt3600be-passwall2-run-v4/.prepare.arm-sync';syncdir.mkdir(mode=0o700)
 (syncdir/'nested').mkdir();(syncdir/'nested/public-file').write_text('synthetic transaction\n')
 f.cmd('/bin/qemu','-L','/','/fixture/fs-safe.arm','sync-tree','/root/mt3600be-passwall2-run-v4/.prepare.arm-sync')
 (syncdir/'outside-link').symlink_to('/etc/config/network')
 assert f.cmd('/bin/qemu','-L','/','/fixture/fs-safe.arm','sync-tree','/root/mt3600be-passwall2-run-v4/.prepare.arm-sync',ok=False).returncode != 0
 (syncdir/'outside-link').unlink()
 result.update(target_sync_tree=True,target_sync_tree_symlink_refused=True)
 # Real ARM snapshot and owned-temp cleanup, not only host-compiled helpers.
 snap=f.root/'root/mt3600be-passwall2-run-v4/.prepare.arm-snapshot';snap.mkdir(mode=0o700)
 f.cmd('/bin/qemu','-L','/','/fixture/fs-safe.arm','snapshot','/etc/config/firewall','/root/mt3600be-passwall2-run-v4/.prepare.arm-snapshot/before','/root/mt3600be-passwall2-run-v4/.prepare.arm-snapshot/expected')
 assert (snap/'before').read_bytes()==(snap/'expected').read_bytes()==f.before['firewall']
 assert (snap/'before').stat().st_mode&0o777==f.before_modes['firewall']
 own=f.state/'native/commits/dhcp.AbC123';own.mkdir(mode=0o700);(own/'data').write_text('synthetic partial commit\n');(own/'data').chmod(0o600)
 alias=f.root/'etc/config/.dhcp.uci-AbC123';os.link(own/'data',alias)
 f.cmd('/bin/qemu','-L','/','/fixture/fs-safe.arm','native-clean')
 assert not alias.exists() and not own.exists()
 result.update(target_snapshot_consistent=True,target_owned_commit_cleanup=True)
 assert HELPERS=={n:sha(PAYLOAD/n) for n in HELPERS}
 result.update(helper_sha256=HELPERS,passed=True,target_APK_install_rollback=True,target_guard_lock_receipt=True,target_atomic_helper=True)
except Exception:
 print('retained fixture',f.tmp,flush=True);raise
else:f.close()
finally:
 (W/'mt3600be-run-native-high-r4.3-20261031/target-apk-tests.json').write_text(json.dumps(result,indent=2)+'\n')
