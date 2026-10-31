# WAN EEE 工具

原厂版本与 LEDE 版本是两个独立发布。均只支持 GL-MT3600BE WAN eth0、已核验的 RTL8221B，具体版本见首页；不自动把工具应用到 LAN 或其他 PHY。

安装前保存 EEE 原始状态及校验和，通过 procd 与热插拔维持关闭。重复运行不会覆盖原始状态。首次状态不支持（例如未验证的 tx_lpi_timer=0）时仍拒绝，不能篡改快照或放宽校验。

不完整首次事务可通过 EEE 工具的 archive-incomplete 操作，在检查无安装文件后保留并归档。以后重新安装会采集新基线，不能说成恢复旧基线。在线脚本可显式调用 `sh install.sh eee-official archive-incomplete`（LEDE 改成 eee-lede），需要 YES 确认。

回滚先禁用后台应用，再用已核验的原始快照恢复；中断后可重试。支持的旧原厂版由本 run 菜单走已检查的回滚路径，避免直接调用旧命令。不能跨固件搬运快照，不自动接管其他版本或设备的记录。

正常关闭应看到 mode=enabled、eee_active=0、tx_lpi_enabled=0、advertised=0x0、PHY 标准 EEE 通告为零。只有状态通过不代表所有丢包都解决，还需要你的链路实测。
