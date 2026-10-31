/* Only native hook subprocesses: private deltas and durable commit-temp ownership.
 * Keep native UCI export/commit/rename semantics. Never delete a foreign temp. */
#define _GNU_SOURCE
#include <uci.h>
#include <sys/stat.h>
#include <sys/file.h>
#include <dlfcn.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdio.h>
#include <errno.h>
#define NATIVE "/root/mt3600be-passwall2-run-v4/transaction/native"
static int lease=-1;
static int private_dir(const char *p){struct stat s;return !lstat(p,&s)&&S_ISDIR(s.st_mode)&&!s.st_uid&&!s.st_gid&&(s.st_mode&07777)==0700;}
static int scope(void){
 const char *p=getenv("MT3600BE_NATIVE_DELTA");if(!p)return 0;
 if(strcmp(p,NATIVE "/delta")||!private_dir(NATIVE)||!private_dir(p)||!private_dir(NATIVE "/commits")){errno=EPERM;return -1;}
 if(lease<0){
  int fd=open(NATIVE "/commit.lock",O_RDWR|O_NOFOLLOW|O_CLOEXEC);struct stat s;
  if(fd<0)return -1;
  if(fstat(fd,&s)||!S_ISREG(s.st_mode)||s.st_uid||s.st_gid||s.st_nlink!=1||(s.st_mode&07777)!=0600||flock(fd,LOCK_SH|LOCK_NB)){close(fd);errno=EBUSY;return -1;}
  lease=fd;
 }
 return 1;
}
struct uci_context *uci_alloc_context(void){
 struct uci_context *(*alloc)(void)=dlsym(RTLD_NEXT,"uci_alloc_context");
 int (*savedir)(struct uci_context*,const char*)=dlsym(RTLD_NEXT,"uci_set_savedir");
 void (*release)(struct uci_context*)=dlsym(RTLD_NEXT,"uci_free_context");
 if(!alloc||!savedir||!release)return NULL;
 int active=scope();if(active<0)return NULL;
 struct uci_context *c=alloc();if(!c||!active)return c;
 umask(077);c->delta_path.next=c->delta_path.prev=&c->delta_path;
 if(savedir(c,NATIVE "/delta")){release(c);return NULL;}return c;
}
static int syncdir(const char *p){int fd=open(p,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return -1;int rc=fsync(fd);close(fd);return rc;}
int mkstemp(char *template){
 static int (*original)(char*);if(!original)original=dlsym(RTLD_NEXT,"mkstemp");
 if(!original){errno=ENOSYS;return -1;}
 const char *env=getenv("MT3600BE_NATIVE_DELTA");
 if(!env||strncmp(template,"/etc/config/.",13))return original(template);
 int active=scope();if(active!=1){errno=EPERM;return -1;}
 const char *names[]={"dhcp","firewall","uhttpd","ucitrack","luci","passwall2","passwall2_server",NULL};
 const char *name=NULL;char want[128];
 for(int i=0;names[i];i++){snprintf(want,sizeof want,"/etc/config/.%s.uci-XXXXXX",names[i]);if(!strcmp(template,want)){name=names[i];break;}}
 if(!name){errno=EPERM;return -1;}
 char dir[256],data[280];snprintf(dir,sizeof dir,NATIVE "/commits/%s.XXXXXX",name);
 if(!mkdtemp(dir))return -1;
 snprintf(data,sizeof data,"%s/data",dir);
 int fd=open(data,O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(fd<0)return -1;
 /* The private inode is durable BEFORE its public alias can exist. Directory
  * name fixes the one permitted alias, so no post-creation journal gap exists. */
 if(fsync(fd)||syncdir(dir)||syncdir(NATIVE "/commits"))goto error;
 memcpy(template+strlen(template)-6,dir+strlen(dir)-6,6);
 if(link(data,template))goto error; /* EXDEV/EEXIST: refuse, never copy/replace. */
 if(syncdir("/etc/config"))goto error;
 return fd;
error:{int e=errno;close(fd);errno=e;return -1;} /* recovery owns cleanup */
}
