#define _GNU_SOURCE
#include <dlfcn.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
/* Fixture-only fault after deletion of an actual package file, before DB commit. */
static int (*real_unlinkat)(int,const char*,int);
int unlinkat(int d,const char *p,int flags){
 if(!real_unlinkat)real_unlinkat=dlsym(RTLD_NEXT,"unlinkat");
 int r=real_unlinkat(d,p,flags);
 if(!r&&(!strcmp(p,"xray")||!strcmp(p,"usr/bin/xray")||!strcmp(p,"/usr/bin/xray"))&&access("/fixture/after-native-unlink",F_OK)==0){
  int f=open("/fixture/barrier",O_CREAT|O_WRONLY,0600);if(f>=0)close(f);
  while(access("/fixture/after-native-unlink",F_OK)==0)usleep(50000);
 }
 return r;
}

static int (*real_rename)(const char*,const char*);
int rename(const char *a,const char *b){
 if(!real_rename)real_rename=dlsym(RTLD_NEXT,"rename");
 if(strstr(b,"/transaction/phase")&&access("/fixture/phase-record-barrier",F_OK)==0){
  int f=open("/fixture/barrier",O_CREAT|O_WRONLY,0600);if(f>=0)close(f);
  while(access("/fixture/phase-record-barrier",F_OK)==0)usleep(50000);
 }
 return real_rename(a,b);
}
