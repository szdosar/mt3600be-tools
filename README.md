# MT3600BE 工具箱

适用于 **GL.iNet GL-MT3600BE（Beryl 7）** 的独立工具。**不刷固件、不自动重启**。仅适用于下述官方 op25 测试版；本工具箱为社区项目，非 GL.iNet 官方项目。

## 这些工具解决什么问题

- **WAN EEE 有线稳定工具**：针对指定官方 op25 测试版固件中，**WAN 口协商为 1 Gbps 时与 EEE 节能功能相关的丢包、断流问题**，通过关闭 WAN EEE 规避，并提供开机生效、状态查询和回滚。只处理 WAN，不处理 LAN；不能作为所有网线、网口或上游故障的通用修复。
- **Passwall2 科学研究工具**：用于**网络代理、协议测试和连通性分析等科学研究**，提供代理与流量分流管理。离线安装包包含 Passwall2、Xray、sslocal、Haproxy、Sing-box 及匹配依赖，解决该测试版固件上依赖配套和离线安装的问题。**不附带代理节点或订阅**，安装后需自行配置；先从原厂高级设置安装 LuCI。

## 仅适用于这一版固件

镜像的是原始测试固件，**没有预装 EEE 或 Passwall2，也不是本项目的 image-v 系列修改版固件**。先完成原厂初始化；安装 Passwall2 前先从原厂高级设置安装 LuCI，再运行工具菜单。

本仓库的 EEE 与 Passwall2 工具均基于 **GL-MT3600BE 官方 op25 测试版**适配和测试：**4.9.1-op25 / OpenWrt 25.12.5 / Linux 6.12.94**，构建号 `r33051-f5dae5ece4`，APK 包管理器。

- [本仓库固件镜像下载](https://github.com/szdosar/mt3600be-tools/releases/tag/firmware-op25-25.12.5)（原文件，未修改、未重新封装）。
- [原始固件下载页面](https://github.com/wukongdaily/gl-inet-onescript/releases/tag/mt3600be)（第三方仓库提供的下载入口，不是 GL.iNet 官方仓库）。
- 文件名：`openwrt25.12.5-mediatek-filogic-glinet_gl-mt3600be-squashfs-sysupgrade.bin`
- SHA-256：`d4f65c9c44d0516a798fcf1b111ed7e8bdb54c9533202d02ac53c35d5e81239c`
- 已核对该发布附件摘要与本地用于适配的原始固件一致；[机器可读记录](firmware.json)。

**不表示兼容所有官方固件。** 其他官方版本、其他 op25 构建及第三方固件均不能据此直接安装。不要跳过版本、架构、PHY 或内核 ABI 检查。脚本不自动下载或刷写固件；刷机需求请另行核对。

安装器能核对运行系统版本字段与组件 ABI，不能仅凭这些字段证明用户实际刷入的镜像字节。准备固件时请核对上面的原始镜像摘要。

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
curl -q --fail --location --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 120 --max-filesize 1048576 --output "$t" https://github.com/szdosar/mt3600be-tools/releases/download/online-v1.3/install.sh
[ -s "$t" ]
printf '%s  %s\n' '1bf93767c99771a5b34c74d6c7c3ae90706927250386fc955008222e2e4221c8' "$t" | sha256sum -c -
sh -n "$t"
sh "$t"
 )
```

当前在线入口为 **online-v1.3**。无需另装 `stat`：缺少时自动使用目标固件自带的 `ucode` 文件系统接口，继续核对类型、权限、大小和锁身份；任一检查失败都停止。

需要可正常验证 HTTPS 的网络和系统时间，以及 `curl`、`sha256sum`、`flock`。缺少命令会停止，不自动改软件源、代理或 DNS。此前看到“缺少 stat”的用户，重新复制本页最新整段命令即可，不必删除旧配置、缓存、事务或备份。首次下载失败可重试同一段命令；不要使用 `-k` 或关闭校验，也不要使用来历不明的加速镜像。无需 GitHub 登录、Token 或提供路由器密码给脚本。

## 选择哪个工具

| 菜单 | 支持范围 | 用途 |
|---|---|---|
| 原厂 WAN EEE v1.2-r3 | 上述官方 op25 测试版 / RTL8221B | 规避 1G WAN 链路下与 EEE 相关的丢包，支持查询和回滚 |
| 原厂 Passwall2 native-r4.3 | 上述官方 op25 测试版，先安装 LuCI | 科学研究、代理与分流管理；Passwall2 26.10.20-r2 + Xray 26.10.21-r2，含匹配依赖 |

其他型号、固件或内核不支持，不能删除版本检查强装。不自动把几个工具同时安装。EEE 只处理 WAN，不修改 LAN。Passwall2 r4.3 完成隔离测试，仍为待用户真机验证的试用包。

## 下载与断线恢复

- [所有发布包](https://github.com/szdosar/mt3600be-tools/releases)；下载 Assets 里的 `.run` 和 `.sha256`，GitHub 自动生成的 Source code ZIP 不是安装包。
- 在线脚本固定使用 [catalog.json](catalog.json) 中的版本和 SHA-256；不会自动追踪 latest，也不会降级为 HTTP。
- 每次执行独立验证副本。下载失败、摘要错误、缓存异常或双终端竞争时停止，不覆盖旧缓存或事务。
- 已验证 run 保留在 `/root/mt3600be-tools/<工具>/<发布标签>/`。断网后可直接用原 run 查询/回滚，不需要再次下载在线脚本。
- SSH 断线或收到中断后，先重新登录查询。不要删除组件事务、原始快照或锁文件强装。强制断电可能留下 `.download.*` 或 `/tmp/mt3600be-online.*` 残留；不会拿它们冒充完整包，后续重试使用新临时文件，不自动删来源不明的残留。

[离线操作和回滚命令](docs/OFFLINE.md) · [EEE 说明](docs/EEE.md) · [Passwall2 安装说明](docs/passwall2.md) · [验证边界](docs/VALIDATION.md)

## 改动范围

EEE 安装可能短暂重新协商 WAN 链路，建议从 LAN 管理；回滚恢复已保存的原始 EEE，不改 DNS、VPN、无线或插件配置。

Passwall2 保留原生安装行为，可能更新 DHCP `localuse`、防火墙 include、uhttpd、ucitrack；已有主开关开启时可能启动代理。保留两份插件配置的内容和权限（含 root:root 664），默认模板另存。回滚只卸载本次新增包并恢复记录的接入修改；后续配置冲突会拒绝覆盖。旧 r4/r4.1/r4.2 正式事务不自动接管；仅预检失败或事务仅剩空目录时可换本版重试。空目录持锁确认后原子归档；任何实际记录缺失或损坏仍拒绝，不删配置和备份。

本仓库发布原始测试固件镜像、工具源码、公共默认内容和验证摘要，不发布设备配置、节点、密码、密钥或备份。不要把路由器事务目录上传到 Issue。工具按固定版本发布；后续更新使用新版本号，不替换既有 run 文件。
