# eee-lede-v1 源码

与发布 run 对应的辅助程序及控制脚本。仅支持 LEDE R26.10.31 / Linux 6.12.115、MT3600BE WAN eth0 RTL8221B。不得放宽型号、内核和 PHY 检查强装。使用在线菜单或原 run 的 status/install/rollback/enable，不直接跨版本调用旧安装的辅助命令。

回滚保留原始快照；未验证快照（包括不支持的计时器）仍拒绝。该源码不含任何设备状态。
