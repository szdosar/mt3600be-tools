#!/usr/bin/env python3
from pathlib import Path
import argparse,subprocess,tempfile,hashlib,json,time,os,signal,runpy
p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
cases=[]
def invoke(f,*args):return subprocess.run(['sh',str(f),*args],capture_output=True,text=True,timeout=60)
def dirs():return set(Path('/tmp').glob('mt3600be-pw-native.*'))
before=dirs();assert invoke(a.run,'--check').returncode==0;assert dirs()==before;cases.append('valid envelope and cleanup')
with tempfile.TemporaryDirectory(prefix='pw-envelope-') as d:
 d=Path(d);b=a.run.read_bytes()
 for label,content in [('truncated',b[:-170]),('tampered',b[:-1]+bytes([b[-1]^1]))]:
  f=d/(label+'.run');f.write_bytes(content);assert invoke(f,'--check').returncode!=0;assert dirs()==before;cases.append(label+' refused and cleaned')
 # Header syntax is checked without interpreting the appended binary tar data.
 header=b.split(b'# __MT3600BE_ARCHIVE__\n',1)[0];f=d/'header.sh';f.write_bytes(header);assert subprocess.run(['sh','-n',str(f)],capture_output=True).returncode==0;cases.append('header syntax')
 assert invoke(a.run,'install').returncode==2;cases.append('missing explicit apply refused')
 jobs=[subprocess.Popen(['sh',str(a.run),'--check'],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
 for j in jobs:j.communicate(timeout=60);assert j.returncode==0
 assert dirs()==before;cases.append('parallel private extraction isolation')
 j=subprocess.Popen(['sh',str(a.run),'--check'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 for _ in range(1000):
  if dirs()-before:break
  assert j.poll() is None,'test did not reach interrupt window';time.sleep(.001)
 j.send_signal(signal.SIGTERM);j.communicate(timeout=60);assert j.returncode!=0;assert dirs()==before;cases.append('TERM cleanup')
 assert invoke(a.run,'--check').returncode==0;assert dirs()==before;cases.append('retry after interruption')
 # Release gate must reject failed or stale tests without creating an output.
 S=Path(__file__).resolve().parents[1];packer=runpy.run_path(str(S/'pack_run.py'))['pack'];payload=a.report.parent/'payload01'
 for label,obj in [('failed',{'passed':False}),('incomplete',{'passed':True,'failures':0,'errors':0,'tests_run':0})]:
  r=d/(label+'.json');r.write_text(json.dumps(obj));out=d/(label+'.run')
  try:packer(payload,out,r)
  except (AssertionError,KeyError):pass
  else:raise AssertionError('release gate accepted bad tests')
  assert not out.exists();cases.append('publish fails closed: '+label)
result={'passed':True,'tests_run':len(cases),'cases':cases,'artifact_sha256':hashlib.sha256(a.run.read_bytes()).hexdigest(),'no_router':True}
a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
