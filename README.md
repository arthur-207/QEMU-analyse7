# QEMU-analyse7

AI 协同化学习项目：QEMU 6.2.0 与 Linux KVM 交互分析。

## T1 实验成果

- [实验方案、源码位置、KVM ABI、三人分工建议与复现步骤](t1-visual/README.md)
- [可视化页面源码](t1-visual/index.html)：下载仓库后，用浏览器打开；GitHub 文件预览不会直接运行网页。
- [采集程序](t1-visual/collect.py)：在已配置 QEMU 6.2.0、KVM、Python 3 和 strace 的 Linux 宿主执行。
- [机器可读实验结果](t1-visual/evidence.json)
- [原始系统调用日志](t1-visual/evidence/syscalls.log)
- [QEMU 退出跟踪日志](t1-visual/evidence/qemu-trace.log)

本次已验证客户机输出 `KVM!`，演示进程按预期返回 33。可视化显示真实采集快照，不是实时监控。

## 移植运行

默认 QEMU 路径为 `/opt/qemu-6.2.0/bin/qemu-system-x86_64`，源码路径为 `/root/t1-lab/src/qemu-6.2.0`。其他机器需先修改 `collect.py` 中的 `QEMU` 和 `SRC`。

```bash
python3 t1-visual/collect.py
```

然后在浏览器打开 `t1-visual/index.html`。日志、快照及源码摘录会重新生成；次数可能变化。

本仓库提供 T1 程序与验证证据，不包含完整 WSL 发行版、Ubuntu 虚拟磁盘、QEMU 安装包或 SSH 私钥。T2/T3 尚未包含。
