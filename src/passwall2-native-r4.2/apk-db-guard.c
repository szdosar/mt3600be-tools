/* Scoped to the frozen dynamic apk executable, never installed system-wide.
 * Validate the preflight baseline after apk obtains its own exclusive lock.
 * No package scripts, hooks, database writes, or lock bypasses are added. */
#define _GNU_SOURCE
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <dlfcn.h>
#include <unistd.h>
#include <stdlib.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <stdio.h>
static int guarded=0,preserve_server=0;

__attribute__((constructor)) static void isolate_native_hooks(void) {
 if(getenv("MT3600BE_APK_BASELINE")) {int f=fcntl(9,F_GETFD);if(f>=0)fcntl(9,F_SETFD,f|FD_CLOEXEC);}
}
static int (*native_flock)(int,int);
int flock(int fd,int operation) {
 struct stat a,b; pid_t child; int status;
 if (!native_flock) native_flock=dlsym(RTLD_NEXT,"flock");
 if (!native_flock) { errno=ENOSYS;return -1; }
 int rc=native_flock(fd,operation);
 if (rc || !(operation&LOCK_EX)) return rc;
 if (fstat(fd,&a) || stat("/lib/apk/db/lock",&b)) { errno=EIO;return -1; }
 if (a.st_dev!=b.st_dev || a.st_ino!=b.st_ino) return rc;
 const char *manifest=getenv("MT3600BE_APK_BASELINE");
 const char *receipt=getenv("MT3600BE_APK_LOCK_RECEIPT");
 if (!manifest || !receipt || strncmp(manifest,"/root/mt3600be-passwall2-run-v4/",sizeof("/root/mt3600be-passwall2-run-v4/")-1) ||
     lstat(manifest,&a) || !S_ISREG(a.st_mode) || a.st_uid || (a.st_mode&0777)!=0600) goto refuse;
 child=fork();
 if (child==0) {
  unsetenv("LD_PRELOAD");
  unsetenv("MT3600BE_NATIVE_DELTA");
  int clean=system("p=$(uci changes) || exit 1; [ -z \"$p\" ]");
  if(clean!=0)_exit(125);
  execl("/bin/busybox","busybox","sha256sum","-c",manifest,(char*)0);
  _exit(126);
 }
 if (child<0) goto refuse;
 do { rc=waitpid(child,&status,0); } while(rc<0 && errno==EINTR);
 if (rc!=child || !WIFEXITED(status) || WEXITSTATUS(status)) goto refuse;
 int marker=open(receipt,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
 if(marker<0) goto refuse;
 if(write(marker,"locked-and-checked\n",19)!=19 || fsync(marker)) { close(marker);goto refuse; }
 close(marker);
 /* Preserve only the two enumerated user configs recorded by this transaction.
  * APK still owns package metadata; uninstall must not erase restored defaults. */
 const char *list="/root/mt3600be-passwall2-run-v4/transaction/retained-files";
 int keep=open(list,O_RDONLY|O_NOFOLLOW);struct stat st;
 if(keep<0||fstat(keep,&st)||!S_ISREG(st.st_mode)||st.st_uid||st.st_gid||(st.st_mode&07777)!=0600||st.st_nlink!=1)goto refuse;
 FILE *fp=fdopen(keep,"r");if(!fp){close(keep);goto refuse;}
 char line[256];int seen=0;
 while(fgets(line,sizeof line,fp)){
  if(!strcmp(line,"/etc/config/passwall2_server\n")){if(preserve_server){fclose(fp);goto refuse;}preserve_server=1;}
  else if(!strcmp(line,"/etc/config/passwall2\n")){if(seen++){fclose(fp);goto refuse;}}
  else{fclose(fp);goto refuse;}
 }
 if(ferror(fp)){fclose(fp);goto refuse;}fclose(fp);guarded=1;return 0;
refuse:
 const char *message="mt3600be: APK baseline changed or guard failed; refusing before mutation\n";
 if (write(2,message,strlen(message))<0) errno=EIO;
 errno=ESTALE;return -1;
}

/* APK fs_fsys uses unlinkat(rootfd, "etc/config/passwall2_server", 0).
 * Match the actual parent inode too; an identically named unrelated file is not protected.
 * This guard exists only in the locked APK process, never system-wide. */
int unlinkat(int dirfd,const char *path,int flags){
 static int (*original)(int,const char*,int);if(!original)original=dlsym(RTLD_NEXT,"unlinkat");
 if(!original){errno=ENOSYS;return -1;}
 if(guarded&&preserve_server&&!flags&&(!strcmp(path,"etc/config/passwall2_server")||!strcmp(path,"/etc/config/passwall2_server")||!strcmp(path,"passwall2_server"))){
  struct stat a,b;
  const char *parent=!strcmp(path,"passwall2_server")?".":!strcmp(path,"/etc/config/passwall2_server")?"/etc/config":"etc/config";
  if(!fstatat(dirfd,parent,&a,AT_SYMLINK_NOFOLLOW)&&!lstat("/etc/config",&b)&&S_ISDIR(a.st_mode)&&a.st_dev==b.st_dev&&a.st_ino==b.st_ino){
   if(fstatat(dirfd,path,&a,AT_SYMLINK_NOFOLLOW)){if(errno==ENOENT)return 0;return -1;}
   if(!S_ISREG(a.st_mode)||a.st_nlink!=1){errno=EPERM;return -1;}
   return 0;
  }
 }
 return original(dirfd,path,flags);
}
