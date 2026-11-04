# WAN EEE v1.2-r4 源码与测试

运行行为与发布run对应，构建产物不提交源码目录。仅支持指定官方op25。timer=0写入仍拒绝。

`run_release_tests.py` 是失败即停止的发布门禁。需要本地ARM交叉工具链、qemu-aarch64-static、BusyBox；v1.1及r3兼容测试需已归档旧版公共工具作为夹具（无设备快照）。测试只生成合成状态，不连接路由器。驱动函数实验与ARM ioctl模拟均不是硬件测试。

发布门禁的完整结果在仓库 tests/eee-r4-validation.json；具体使用见 docs/EEE.md。2026-11-04真机结果属于r3，不能标成r4真机验收。
