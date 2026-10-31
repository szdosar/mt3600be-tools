/* Test-only injection: never included in the delivered run archive. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
static int (*real_rename)(const char*,const char*);
int rename(const char *a,const char *b){
 if(!real_rename)real_rename=dlsym(RTLD_NEXT,"rename");
 int r=real_rename(a,b);
 if(!r&&!strcmp(b,"/etc/config/firewall")&&access("/fixture/after-native-firewall",F_OK)==0){
  int f=open("/fixture/barrier",O_CREAT|O_WRONLY,0600);if(f>=0)close(f);
  while(access("/fixture/after-native-firewall",F_OK)==0)usleep(50000);
 }
 return r;
}
