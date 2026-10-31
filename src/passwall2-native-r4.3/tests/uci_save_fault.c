#define _GNU_SOURCE
#include <dlfcn.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
int uci_save(void *c,void *p){
 static int (*real_save)(void*,void*);if(!real_save)real_save=dlsym(RTLD_NEXT,"uci_save");
 int r=real_save(c,p);
 if(!r&&getenv("MT3600BE_NATIVE_DELTA")&&access("/fixture/after-native-firewall",F_OK)==0){int f=open("/fixture/barrier",O_CREAT|O_WRONLY,0600);if(f>=0)close(f);while(access("/fixture/after-native-firewall",F_OK)==0)usleep(50000);}
 return r;
}
