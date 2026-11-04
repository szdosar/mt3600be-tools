#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <ctype.h>
#include <net/if.h>
#include <linux/ethtool.h>
#include <linux/sockios.h>
#include <linux/mii.h>
struct saved { uint32_t magic; struct ethtool_eee e; uint16_t adv; };
static int fd;
static void fail(const char *s){perror(s);exit(1);}
static void eth(void *p){struct ifreq r={0};strcpy(r.ifr_name,"eth0");r.ifr_data=p;if(ioctl(fd,SIOCETHTOOL,&r)<0)fail("ethtool ioctl");}
static unsigned mii(unsigned cmd,unsigned value){struct ifreq r={0};strcpy(r.ifr_name,"eth0");struct mii_ioctl_data *m=(void *)&r.ifr_ifru; m->phy_id=0x8000|(7<<5)|7;m->reg_num=0x3c;m->val_in=value;if(ioctl(fd,cmd,&r)<0)fail("EEE advertisement ioctl");return m->val_out;}
static void show(struct saved *s){printf("eee_enabled=%u eee_active=%u tx_lpi_enabled=%u tx_lpi_timer=%u supported=0x%x advertised=0x%x lp_advertised=0x%x phy7_mmd7_003c=0x%04x\n",s->e.eee_enabled,s->e.eee_active,s->e.tx_lpi_enabled,s->e.tx_lpi_timer,s->e.supported,s->e.advertised,s->e.lp_advertised,s->adv);}
static struct saved readstate(void){struct saved s={0};s.magic=0x45454531;s.e.cmd=ETHTOOL_GEEE;eth(&s.e);s.adv=mii(SIOCGMIIREG,0);return s;}
static int valid(const struct saved *s){
 if(s->magic!=0x45454531)return 3;
 if(s->e.eee_enabled>1||s->e.tx_lpi_enabled>1||s->e.tx_lpi_timer!=1000||(s->adv!=0 && s->adv!=6)||s->e.advertised!=(s->adv==6?0x28:0))return 4;
 return 0;
}
/* Hash exactly the in-memory snapshot that will be restored. */
static int verify_digest(const void *data,size_t n,const char *expected){
 int in[2],out[2],status;char result[96];ssize_t got=0,r;pid_t pid;
 if(strlen(expected)!=64)return 0;
 for(size_t i=0;i<64;i++)if(!isdigit((unsigned char)expected[i]) && !(expected[i]>='a' && expected[i]<='f'))return 0;
 if(pipe(in)<0)return 0;
 if(pipe(out)<0){close(in[0]);close(in[1]);return 0;}
 pid=fork();if(pid<0){close(in[0]);close(in[1]);close(out[0]);close(out[1]);return 0;}
 if(pid==0){dup2(in[0],STDIN_FILENO);dup2(out[1],STDOUT_FILENO);close(in[0]);close(in[1]);close(out[0]);close(out[1]);execlp("sha256sum","sha256sum",(char *)NULL);_exit(127);}
 close(in[0]);close(out[1]);
 ssize_t sent=write(in[1],data,n);close(in[1]);
 while(got<(ssize_t)sizeof(result) && (r=read(out[0],result+got,sizeof(result)-got))>0)got+=r;
 close(out[0]);if(waitpid(pid,&status,0)!=pid)return 0;
 return sent==(ssize_t)n && WIFEXITED(status) && WEXITSTATUS(status)==0 && got==68 && !memcmp(result,expected,64) && !memcmp(result+64,"  -\n",4);
}
static int restore_state(struct saved *s){
 struct ethtool_eee e=s->e;e.cmd=ETHTOOL_SEEE;eth(&e);
 if(mii(SIOCGMIIREG,0)!=s->adv){mii(SIOCSMIIREG,s->adv);if(mii(SIOCGMIIREG,0)!=s->adv)return 5;struct ethtool_value v={.cmd=ETHTOOL_NWAY_RST};eth(&v);}
 struct saved now=readstate();show(&now);if(now.e.eee_enabled!=s->e.eee_enabled||now.e.tx_lpi_enabled!=s->e.tx_lpi_enabled||now.e.tx_lpi_timer!=s->e.tx_lpi_timer||now.e.advertised!=s->e.advertised||now.adv!=s->adv)return 6;return 0;
}
int main(int ac,char **av){if(ac<2)return 2;
 /* rename(2) never falls back to copying if the state is a mount point. */
 if(ac==4 && !strcmp(av[1],"archive")){
  struct stat src,dst;
  if(lstat(av[2],&src)<0||!S_ISDIR(src.st_mode))return 3;
  if(lstat(av[3],&dst)==0||errno!=ENOENT)return 3;
  if(rename(av[2],av[3])<0)fail("archive rename");
  return 0;
 }
 if(ac==4 && !strcmp(av[1],"import")){
  struct saved s={0};struct stat before,after;int rc;
  int in=open(av[2],O_RDONLY|O_NOFOLLOW|O_NONBLOCK);
  if(in<0)fail("snapshot open");
  if(fstat(in,&before)<0||!S_ISREG(before.st_mode)||before.st_size!=sizeof(s)||before.st_uid!=0||(before.st_mode&077)){close(in);return 3;}
  if(read(in,&s,sizeof(s))!=sizeof(s)||fstat(in,&after)<0){close(in);return 3;}
  close(in);
  if(before.st_dev!=after.st_dev||before.st_ino!=after.st_ino||before.st_size!=after.st_size||
     before.st_mtim.tv_sec!=after.st_mtim.tv_sec||before.st_mtim.tv_nsec!=after.st_mtim.tv_nsec||
     before.st_ctim.tv_sec!=after.st_ctim.tv_sec||before.st_ctim.tv_nsec!=after.st_ctim.tv_nsec)return 3;
  rc=valid(&s);if(rc)return rc;
  int out=open(av[3],O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
  if(out<0)fail("snapshot destination open");
  if(write(out,&s,sizeof(s))!=sizeof(s)||fsync(out)<0)fail("snapshot destination write");
  if(close(out)<0)fail("snapshot destination close");
  show(&s);return 0;
 }
 if(ac==4 && !strcmp(av[1],"restore-checked")){
  struct saved s={0};struct stat st;int in=open(av[2],O_RDONLY|O_NOFOLLOW|O_NONBLOCK),rc;
  if(in<0)fail("snapshot open");
  if(fstat(in,&st)<0||!S_ISREG(st.st_mode)||st.st_size!=sizeof(s)||st.st_uid!=0||(st.st_mode&077)){close(in);return 3;}
  if(read(in,&s,sizeof(s))!=sizeof(s)){close(in);return 3;}close(in);
  rc=valid(&s);if(rc)return rc;
  if(!verify_digest(&s,sizeof(s),av[3])){fprintf(stderr,"snapshot digest mismatch or hash failed\n");return 8;}
  fd=socket(AF_INET,SOCK_DGRAM,0);if(fd<0)fail("socket");
  return restore_state(&s);
 }
 fd=socket(AF_INET,SOCK_DGRAM,0);if(fd<0)fail("socket");
 if(!strcmp(av[1],"read")){struct saved s=readstate();show(&s);return 0;}
 /* Offline candidate: assess is read-only; zero has NOT been authorized for writes. */
 if(!strcmp(av[1],"assess")){
  struct saved s=readstate();struct ethtool_value link={.cmd=ETHTOOL_GLINK};int rc=valid(&s);
  show(&s);eth(&link);printf("carrier=%u\n",!!link.data);
  if(s.e.tx_lpi_timer==0){fprintf(stderr,"timer=0 原样恢复尚未验证，未写入；请接通 WAN 后重新查询，不能强改或重写旧快照。\n");return 4;}
  if(rc){fprintf(stderr,"unsupported baseline; no write.\n");return rc;}
  puts("timer=1000 范围检查通过；未写硬件。");return 0;
 }
 if(!strcmp(av[1],"disable")){struct saved s=readstate();int rc=valid(&s);if(rc){show(&s);fprintf(stderr,"Current EEE state outside validated write profile; no write.\n");return rc;}s.e.cmd=ETHTOOL_SEEE;s.e.eee_enabled=0;s.e.tx_lpi_enabled=0;eth(&s.e);s=readstate();show(&s);return s.adv==0 && s.e.advertised==0 && s.e.eee_enabled==0 && s.e.tx_lpi_enabled==0 ? 0 : 7;}
 if(ac!=3)return 2;
 if(!strcmp(av[1],"save")){struct saved s=readstate();int f=open(av[2],O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(f<0)fail("save open");if(write(f,&s,sizeof(s))!=sizeof(s)||fsync(f)<0)fail("save write");close(f);show(&s);return 0;}
 if(strcmp(av[1],"validate"))return 2;
 struct saved s={0};int f=open(av[2],O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(f<0)fail("validate open");struct stat st;if(fstat(f,&st)<0||!S_ISREG(st.st_mode)||st.st_size!=sizeof(s)||st.st_uid!=0||(st.st_mode&077))return 3;if(read(f,&s,sizeof(s))!=sizeof(s))return 3;close(f);
 int rc=valid(&s);if(rc)return rc;show(&s);return 0;}
