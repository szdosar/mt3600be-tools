# 支持的官方 op25 测试固件

## 仅适用于这一版固件

镜像的是原始测试固件，**没有预装 EEE 或 Passwall2，也不是本项目的 image-v 系列修改版固件**。先完成原厂初始化；安装 Passwall2 前先从原厂高级设置安装 LuCI，再运行工具菜单。

本仓库的 EEE 与 Passwall2 工具均基于 **GL-MT3600BE 官方 op25 测试版**适配和测试：**4.9.1-op25 / OpenWrt 25.12.5 / Linux 6.12.94**，构建号 `r33051-f5dae5ece4`，APK 包管理器。

- [本仓库固件镜像下载](https://github.com/szdosar/mt3600be-tools/releases/tag/firmware-op25-25.12.5)（原文件，未修改、未重新封装）。
- [原始固件下载页面](https://github.com/wukongdaily/gl-inet-onescript/releases/tag/mt3600be)（第三方仓库提供的下载入口，不是 GL.iNet 官方仓库）。
- 文件名：`openwrt25.12.5-mediatek-filogic-glinet_gl-mt3600be-squashfs-sysupgrade.bin`
- SHA-256：`d4f65c9c44d0516a798fcf1b111ed7e8bdb54c9533202d02ac53c35d5e81239c`
- 已核对该发布附件摘要与本地用于适配的原始固件一致；[机器可读记录](../firmware.json)。

**不表示兼容所有官方固件。** 4.9.0、其他 4.9.x、其他 op25 构建、LEDE、ImmortalWrt 均不能据此直接安装。不要跳过版本、架构、PHY 或内核 ABI 检查。脚本不自动下载或刷写固件；刷机需求请另行核对。

安装器能核对运行系统版本字段与组件 ABI，不能仅凭这些字段证明用户实际刷入的镜像字节。准备固件时请核对上面的原始镜像摘要。
