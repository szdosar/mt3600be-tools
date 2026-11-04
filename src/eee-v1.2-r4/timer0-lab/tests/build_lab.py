from pathlib import Path
import subprocess,hashlib,json
P=Path(__file__).resolve().parents[1]
K=P/'evidence/actual-driver-functions.c'
body=K.read_text()
shim=r'''
#include <stdint.h>
#include <stdbool.h>
#include <errno.h>
#include <linux/ethtool.h>
typedef uint32_t u32;
#define ethtool_keee ethtool_eee
#define FIELD_GET(mask,x) (((x)&(mask))>>__builtin_ctz(mask))
#define FIELD_PREP(mask,x) (((x)<<__builtin_ctz(mask))&(mask))
#define FIELD_FIT(mask,x) (((x) & ~((mask)>>__builtin_ctz(mask)))==0)
#define DIV_ROUND_UP(x,y) (((x)+(y)-1)/(y))
#define MAC_EEE_LPI_TXIDLE_THD 0xff00u
#define MAC_EEE_WAKEUP_TIME_1000 0xff000000u
#define MAC_EEE_WAKEUP_TIME_100 0xff0000u
#define MAC_EEE_LPI_MODE 1u
#define MAC_MCR_EEE100M 0x40u
#define MAC_MCR_EEE1G 0x80u
#define MTK_MAC_EEECR(id) 0
#define MTK_MAC_MCR(id) 1
struct hw {u32 r[2];unsigned writes;};
struct mtk_mac {struct hw *hw;void *phylink;int id;bool tx_lpi_enabled;u32 txidle_thd_ms;};
struct net_device {struct mtk_mac *mac;};
static struct hw hw;
static struct mtk_mac mac;
static struct net_device dev;
static struct ethtool_eee phy;
static int error_before,error_after,get_error;
#define netdev_priv(d) ((d)->mac)
static int phylink_ethtool_get_eee(void *p,struct ethtool_eee *e){(void)p;if(get_error)return -5;*e=phy;return 0;}
static int phylink_ethtool_set_eee(void *p,struct ethtool_eee *e){(void)p;if(error_before)return -5;phy=*e;phy.advertised=e->eee_enabled?0x28:0;if(error_after)return -5;return 0;}
static u32 mtk_r32(struct hw *h,int reg){return h->r[reg];}
static void mtk_w32(struct hw *h,u32 v,int reg){h->r[reg]=v;h->writes++;}
static void mtk_m32(struct hw *h,u32 clear,u32 set,int reg){h->r[reg]=(h->r[reg]&~clear)|set;h->writes++;}
'''
tail=r'''
void reset(unsigned raw,unsigned timer_cache){hw=(struct hw){.r={raw,0x1200}};mac=(struct mtk_mac){.hw=&hw,.tx_lpi_enabled=true,.txidle_thd_ms=timer_cache};dev.mac=&mac;phy=(struct ethtool_eee){.supported=0x28,.advertised=0x28,.tx_lpi_enabled=1};error_before=error_after=get_error=0;}
unsigned raw(void){return hw.r[0];}
unsigned cache(void){return mac.txidle_thd_ms;}
unsigned writes(void){return hw.writes;}
unsigned adv(void){return phy.advertised;}
void fault(int before,int after,int get){error_before=before;error_after=after;get_error=get;}
int observe(struct ethtool_eee *out){return mtk_get_eee(&dev,out);}
int apply(unsigned enabled,unsigned tx,unsigned timer){struct ethtool_eee e=phy;e.eee_enabled=enabled;e.tx_lpi_enabled=tx;e.tx_lpi_timer=timer;return mtk_set_eee(&dev,&e);}
'''
(P/'tests/driver-lab.c').write_text(shim+body+tail)
subprocess.run(['cc','-Wall','-Wextra','-shared','-fPIC',str(P/'tests/driver-lab.c'),'-o',str(P/'tests/driver-lab.so')],check=True)
# Original synthetic ioctl adapter remains synthetic, not a model of full hardware.
mock=(P/'tests/mock_ioctl_legacy.c').read_text()
mock=mock.replace('if(cmd==ETHTOOL_GEEE)', 'if(cmd==ETHTOOL_GLINK){((struct ethtool_value*)r->ifr_data)->data=getenv("CARRIER")?atoi(getenv("CARRIER")):0;return 0;}\n  if(cmd==ETHTOOL_GEEE)')
(P/'tests/mock_ioctl.c').write_text(mock)
for name,src in [('legacy',P.parent/'legacy/patch-v1/eee-state.c'),('candidate',P.parent/'patch-v1/eee-state.c')]:
 obj=P/'tests'/f'{name}.o';exe=P/'tests'/f'{name}-helper-host'
 subprocess.run(['cc','-Wall','-Wextra','-Dioctl=test_ioctl','-Dsocket=test_socket','-Dfstat=test_fstat','-c',str(src),'-o',str(obj)],check=True)
 subprocess.run(['cc',str(obj),str(P/'tests/mock_ioctl.c'),'-o',str(exe)],check=True)
(P/'results/source-provenance.json').write_text(json.dumps({'source':str(K),'sha256':hashlib.sha256(K.read_bytes()).hexdigest(),'extracted_functions_sha256':hashlib.sha256(body.encode()).hexdigest(),'scope':'Actual reconstructed driver C functions; PHY and register access are synthetic; no hardware'},indent=2)+'\n')
