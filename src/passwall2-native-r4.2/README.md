# native-r4.2 控制器源码

与发布 run 对应的外围 shell 和 ARM helper C 源码。APK 版本与上游原生安装脚本不修改，默认模板来自签名 APK。

包含 Passwall2 26.10.20-r2、Xray 26.10.21-r2、sslocal 1.25.0-r1、Haproxy 3.2.15-r1、Sing-box 1.12.17-r1 与匹配依赖，完整清单见 run 内元数据。不得把原厂内核模块装到 LEDE。

安装及回滚见 ../../docs/passwall2.md。完整离线测试报告摘要见 ../../docs/VALIDATION.md。
