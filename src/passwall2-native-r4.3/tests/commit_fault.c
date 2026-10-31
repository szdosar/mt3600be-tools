#define _GNU_SOURCE
#include <dlfcn.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
static void pause_at(const char *flag){if(access(flag,F_OK))return;int fd=open("/fixture/barrier",O_CREAT|O_WRONLY,0600);if(fd>=0)close(fd);while(!access(flag,F_OK))usleep(25000);}
int rename(const char *a,const char *b){static int(*fn)(const char*,const char*);if(!fn)fn=dlsym(RTLD_NEXT,"rename");if(getenv("MT3600BE_NATIVE_DELTA")&&!strcmp(b,"/etc/config/firewall"))pause_at("/fixture/pause-rename");return fn(a,b);}
int link(const char *a,const char *b){static int(*fn)(const char*,const char*);if(!fn)fn=dlsym(RTLD_NEXT,"link");int target=getenv("MT3600BE_NATIVE_DELTA")&&!strncmp(b,"/etc/config/.firewall.uci-",26);if(target)pause_at("/fixture/pause-before-link");int rc=fn(a,b);if(!rc&&target)pause_at("/fixture/pause-after-link");return rc;}
int unlink(const char *p){static int(*fn)(const char*);if(!fn)fn=dlsym(RTLD_NEXT,"unlink");int rc=fn(p);if(!rc&&!strncmp(p,"/etc/config/.firewall.uci-",26))pause_at("/fixture/pause-clean");return rc;}
int fsync(int fd){static int(*fn)(int);if(!fn)fn=dlsym(RTLD_NEXT,"fsync");int rc=fn(fd);char path[64],target[512];snprintf(path,sizeof path,"/proc/self/fd/%d",fd);ssize_t n=readlink(path,target,sizeof target-1);if(n>0){target[n]=0;if(strstr(target,"/native/before/firewall"))pause_at("/fixture/pause-snapshot");}return rc;}
