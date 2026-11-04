from pathlib import Path
import subprocess,sys,os,json,hashlib
P=Path(__file__).resolve().parent
out=P/'results/release-ready.json';out.unlink(missing_ok=True)
steps=[('regression',[sys.executable,str(P/'run_tests.py')],{}),('timer0-build',[sys.executable,str(P/'timer0-lab/tests/build_lab.py')],{}),('timer0-tests',[sys.executable,str(P/'timer0-lab/tests/test_timer0.py')],{}),('r4-tests',[sys.executable,str(P/'test_r4.py')],{}),('r3-compat',[sys.executable,str(P/'test-review-r2.py')],{'EEE_LEGACY_SOURCE':str(P/'legacy/patch-v1')}),('r3-rollback',[sys.executable,str(P/'test-rollback-r3.py')],{'EEE_LEGACY_SOURCE':str(P/'legacy/patch-v1')})]
for name,args,env in steps:
 with (P/'results'/(name+'.log')).open('w') as f:subprocess.run(args,cwd=P,env=dict(os.environ,**env),stdout=f,stderr=subprocess.STDOUT,check=True)
 print('PASS',name,flush=True)
for group,n in [('timer0-lab/results/timer0-tests.json',36),('results/r4-tests.json',7)]:
 r=json.loads((P/group).read_text());assert r['passed'] and r['tests']==n
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
artifact=P/'release/mt3600be-eee-tool-v1.2-r4.run'
r={'release':'eee-v1.2-r4','passed':True,'router_connected':False,'zero_timer_write_enabled':False,'existing_checks':69,'existing_specialized_tests':16,'timer0_tests':36,'r3_compat_and_rollback_tests':9,'new_recovery_and_ARM_tests':7,'artifact':{'sha256':sha(artifact),'bytes':artifact.stat().st_size},'source_sha256':{str(f.relative_to(P)):sha(f) for f in [P/'tool/menu.sh',*sorted(x for x in (P/'patch-v1').iterdir() if x.name!='eee-state')]},'live_evidence_version':'v1.2-r3 on 2026-11-04; r4 not live-tested'}
out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('RELEASE GATE PASS')
