from pathlib import Path
import base64,hashlib,io,tarfile,gzip,shutil
P=Path(__file__).resolve().parent
D=P/'tool';patch=D/'patch'
if not patch.exists():shutil.copytree(P/'patch-v1',patch)
else:
 for source in (P/'patch-v1').iterdir():
  if not (patch/source.name).is_file() or (patch/source.name).read_bytes()!=source.read_bytes():
   raise SystemExit('Staged patch differs from patch-v1; refusing stale build')
files=['menu.sh']+['patch/'+n for n in ['eee-state','eee-state.c','mt3600be-wan-eee','init','hotplug','install.sh','README.md','SHA256SUMS']]
(D/'SHA256SUMS').write_text(''.join(hashlib.sha256((D/f).read_bytes()).hexdigest()+'  '+f+'\n' for f in files))
b=io.BytesIO()
with tarfile.open(fileobj=b,mode='w') as t:
 for f in files+['SHA256SUMS']:
  info=t.gettarinfo(str(D/f),f);info.uid=info.gid=0;info.uname=info.gname='root';info.mtime=0
  info.mode=0o755 if f in {'menu.sh','patch/eee-state','patch/mt3600be-wan-eee','patch/init','patch/hotplug','patch/install.sh'} else (0o664 if f == 'SHA256SUMS' else 0o644)
  with (D/f).open('rb') as src:t.addfile(info,src)
payload=gzip.compress(b.getvalue(),mtime=0)
header='''#!/bin/sh
# MT3600BE EEE tool v1.2. No passwords, configuration snapshots or router identity.
set -eu
umask 077
TMP=$(mktemp -d /tmp/mt3600be-eee-tool.XXXXXXXX) || exit 1
child=''
cleanup() { rm -rf "$TMP"; }
interrupt() {
 trap '' HUP INT TERM
 if [ -n "$child" ]; then kill -TERM "$child" 2>/dev/null || :; wait "$child" 2>/dev/null || :; fi
 exit 130
}
trap cleanup EXIT
trap interrupt HUP INT TERM
awk 'f { print } $0 == "__MT3600BE_EEE_PAYLOAD__" { f=1 }' "$0" > "$TMP/payload.b64"
if command -v base64 >/dev/null 2>&1; then
 decoder=base64
elif command -v openssl >/dev/null 2>&1; then
 decoder=openssl
else
 echo '缺少 base64 和 OpenSSL 解码工具，未执行。' >&2
 exit 1
fi
decode_payload() {
 if [ "$decoder" = base64 ]; then
  base64 -d "$TMP/payload.b64"
 else
  openssl base64 -d -in "$TMP/payload.b64"
 fi
}
decode_payload > "$TMP/payload.tgz" || { echo '解码失败，未执行。' >&2; exit 1; }
printf '%s  %s\\n' '@HASH@' "$TMP/payload.tgz" | sha256sum -c - >/dev/null || { echo '离线包损坏，未执行。' >&2; exit 1; }
mkdir "$TMP/run"
tar -xzf "$TMP/payload.tgz" -C "$TMP/run"
(cd "$TMP/run"; sha256sum -c SHA256SUMS >/dev/null) || exit 1
exec 3<&0
sh "$TMP/run/menu.sh" "$@" <&3 &
child=$!
exec 3<&-
rc=0; wait "$child" || rc=$?
child=''
exit "$rc"
__MT3600BE_EEE_PAYLOAD__
'''.replace('@HASH@',hashlib.sha256(payload).hexdigest())
release=P/'release';release.mkdir(exist_ok=True)
out=release/'mt3600be-eee-tool-v1.2-r4.run';out.write_bytes(header.encode()+base64.encodebytes(payload));out.chmod(0o755)
(release/'SHA256SUMS').write_text(hashlib.sha256(out.read_bytes()).hexdigest()+'  '+out.name+'\n')
print(out);print((release/'SHA256SUMS').read_text())

import zipfile
checksum=hashlib.sha256(out.read_bytes()).hexdigest()+'  '+out.name+'\n'
(release/'mt3600be-eee-tool-v1.2-r4.sha256').write_text(checksum)
zipout=release/'mt3600be-eee-tool-v1.2-r4.zip'
with zipfile.ZipFile(zipout,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for name in [out.name,'mt3600be-eee-tool-v1.2-r4.sha256','小白使用说明.md']:
  info=zipfile.ZipInfo(name,date_time=(2026,10,26,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
  z.writestr(info,(release/name).read_bytes())
zipchecksum=hashlib.sha256(zipout.read_bytes()).hexdigest()+'  '+zipout.name+'\n'
(release/'mt3600be-eee-tool-v1.2-r4.zip.sha256').write_text(zipchecksum)
(release/'SHA256SUMS').write_text(checksum+zipchecksum+hashlib.sha256((release/'小白使用说明.md').read_bytes()).hexdigest()+'  小白使用说明.md\n')
