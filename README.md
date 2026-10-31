# MT3600BE 工具箱

适用于 **GL.iNet GL-MT3600BE（Beryl 7）** 的独立工具。**不刷固件、不自动重启**。原厂与 LEDE 包严格区分；不是 GL.iNet 官方项目或厂商签名包。

## 小白怎么用

1. 通过 SSH 登录路由器：`ssh root@192.168.8.1`。以下命令在**路由器**终端运行，不在电脑上运行。
2. 安装 Passwall2 前，先从原厂“高级设置”安装并开启 LuCI，备份现有设置。
3. 整段复制下面命令并回车。它先下载校验入口，再显示中文菜单。选择工具和操作，输入 `YES` 才更改；其他输入取消。

```sh
(
set -eu
umask 077
t=$(mktemp /tmp/mt3600be-launch.XXXXXXXX) || exit 1
trap 'rm -f -- "$t"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap '' HUP
curl -q --fail --location --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 120 --max-filesize 1048576 --output "$t" https://github.com/szdosar/mt3600be-tools/releases/download/online-v1/install.sh
[ -s "$t" ]
printf '%s  %s\n' 'cc5a17f1b939306e3f657a0099e2fa951ce36616b3845faff7c68e098e1dec61' "$t" | sha256sum -c -
sh -n "$t"
sh "$t"
 )
```

需要可正常验证 HTTPS 的网络和系统时间，以及 `curl`、`sha256sum`、`flock`。缺少命令会停止，不自动改软件源、代理或 DNS。首次下载失败可重试同一段命令；不要使用 `-k` 或关闭校验，也不要使用来历不明的加速镜像。无需 GitHub 登录、Token 或提供路由器密码给脚本。

## 选择哪个工具

| 菜单 | 支持范围 | 用途 |
|---|---|---|
| 原厂 WAN EEE v1.2-r3 | 原厂 4.9.1-op25 / Linux 6.12.94 / RTL8221B | 关闭 WAN EEE，保留状态查询、回滚和重新启用 |
| LEDE WAN EEE v1 | LEDE R26.10.31 / Linux 6.12.115 / RTL8221B PHY@7 | 同上，但不接管原厂版事务 |
| 原厂 Passwall2 native-r4.2 | 原厂 OpenWrt 25.12.5 / Linux 6.12.94，先安装 LuCI | Passwall2 26.10.20-r2 + Xray 26.10.21-r2，含 sslocal、Haproxy、Sing-box 和离线依赖 |

其他型号、固件或内核不支持，不能删除版本检查强装。不自动把几个工具同时安装。EEE 只处理 WAN，不修改 LAN。Passwall2 r4.2 完成隔离测试，仍为待用户真机验证的试用包。

## 下载与断线恢复

- [所有发布包](https://github.com/szdosar/mt3600be-tools/releases)；下载 Assets 里的 `.run` 和 `.sha256`，GitHub 自动生成的 Source code ZIP 不是安装包。
- 在线脚本固定使用 [catalog.json](catalog.json) 中的版本和 SHA-256；不会自动追踪 latest，也不会降级为 HTTP。
- 每次执行独立验证副本。下载失败、摘要错误、缓存异常或双终端竞争时停止，不覆盖旧缓存或事务。
- 已验证 run 保留在 `/root/mt3600be-tools/<工具>/<发布标签>/`。断网后可直接用原 run 查询/回滚，不需要再次下载在线脚本。
- SSH 断线或收到中断后，先重新登录查询。不要删除组件事务、原始快照或锁文件强装。强制断电可能留下 `.download.*` 或 `/tmp/mt3600be-online.*` 残留；不会拿它们冒充完整包，后续重试使用新临时文件，不自动删来源不明的残留。

[离线操作和回滚命令](docs/OFFLINE.md) · [EEE 说明](docs/EEE.md) · [Passwall2 安装说明](docs/passwall2.md) · [验证边界](docs/VALIDATION.md)

## 改动范围

EEE 安装可能短暂重新协商 WAN 链路，建议从 LAN 管理；回滚恢复已保存的原始 EEE，不改 DNS、VPN、无线或插件配置。

Passwall2 保留原生安装行为，可能更新 DHCP `localuse`、防火墙 include、uhttpd、ucitrack；已有主开关开启时可能启动代理。保留两份插件配置的内容和权限（含 root:root 664），默认模板另存。回滚只卸载本次新增包并恢复记录的接入修改；后续配置冲突会拒绝覆盖。旧 r4/r4.1 正式事务不自动接管；仅权限预检失败可换本版重试。

本仓库只发布工具源码、公共默认内容和验证摘要，不发布设备配置、节点、密码、密钥或备份。不要把路由器事务目录上传到 Issue。旧版发布按标签保留；修复采用新版本，不替换既有 run 文件。
