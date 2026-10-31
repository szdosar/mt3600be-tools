#!/usr/bin/env python3
"""Real ARM Lua generator and Xray test with only synthetic nodes, no network."""
from pathlib import Path
import argparse,json,shutil,subprocess,tempfile,hashlib
p=argparse.ArgumentParser();p.add_argument('--payload',type=Path,required=True);p.add_argument('--public-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
A='/home/dosar/immortalwrt/staging_dir/host/bin/apk'
def run(cmd):
 q=subprocess.run(list(map(str,cmd)),capture_output=True,text=True,timeout=90)
 if q.returncode:raise RuntimeError(q.stdout+q.stderr)
 return q.stdout
with tempfile.TemporaryDirectory(prefix='pw261020-native-') as d:
 root=Path(d)/'root';shutil.copytree(a.public_root,root,symlinks=True)
 lu=Path('/home/dosar/Projects/openclaw/work/mt3600be-v11-luci-repair-r4-candidate03/kits/luci-bootstrap');pw=a.payload
 common=[A,'--root',root,'--arch','aarch64_cortex-a53','--no-network','--repositories-file','/dev/null','--keys-dir',lu/'keys','add','--no-scripts','--no-commit-hooks','--usermode']
 run(common+[lu/r['file'] for r in json.loads((lu/'manifest.json').read_text())])
 run([A,'--root',root,'--arch','aarch64_cortex-a53','--no-network','--repositories-file','/dev/null','--keys-dir',pw/'keys','add','--no-scripts','--no-commit-hooks','--usermode',*[pw/r['file'] for r in json.loads((pw/'packages.json').read_text())]])
 (root/'etc/config/luci').write_text("config core 'main'\n option lang 'auto'\n option mediaurlbase '/luci-static/bootstrap'\n")
 (root/'etc/config/passwall2').write_text("""config global 'main'
 option enabled '0'
 option node 'fixture'
config global_app
 option xray_file '/usr/bin/xray'
config global_rules
 option v2ray_location_asset '/usr/share/v2ray/'
config nodes 'fixture'
 option remarks 'synthetic fixture'
 option type 'Xray'
 option protocol 'vless'
 option address '192.0.2.1'
 option port '443'
 option uuid '00000000-0000-0000-0000-000000000001'
 option tls '1'
 option tls_serverName 'example.com'
 option transport 'raw'
 option encryption 'none'
""")
 (root/'tmp/etc/passwall2').mkdir(parents=True,exist_ok=True)
 prefix=['bwrap','--unshare-all','--uid','0','--gid','0','--die-with-parent','--bind',root,'/','--ro-bind','/usr/bin/qemu-aarch64-static','/bin/qemu','--dev','/dev','--proc','/proc','--chdir','/']
 # No router ubus daemon exists here. Use the real native libuci-lua cursor
 # against the same synthetic files, adapting transport only, not the generator.
 (root/'tmp/generate.lua').write_text('luci=luci or {};luci.model=luci.model or {};luci.model.uci=require("uci");package.loaded["luci.model.uci"]=luci.model.uci;dofile("/usr/lib/lua/luci/passwall2/util_xray.lua")\n')
 options={'node':'fixture','no_run':'1','flag':'fixture','local_socks_address':'127.0.0.1','local_socks_port':'61080','dns_listen_port':'61081','direct_dns_udp_server':'192.0.2.53','direct_dns_udp_port':'53'}
 cmd=prefix+['/bin/qemu','-L','/','/usr/bin/lua5.1','/tmp/generate.lua','gen_config']+[json.dumps(options)]
 text=run(cmd);config=json.loads(text);assert 'inbounds' in config and 'outbounds' in config
 (root/'tmp/fixture.json').write_text(text)
 output=run(prefix+['/bin/qemu','-L','/','/usr/bin/xray','run','-test','-c','/tmp/fixture.json'])
 assert 'Configuration OK' in output,output
 def count(t,k):return sum((n==k)+count(v,k) for n,v in t.items()) if isinstance(t,dict) else sum(count(v,k) for v in t) if isinstance(t,list) else 0
 assert any(o.get('protocol')=='vless' for o in config['outbounds'])
 result={'passed':True,'tests_run':1,'real_ARM_Lua_generator':True,'real_ARM_Xray_version':run(prefix+['/bin/qemu','-L','/','/usr/bin/xray','version']).splitlines()[0],'UCI_transport_adapter':'native libuci-lua; no ubus daemon','native_generated_config_accepted':True,'proxySettings_count':count(config,'proxySettings'),'no_network_or_router_or_VM':True,'synthetic_nodes_only':True,'generator_sha256':hashlib.sha256((root/'usr/lib/lua/luci/passwall2/util_xray.lua').read_bytes()).hexdigest()}
a.report.write_text(json.dumps(result,indent=2)+'\n')
