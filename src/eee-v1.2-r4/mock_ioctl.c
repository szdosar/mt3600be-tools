#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stdarg.h>
#include <signal.h>
#include <sys/stat.h>
#include <net/if.h>
#include <linux/ethtool.h>
#include <linux/sockios.h>
#include <linux/mii.h>
struct saved {uint32_t magic;struct ethtool_eee e;uint16_t adv;};
struct model {struct saved s;unsigned pending;unsigned restarts;};
static struct model m;
static void load(void){FILE*f=fopen(getenv("MODEL"),"rb");if(!f||fread(&m,sizeof(m),1,f)!=1)exit(90);fclose(f);}
static void save(const char*point){FILE*f=fopen(getenv("MODEL"),"wb");if(!f||fwrite(&m,sizeof(m),1,f)!=1)exit(91);fclose(f);if(getenv("CRASH")&&!strcmp(getenv("CRASH"),point))raise(SIGKILL);}
int test_fstat(int fd,struct stat *s){int r=fstat(fd,s);if(!r)s->st_uid=0;return r;}
int test_ioctl(int fd,unsigned long req,...){(void)fd;va_list ap;va_start(ap,req);struct ifreq*r=va_arg(ap,struct ifreq*);va_end(ap);load();
 if(strcmp(r->ifr_name,"eth0"))exit(92);
 if(req==SIOCETHTOOL){unsigned cmd=*(unsigned*)r->ifr_data;
  if(cmd==ETHTOOL_GLINK){((struct ethtool_value*)r->ifr_data)->data=1;return 0;}
  if(cmd==ETHTOOL_GEEE){*(struct ethtool_eee*)r->ifr_data=m.s.e;return 0;}
  if(cmd==ETHTOOL_SEEE){struct ethtool_eee*e=(void*)r->ifr_data; m.s.e=*e;m.s.e.cmd=ETHTOOL_GEEE;m.s.adv=e->eee_enabled?6:0;m.s.e.advertised=m.s.adv?0x28:0;m.s.e.eee_active=m.s.adv?1:0;m.pending=0;save("after-seteee");return 0;}
  if(cmd==ETHTOOL_NWAY_RST){m.pending=0;m.restarts++;m.s.e.eee_active=m.s.adv?1:0;save("after-nway");return 0;}
 }else{struct mii_ioctl_data*a=(void*)&r->ifr_ifru;if(a->phy_id!=(0x8000|(7<<5)|7)||a->reg_num!=0x3c)exit(93);
  if(req==SIOCGMIIREG){a->val_out=m.s.adv;return 0;}
  if(req==SIOCSMIIREG){m.s.adv=a->val_in;m.s.e.advertised=m.s.adv?0x28:0;m.pending=1;save("after-miiwrite");return 0;}
 }
 exit(94);
}

int test_socket(int a,int b,int c){(void)a;(void)b;(void)c;return 123;}
