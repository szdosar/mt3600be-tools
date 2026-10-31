/* Build expected native UCI commits in a PRIVATE configuration directory.
 * No global delta paths or override directory are read. Never used on /etc. */
#include <uci.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static struct uci_context *c;
static void bad(void){fputs("private UCI projection failed\n",stderr);exit(1);}
static void set(const char *s){struct uci_ptr p;char *b=strdup(s);if(uci_lookup_ptr(c,&p,b,1)||uci_set(c,&p))bad();free(b);}
static void del(const char *s){struct uci_ptr p;char *b=strdup(s);int rc=uci_lookup_ptr(c,&p,b,1);if(rc!=UCI_OK&&rc!=UCI_ERR_NOTFOUND)bad();if(!rc&&(p.flags&UCI_LOOKUP_COMPLETE)&&uci_delete(c,&p))bad();free(b);}
static void validate_existing(void){
 const char *pkgs[]={"firewall","ucitrack"};
 for(int i=0;i<2;i++){
  struct uci_package *p=NULL;
  int rc=uci_load(c,pkgs[i],&p);if(rc){if(i==1&&rc==UCI_ERR_NOTFOUND)continue;bad();}
  int counts[2]={0,0};struct uci_element *e;
  uci_foreach_element(&p->sections,e){
   struct uci_section *s=uci_to_section(e);int index=-1;
   const char *match=i?s->type:e->name;
   if(!strcmp(match,"passwall2"))index=0;else if(!strcmp(match,"passwall2_server"))index=1;else continue;
   if(++counts[index]>1)bad();
   if(!i&&strcmp(s->type,"include"))bad();
   const char *name=index?"passwall2_server":"passwall2";int got_type=0,got_path=0,got_init=0;
   struct uci_element *oe;
   uci_foreach_element(&s->options,oe){
    struct uci_option *o=uci_to_option(oe);if(o->type!=UCI_TYPE_STRING)bad();const char *v=o->v.string;
    if(i){if(strcmp(oe->name,"init")||strcmp(v,name))bad();got_init=1;}
    else if(!strcmp(oe->name,"type")){if(strcmp(v,"script"))bad();got_type=1;}
    else if(!strcmp(oe->name,"path")){char want[128];snprintf(want,sizeof want,"/var/etc/%s.include",name);if(strcmp(v,want))bad();got_path=1;}
    else if(!strcmp(oe->name,"reload")||!strcmp(oe->name,"fw4_compatible")||!strcmp(oe->name,"enabled")){if(strcmp(v,"1"))bad();}
    else bad();
   }
   if(i?!got_init:(!got_type||!got_path))bad();
  }
  uci_unload(c,p);
 }
}
int main(int n,char **v){
 if(n!=3||strncmp(v[1],"/root/mt3600be-passwall2-run-v4/",sizeof("/root/mt3600be-passwall2-run-v4/")-1)||strstr(v[1],".."))return 2;
 c=uci_alloc_context();if(!c)bad();
 /* Discard the default search path list (process-local, tiny intentional leak).
  * set_savedir may add another path, so reset only after all setters. */
 char saved[1024],over[1024];
 if(snprintf(saved,sizeof saved,"%s/.delta",v[1])>=sizeof saved||snprintf(over,sizeof over,"%s/.override",v[1])>=sizeof over)bad();
 if(uci_set_confdir(c,v[1])||uci_set_conf2dir(c,over)||uci_set_savedir(c,saved))bad();
 c->delta_path.next=c->delta_path.prev=&c->delta_path;
 if(!strcmp(v[2],"validate-existing")){validate_existing();uci_free_context(c);return 0;}
 const char *pkg=NULL;struct uci_package *p=NULL;struct uci_section *s=NULL;
 if(!strcmp(v[2],"dhcp")){pkg="dhcp";set("dhcp.@dnsmasq[0].localuse=1");}
 else if(!strcmp(v[2],"uhttpd")){pkg="uhttpd";set("uhttpd.main.max_requests=50");}
 else if(!strcmp(v[2],"luci")){pkg="luci";set("luci.languages.zh_cn=简体中文 (Simplified Chinese)");}
 else if(!strcmp(v[2],"firewall1")||!strcmp(v[2],"firewall2")){
  pkg="firewall";const char *x=!strcmp(v[2],"firewall1")?"passwall2":"passwall2_server";char b[256];
  snprintf(b,sizeof b,"firewall.%s",x);del(b);
  snprintf(b,sizeof b,"firewall.%s=include",x);set(b);
  snprintf(b,sizeof b,"firewall.%s.type=script",x);set(b);
  snprintf(b,sizeof b,"firewall.%s.path=/var/etc/%s.include",x,x);set(b);
  snprintf(b,sizeof b,"firewall.%s.reload=1",x);set(b);
 }else if(!strcmp(v[2],"ucitrack1")||!strcmp(v[2],"ucitrack2")){
  pkg="ucitrack";const char *x=!strcmp(v[2],"ucitrack1")?"passwall2":"passwall2_server";
  char b[256];snprintf(b,sizeof b,"ucitrack.@%s[-1]",x);del(b);
  struct uci_element *e;uci_foreach_element(&c->root,e){if(!strcmp(e->name,pkg)){p=uci_to_package(e);break;}}
  if(!p&&uci_load(c,pkg,&p))bad();
  if(uci_add_section(c,p,x,&s))bad();
  snprintf(b,sizeof b,"ucitrack.%s.init=%s",s->e.name,x);set(b);
 }else return 2;
 if(!p){struct uci_element *e;uci_foreach_element(&c->root,e){if(!strcmp(e->name,pkg)){p=uci_to_package(e);break;}}}
 if(!p)bad();
 p->has_delta=false; /* export the in-memory projection; never load any delta */
 if(uci_commit(c,&p,1))bad();
 uci_free_context(c);return 0;
}
