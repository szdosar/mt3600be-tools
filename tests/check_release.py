#!/usr/bin/env python3
"""Fail closed before public publication. Assets folder must be curated."""
from pathlib import Path
import base64,hashlib,io,json,re,sys,tarfile
D=Path(__file__).resolve().parents[1];A=Path(sys.argv[1]);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=json.loads((D/'tests/results.json').read_text());b=json.loads((D/'tests/bootstrap-results.json').read_text())
assert a['passed'] and a['tests_run']==32 and not a['skipped'] and a['source_sha256']==sha(D/'install.sh')
assert b['passed'] and b['tests_run']==7 and b['bootstrap_sha256']==sha(D/'bootstrap.sh') and b['launcher_sha256']==sha(D/'install.sh')
c=json.loads((D/'tests/target-results.json').read_text())
assert c['passed'] and c['tests_run']==18 and not c['skipped'] and not c['failures'] and not c['errors'] and c['source_sha256']==sha(D/'install.sh')
assert sha(D/'install.sh') in (D/'README.md').read_text()
for line in ((D/'sources.sha256').read_text()+(D/'online.sha256').read_text()).splitlines():
 digest,n=line.split('  ',1);assert sha(D/n)==digest,n
for p in D.rglob('*'):
 if '.git' in p.parts or '__pycache__' in p.parts:continue
 assert not p.is_symlink(),p
 if not p.is_file():continue
 assert p.suffix not in ['.run','.apk','.bin','.zip','.pem','.key'],p
 assert p.name not in ['shadow','authorized_keys','original.bin','config.yaml','identity.secret','authtoken.secret'],p
 data=p.read_bytes();assert not re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}',data),p
for name in ['install.sh','bootstrap.sh','install.sha256','README.md','catalog.json']:
 assert (A/'online-v1.3'/name).read_bytes()==(D/name).read_bytes(),name
cat=json.loads((D/'catalog.json').read_text());rows=[]
pw=json.loads((D/'tests/passwall2-r4.3-validation.json').read_text())
assert pw['release']=='native-r4.3' and pw['regression']['passed'] and pw['regression']['tests_run']==113
assert pw['envelope']['passed'] and pw['envelope']['tests_run']==10 and pw['target_ARM_APK_UCI']['target_empty_archive_restored_configs']
assert pw['artifact']['sha256']==cat[1]['sha256'] and pw['artifact']['bytes']==cat[1]['bytes']
assert pw['regression']['source_sha256']['controller.sh']==sha(D/'src/passwall2-native-r4.3/controller.sh')

assert [x['tool'] for x in cat]==['eee-official','passwall2']
f=json.loads((D/'firmware.json').read_text());assert f['sha256']=='d4f65c9c44d0516a798fcf1b111ed7e8bdb54c9533202d02ac53c35d5e81239c'
assert all(x['tested_firmware']==f['release_url'] for x in cat)
for x in cat:
 p=A/x['tag']/x['file'];assert sha(p)==x['sha256'] and p.stat().st_size==x['bytes'],p
 raw=p.read_bytes()
 if x['tool'].startswith('eee'):
  raw=raw.split(b'\n__MT3600BE_EEE_PAYLOAD__\n',1)[1];archive=base64.b64decode(raw)
  expected={'menu.sh','SHA256SUMS'}|{'patch/'+n for n in ['eee-state','eee-state.c','mt3600be-wan-eee','init','hotplug','install.sh','README.md','SHA256SUMS']}
 else:archive=raw.split(b'# __MT3600BE_ARCHIVE__\n',1)[1];expected=None
 with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as t:
  names=[]
  for m in t.getmembers():
   assert m.isfile() and not m.issym() and not m.islnk(),m.name
   assert '..' not in Path(m.name).parts and not m.name.startswith('/'),m.name
   names.append(m.name)
   if expected is None:
    n=m.name.removeprefix('bundle/');assert m.name.startswith('bundle/')
    allowed={'controller.sh','native-config.sh','fs-safe','uci-plan','apk-db-guard.so','native-uci.so','native-file-modes.tsv','provenance.json','components.txt','packages.json','packages.tsv','files.tsv','services.tsv','defaults.tsv','alternatives.json','target-apk.sha256','target-runtime.tsv','release.ready','SHA256SUMS','default-templates/passwall2','default-templates/passwall2_server','template-files.tsv','keys/mt3600be-passwall2-20261022.pem'}
    assert n in allowed or (n.startswith('repo/') and (n.endswith('.apk') or n=='repo/packages.adb')) or (n.startswith('hooks/') and n.endswith(('.post-install','.post-upgrade','.pre-deinstall'))),n
  if expected is not None:assert set(names)==expected and len(names)==len(expected)
  else:assert len(names)==len(set(names))
 rows.append({'tag':x['tag'],'sha256':sha(p),'bytes':p.stat().st_size,'archive_files':len(names),'archive_allowlist_verified':True})
result={'passed':True,'router_connected':False,'tests':57,'launcher_sha256':sha(D/'install.sh'),'no_credentials_or_router_backups_in_publication':True,'releases':rows}
(D/'tests/publication-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
