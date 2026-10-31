/* Local helper: strict metadata and atomic state writes, never mv copy fallback. */
#define _GNU_SOURCE
#include <sys/stat.h>
#include <sys/file.h>
#include <dirent.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <linux/fs.h>
static void die(void) { perror("fs-safe"); exit(1); }
static void sync_parent(const char *p) {
 char *b=strdup(p), *s=strrchr(b,'/'); if(!s) exit(2); *s=0;
 int fd=open(*b?b:"/",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
 if(fd<0 || fsync(fd)) die();
 close(fd); free(b);
}
/* Hash an already-open inode, not a second path lookup. */
static void verify_target(int fd,const char *digest,const char *metadata) {
 struct stat st;char actual[96];
 if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_nlink!=1)die();
 snprintf(actual,sizeof actual,"%u:%u:%o:f",st.st_uid,st.st_gid,st.st_mode&07777);
 if(strcmp(actual,metadata)){errno=ESTALE;die();}
 int pp[2];if(pipe(pp))die();pid_t pid=fork();if(pid<0)die();
 if(!pid){char path[64];close(pp[0]);if(dup2(pp[1],1)<0)_exit(126);close(pp[1]);snprintf(path,sizeof path,"/proc/self/fd/%d",fd);execl("/bin/busybox","busybox","sha256sum",path,(char*)0);_exit(127);}
 close(pp[1]);char result[512];size_t n=0;ssize_t nr;
 while(n<sizeof result-1&&(nr=read(pp[0],result+n,sizeof result-1-n))>0)n+=nr;
 close(pp[0]);result[n]=0;int rc;while(waitpid(pid,&rc,0)<0)if(errno!=EINTR)die();
 if(!WIFEXITED(rc)||WEXITSTATUS(rc)||strlen(digest)!=64||n<65||memcmp(result,digest,64)||result[64]!=' '){errno=ESTALE;die();}
}
/* Native libuci holds flock while preparing .<name>.uci-* and only then
 * unlocks before its rename. Refuse a prepared writer rather than race it. */
static void no_pending_commit(const char *path) {
 char *dir=strdup(path),*base=strrchr(dir,'/');if(!base)exit(2);*base++=0;
 char prefix[256];if(snprintf(prefix,sizeof prefix,".%s.uci-",base)>=(int)sizeof prefix)exit(2);
 DIR *d=opendir(dir);if(!d)die();struct dirent *e;
 while((e=readdir(d))){if(!strncmp(e->d_name,prefix,strlen(prefix))){closedir(d);free(dir);errno=EBUSY;die();}}
 closedir(d);free(dir);
}
static void sync_tree(int fd) {
 DIR *d=fdopendir(dup(fd));if(!d)die();struct dirent *e;
 while((e=readdir(d))){
  if(!strcmp(e->d_name,".")||!strcmp(e->d_name,".."))continue;
  struct stat st;if(fstatat(fd,e->d_name,&st,AT_SYMLINK_NOFOLLOW))die();
  if(!S_ISREG(st.st_mode)&&!S_ISDIR(st.st_mode)){errno=EINVAL;die();}
  int child=openat(fd,e->d_name,O_RDONLY|O_NOFOLLOW|(S_ISDIR(st.st_mode)?O_DIRECTORY:0));if(child<0)die();
  if(S_ISDIR(st.st_mode))sync_tree(child);else if(fsync(child))die();close(child);
 }
 closedir(d);if(fsync(fd))die();
}

