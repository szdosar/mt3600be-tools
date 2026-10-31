from native_fixture import *
import unittest,concurrent.futures
from test_native import Tests
from test_recovery_v2 import Recovery
from test_transaction_v3 import Transaction
from test_retained_v4 import Retained
from test_predecessor_v4_1 import Predecessor
from test_retained_v4_2 import Restored42
from test_empty_v4_3 import Empty43
source={p.name:sha(p) for p in S.iterdir() if p.is_file() and p.suffix in ['.sh','.c']}
tests={p.name:sha(p) for p in (S/'tests').iterdir() if p.is_file() and p.suffix in ['.py','.c']}
cases=[t for c in [Tests,Recovery,Transaction,Retained,Predecessor,Restored42,Empty43] for t in unittest.defaultTestLoader.loadTestsFromTestCase(c)]
def execute(t):
 r=unittest.TestResult();t.run(r)
 return {'case':t.id(),'passed':r.wasSuccessful(),'failures':r.failures,'errors':r.errors}
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
 jobs=[ex.submit(execute,t) for t in cases]
 for fut in concurrent.futures.as_completed(jobs):
  r=fut.result();rows.append(r);print(r['case'], 'PASS' if r['passed'] else 'FAIL',flush=True)
  for _,why in r['failures']+r['errors']:print(why,flush=True)
assert source=={p.name:sha(p) for p in S.iterdir() if p.is_file() and p.suffix in ['.sh','.c']}
assert tests=={p.name:sha(p) for p in (S/'tests').iterdir() if p.is_file() and p.suffix in ['.py','.c']}
obj={'passed':all(x['passed'] for x in rows),'tests_run':len(rows),'failures':sum(len(x['failures']) for x in rows),'errors':sum(len(x['errors']) for x in rows),'cases':sorted(x['case'] for x in rows),'source_sha256':source,'test_source_sha256':tests,'payload_packages_sha256':sha(PAYLOAD/'packages.json'),'real_signed_APKs':True,'native_package_hooks':True,'network_isolated':True,'real_ARM_UCI':True,'services':'fixtures; no procd/kernel traffic acceptance','no_router_or_VM':True,'parallel_independent_roots':2}
(W/'mt3600be-run-native-high-r4.3-20261031/native-tests.json').write_text(json.dumps(obj,indent=2)+'\n')
print('SUMMARY',obj['tests_run'],obj['failures'],obj['errors'],flush=True)
raise SystemExit(0 if obj['passed'] else 1)
