# 断网查询和回滚

首次成功下载后，可在路由器终端使用下面命令。先执行对应目录的 SHA-256 校验；公开摘要见根目录 catalog.json。在线缓存不会自动保存额外 `.sha256` 文件，下列校验直接使用固定摘要。

## eee-official / eee-v1.2-r3

```sh
cd /root/mt3600be-tools/eee-official/eee-v1.2-r3 &&
printf '%s  %s\n' 'baaeaafb216f845270bb477605ffa3889c166758e953454dfabee3403738efbb' 'mt3600be-eee-tool-v1.2-r3.run' | sha256sum -c - &&
sh ./mt3600be-eee-tool-v1.2-r3.run status
```

回滚时，把最后一行的 `status` 改成 `rollback`。EEE run 会再次要求输入 YES；也支持 enable 重新启用。

## passwall2 / passwall2-native-r4.3

```sh
cd /root/mt3600be-tools/passwall2/passwall2-native-r4.3 &&
printf '%s  %s\n' '628edf81254ae180c5a0cb168db9bc31341a2a6cbbf63ee58e5be86ab9b472ad' 'passwall2-high-native-r4.3.run' | sha256sum -c - &&
sh ./passwall2-high-native-r4.3.run status
```

回滚时，把最后一行的 `status` 改成 `rollback --apply`。Passwall2 的 --apply 表示你明确同意回滚，先关闭正在运行的代理。

不要单独执行未校验的旧下载文件。事务记录损坏、版本不匹配或共享配置后来发生变化时，停止并保留现场，不删除备份或强制接管。

恢复出厂或不保留配置刷机后，本地缓存和补丁可能消失；重新核对固件是否仍支持，再安装。此工具不是升级固件后的自动适配器。