#define NATIVE "/root/mt3600be-passwall2-run-v4/transaction/native"
static void dir_private(const char *p){struct stat s;if(lstat(p,&s)||!S_ISDIR(s.st_mode)||s.st_uid||s.st_gid||(s.st_mode&07777)!=0700){errno=EPERM;die();}}
static void commit_entry(const char *entry,int erase){
 const char *names[]={"dhcp","firewall","uhttpd","ucitrack","luci","passwall2","passwall2_server",NULL};const char *name=NULL,*suffix=NULL;
 for(int i=0;names[i];i++){size_t n=strlen(names[i]);if(!strncmp(entry,names[i],n)&&entry[n]=='.'&&strlen(entry+n+1)==6){name=names[i];suffix=entry+n+1;break;}}
 if(!name||strspn(suffix,"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")!=6){errno=EINVAL;die();}
 char dir[256],anchor[280],temp[128];snprintf(dir,sizeof dir,NATIVE "/commits/%.64s",entry);snprintf(anchor,sizeof anchor,"%s/data",dir);snprintf(temp,sizeof temp,"/etc/config/.%s.uci-%s",name,suffix);
 dir_private(dir);DIR *d=opendir(dir);if(!d)die();struct dirent *e;
 while((e=readdir(d)))if(strcmp(e->d_name,".")&&strcmp(e->d_name,"..")&&strcmp(e->d_name,"data")){errno=EINVAL;die();}
 closedir(d);
 struct stat a,b;int exists=lstat(anchor,&a)==0;if(!exists&&errno!=ENOENT)die();
 int public_exists=lstat(temp,&b)==0;if(!public_exists&&errno!=ENOENT)die();
 if(!exists){if(public_exists){errno=ESTALE;die();}if(erase&&rmdir(dir))die();return;}
 if(!S_ISREG(a.st_mode)||a.st_uid||a.st_gid||a.st_nlink<1||a.st_nlink>2){errno=ESTALE;die();}
 int fd=open(anchor,O_RDONLY|O_NOFOLLOW);struct stat now;
 if(fd<0||flock(fd,LOCK_EX|LOCK_NB)||fstat(fd,&now)||a.st_dev!=now.st_dev||a.st_ino!=now.st_ino)die();
 if(public_exists&&(!S_ISREG(b.st_mode)||a.st_dev!=b.st_dev||a.st_ino!=b.st_ino||a.st_nlink!=2)){errno=ESTALE;die();}
 if(erase){
  if(public_exists){if(lstat(temp,&now)||a.st_dev!=now.st_dev||a.st_ino!=now.st_ino){errno=ESTALE;die();}if(unlink(temp))die();sync_parent(temp);}
  if(lstat(anchor,&now)||a.st_dev!=now.st_dev||a.st_ino!=now.st_ino){errno=ESTALE;die();}
  if(unlink(anchor))die();
  sync_parent(anchor);if(rmdir(dir))die();
  sync_parent(dir);
 }
 close(fd);
}
static void clean_commits(void){
 dir_private(NATIVE);dir_private(NATIVE "/commits");
 int lock=open(NATIVE "/commit.lock",O_RDWR|O_NOFOLLOW);struct stat s;
 if(lock<0||fstat(lock,&s)||!S_ISREG(s.st_mode)||s.st_uid||s.st_gid||s.st_nlink!=1||(s.st_mode&07777)!=0600)die();
 if(flock(lock,LOCK_EX|LOCK_NB)){errno=EBUSY;die();}
 /* Validate the whole set before deleting anything. Shared leases held by
  * native UCI processes prevent cleanup while an abandoned child still runs. */
 for(int erase=0;erase<2;erase++){
  DIR *d=opendir(NATIVE "/commits");if(!d)die();struct dirent *e;
  while((e=readdir(d)))if(strcmp(e->d_name,".")&&strcmp(e->d_name,".."))commit_entry(e->d_name,erase);
  closedir(d);
 }
 sync_parent(NATIVE "/commits/marker");close(lock);
}
static void copyfd(int in,int out){char b[65536];ssize_t n;if(lseek(in,0,SEEK_SET)<0)die();while((n=read(in,b,sizeof b))>0){ssize_t pos=0;while(pos<n){ssize_t w=write(out,b+pos,n-pos);if(w<=0)die();pos+=w;}}if(n<0)die();}
static void snapshot(const char *src,const char *before,const char *expected){
 struct stat st,now;int in=open(src,O_RDONLY|O_NOFOLLOW);
 if(in<0||flock(in,LOCK_SH|LOCK_NB)||fstat(in,&st)||!S_ISREG(st.st_mode)||st.st_nlink!=1)die();
 no_pending_commit(src);
 int b=open(before,O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(b<0)die();copyfd(in,b);
 if(fchown(b,st.st_uid,st.st_gid)||fchmod(b,st.st_mode&07777)||fsync(b))die();
 int e=open(expected,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(e<0)die();copyfd(b,e);
 if(fchown(e,st.st_uid,st.st_gid)||fchmod(e,st.st_mode&07777)||fsync(e))die();
 if(lstat(src,&now)||st.st_dev!=now.st_dev||st.st_ino!=now.st_ino||st.st_size!=now.st_size||st.st_mtim.tv_sec!=now.st_mtim.tv_sec||st.st_mtim.tv_nsec!=now.st_mtim.tv_nsec||st.st_ctim.tv_sec!=now.st_ctim.tv_sec||st.st_ctim.tv_nsec!=now.st_ctim.tv_nsec){errno=ESTALE;die();}
 no_pending_commit(src);sync_parent(before);sync_parent(expected);close(e);close(b);close(in);
}

int main(int c,char **v) {
 struct stat s; if(c<2) return 2;
 if(!strcmp(v[1],"native-clean")){if(c!=2)return 2;clean_commits();return 0;}
 if(c<3)return 2;
 if(!strcmp(v[1],"snapshot")){if(c!=5)return 2;snapshot(v[2],v[3],v[4]);return 0;}
 if(!strcmp(v[1],"sync-tree")){
  if(c!=3||strncmp(v[2],"/root/mt3600be-passwall2-run-v4/.prepare.",sizeof("/root/mt3600be-passwall2-run-v4/.prepare.")-1))return 2;
  int fd=open(v[2],O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)die();sync_tree(fd);close(fd);return 0;
 }
 if(!strcmp(v[1],"meta")) {
  if(c!=3 || lstat(v[2],&s)) return 1;
  printf("%u:%u:%o:%c\n",s.st_uid,s.st_gid,s.st_mode&07777,
    S_ISREG(s.st_mode)?'f':S_ISDIR(s.st_mode)?'d':S_ISLNK(s.st_mode)?'l':'x');return 0;
 }
 if(!strcmp(v[1],"record")) {
  if(c!=5 || strncmp(v[4],"/root/mt3600be-passwall2-run-v4/.attempt.",sizeof("/root/mt3600be-passwall2-run-v4/.attempt.")-1)) return 2;
  if(lstat(v[2],&s)==0) {if(!S_ISREG(s.st_mode)||s.st_uid||s.st_nlink!=1)return 1;}
  else if(errno!=ENOENT)return 1;
  char *t; if(asprintf(&t,"%s/record.XXXXXX",v[4])<0) die();
  int fd=mkstemp(t);if(fd<0) die();
  size_t n=strlen(v[3]);
  if(fchmod(fd,0600)||write(fd,v[3],n)!=(ssize_t)n||write(fd,"\n",1)!=1||fsync(fd)) die();
  if(close(fd)||rename(t,v[2])) die();
  sync_parent(v[2]);free(t);return 0;
 }
 if(!strcmp(v[1],"publish")) {
  /* Atomically publish a prepared directory, only if destination is absent. */
  if(c!=4) return 2;
  if(lstat(v[2],&s)||!S_ISDIR(s.st_mode)||s.st_uid||(s.st_mode&0777)!=0700) return 1;
  if(syscall(SYS_renameat2,AT_FDCWD,v[2],AT_FDCWD,v[3],RENAME_NOREPLACE)) die();
  sync_parent(v[3]);return 0;
 }

 if(!strcmp(v[1],"restore")) {
  if(c!=7||strncmp(v[4],"/root/mt3600be-passwall2-run-v4/.attempt.",sizeof("/root/mt3600be-passwall2-run-v4/.attempt.")-1)) return 2;
  int in=open(v[2],O_RDONLY|O_NOFOLLOW);struct stat src,old,now;
  if(in<0||fstat(in,&src)||!S_ISREG(src.st_mode)||src.st_nlink!=1)die();
  int existed=lstat(v[3],&old)==0;
  if(!existed&&errno!=ENOENT)die();
  if(!existed||!S_ISREG(old.st_mode))return 1;
  int target=open(v[3],O_RDONLY|O_NOFOLLOW);if(target<0||flock(target,LOCK_EX|LOCK_NB))die();
  struct stat opened;if(fstat(target,&opened)||old.st_dev!=opened.st_dev||old.st_ino!=opened.st_ino){errno=ESTALE;die();}
  no_pending_commit(v[3]);
  verify_target(target,v[5],v[6]);
  char *t;if(asprintf(&t,"%s/restore.XXXXXX",v[4])<0)die();int out=mkstemp(t);if(out<0)die();
  char b[65536];ssize_t nr;
  while((nr=read(in,b,sizeof b))>0){ssize_t i=0;while(i<nr){ssize_t w=write(out,b+i,nr-i);if(w<=0)die();i+=w;}}
  if(nr<0||fchown(out,src.st_uid,src.st_gid)||fchmod(out,src.st_mode&07777)||fsync(out)||close(out))die();
  close(in);
  if(existed){if(lstat(v[3],&now)||old.st_dev!=now.st_dev||old.st_ino!=now.st_ino||old.st_size!=now.st_size||old.st_mtim.tv_sec!=now.st_mtim.tv_sec||old.st_mtim.tv_nsec!=now.st_mtim.tv_nsec)die();}
  else if(lstat(v[3],&now)==0||errno!=ENOENT)die();
  no_pending_commit(v[3]);
  verify_target(target,v[5],v[6]);
  /* rename fails on mount boundaries; NEVER copy as a fallback. */
  if(rename(t,v[3]))die();
  sync_parent(v[3]);close(target);free(t);return 0;
 }

 if(!strcmp(v[1],"remove")) {
  if(c!=6||lstat(v[2],&s))return 1;
  struct stat initial=s,now;char m[96];snprintf(m,sizeof m,"%u:%u:%o:%c",s.st_uid,s.st_gid,s.st_mode&07777,S_ISREG(s.st_mode)?'f':S_ISLNK(s.st_mode)?'l':'x');
  if(strcmp(m,v[4]))return 1;
  int fd=-1;
  if(!strcmp(v[5],"f")){
   fd=open(v[2],O_RDONLY|O_NOFOLLOW);if(fd<0||flock(fd,LOCK_EX|LOCK_NB))die();verify_target(fd,v[3],v[4]);
  }else if(!strcmp(v[5],"l")){
   char target[4096];ssize_t n=readlink(v[2],target,sizeof target-1);if(n<0||n>=(ssize_t)sizeof target-1)return 1;target[n]=0;if(strcmp(target,v[3]))return 1;
  }else return 2;
  if(lstat(v[2],&now)||now.st_ino!=initial.st_ino||now.st_dev!=initial.st_dev){errno=ESTALE;die();}
  if(unlink(v[2]))die();
  sync_parent(v[2]);if(fd>=0)close(fd);return 0;
 }

 if(!strcmp(v[1],"link-restore")) {
  if(c!=4||lstat(v[2],&s)||!S_ISLNK(s.st_mode))return 1;
  if(lstat(v[3],&s)==0&&!S_ISLNK(s.st_mode))return 1;
  if(rename(v[2],v[3]))die();
  sync_parent(v[3]);return 0;
 }
 if(!strcmp(v[1],"run")) {
  if(c!=3)return 2;
  pid_t p=fork();if(p<0)die();
  if(!p){close(7);close(8);close(9);umask(022);execl("/bin/sh","sh",v[2],(char*)0);_exit(127);}
  int st;while(waitpid(p,&st,0)<0){if(errno!=EINTR)die();}
  return WIFEXITED(st)?WEXITSTATUS(st):128;
 }
 return 2;
}
