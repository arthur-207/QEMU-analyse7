# T1 解决方案：QEMU 6.2.0 与 KVM 的用户态 ABI

本实验回答：QEMU 如何把内存和 vCPU 交给 KVM，KVM 如何把需要用户态设备模拟的事件交回 QEMU。
这里的“协议”是 Linux KVM 用户态 ABI：文件描述符、ioctl 请求、mmap 共享结构体；不是网络协议。

## 已验证的源码与接口

源码根目录：Ubuntu-T1 的 `/root/t1-lab/src/qemu-6.2.0`。
网页列出本次读取文件的 SHA256 和精确命中行，便于复查。源码摘录不等于该行本次一定执行。

| 源码 | 分析位置 | 协议与机制 |
|---|---|---|
| accel/kvm/kvm-all.c | kvm_init，2306 起 | 打开 /dev/kvm；KVM_GET_API_VERSION 返回 12；KVM_CHECK_EXTENSION 探测能力；KVM_CREATE_VM 得到 VM fd |
| 同上 | kvm_init_vcpu，454 起；创建调用在 451 | KVM_CREATE_VCPU 得到 vCPU fd；KVM_GET_VCPU_MMAP_SIZE；mmap(MAP_SHARED) 映射 kvm_run |
| 同上 | 内存注册调用 367/373；kvm_set_phys_mem，1337 起 | KVM_SET_USER_MEMORY_REGION：slot、guest_phys_addr、memory_size、userspace_addr 建立 GPA 到 QEMU 用户态 RAM 的关联；不意味着每次访存均退出 |
| target/i386/kvm/kvm.c | kvm_arch_init_vcpu 1567；kvm_arch_put_registers 4168；kvm_arch_get_registers 4250 | x86 初始化及 KVM_SET/GET_REGS、SREGS、MSRS 等寄存器同步 |
| accel/kvm/kvm-all.c | kvm_cpu_exec，2814 起 | 对 vCPU fd 调用 KVM_RUN；处理 EINTR/EAGAIN 等返回；成功后读取共享 run->exit_reason |
| 同上 | 2890/2900 | KVM_EXIT_IO 调 kvm_handle_io，使用 port/direction/size/count/data_offset；KVM_EXIT_MMIO 调 address_space_rw，使用 phys_addr/data/len/is_write；处理后通常重新 KVM_RUN |
| linux-headers/linux/kvm.h | ABI 宏、struct kvm_run 等定义 | 核对请求与共享数据结构；这是 QEMU 附带头文件，不是当前 WSL KVM 内核实现源码 |
| accel/kvm/kvm-accel-ops.c | 仅保存检索结果供导航 | 本轮未深入分析线程调度实现，不将其作为核心机制证据 |

fd 分层：系统 fd 负责 API/能力/建 VM；VM fd 负责内存/IRQ/建 vCPU；vCPU fd 负责寄存器和运行。
KVM_RUN 的系统调用返回值和 kvm_run.exit_reason 是两个不同概念。exit_reason=2 是 IO，6 是 MMIO；这也是用户态可见退出，不是全部硬件 VM-exit。

## 实验与证据

保留现有 4 核 4 GB Ubuntu 客户机，另起强制 `accel=kvm` 的 1 核 16 MB 实验机，不联网、不访问原客户机工作盘。
collect.py 生成 512 字节可启动程序：依次 OUT 四个字符到 0xe9，再向 0xf4 输出 0x10。
QEMU debugcon 保存 `KVM!`，isa-debug-exit 设备使进程按 `(0x10 << 1) | 1 = 33` 结束。
可执行程序在 evidence/boot.bin，运行环境使用已安装 QEMU 及其 BIOS；验证虚机交付时仍需保留原有 QEMU/WSL 环境。

- strace 捕获 openat、ioctl、mmap，日志 `evidence/syscalls.log` 是首要系统调用证据。
- QEMU 自带 kvm_run_exit、kvm_set_user_memory trace 保存到 `evidence/qemu-trace.log`。
- `evidence/guest-output.txt` 是客户机程序输出；`evidence/stderr.txt` 保存错误输出。
- `evidence.json` 包含命令、版本、内核、时间、计数、源码位置及运行中的 QEMU。
- 所有调用次数包括 BIOS 启动阶段；不能把它们全部归因于四条 OUT。MMIO 已观测到，但本轮没有隔离并确定每个 MMIO 的设备来源。
- 寄存器、CPUID、IRQ 等附加接口以实际日志为准；能力探测返回 0 可能代表不支持，不必然是错误。
- strace 会明显干扰运行速度，这些数字不能用于 T2 性能结论。

本轮实测：API=12；vCPU mmap 大小=12288；KVM_RUN=4001 次；IO 退出=3624；MMIO 退出=376；输出 KVM!；退出码 33。计数随运行变化。4001 与 4000 个已记录退出不必相等，退出设备会在最后一次处理途中终止进程。

## 打开窗口和重复实验

Windows 直接双击本目录 index.html 即可看已生成快照，不需要安装网页依赖。
窗口不是实时跟踪器；“刷新证据”只读数据。文件方式打开时，重新采集后请重新打开网页或用文件框选 evidence.json。

在 **Windows PowerShell** 复制：

```powershell
wsl -d Ubuntu-T1 -u root -- python3 '/mnt/e/code work/wdwd-1/t1-visual/collect.py'
Start-Process 'E:\code work\wdwd-1\t1-visual\index.html'
```

在 **root@LAPTOP… 的 WSL 宿主** 也可运行：

```bash
python3 '/mnt/e/code work/wdwd-1/t1-visual/collect.py'
```

不要在 ubuntu@t1-guest 终端执行以上路径。采集一般数秒，超时则先检查环境及 stderr，不要把失败结果写成通过。

## 三人分工与 AI 协作记录建议

1. 成员 A：逐项阅读 kvm-all.c 和 ABI 头文件，写初始化/内存/运行循环，复核源码行号。
2. 成员 B：复跑程序，核对 fd、mmap、ioctl 返回和退出 trace，保存原始日志及录屏。
3. 成员 C：说明 x86 寄存器与设备退出机制，整理窗口、报告及验证虚机交付。

以上是建议分工，不是已完成的人类工作记录。AI 本轮编写采集程序及窗口，读取本机源码，运行实验生成真实证据；团队需记录各自实际复核、修订和验证过程。
报告以“问题 → 源码 → ABI → 原始证据 → 局限”组织，在 2026-11-08 23:59 前交付报告、程序、环境与协作记录。
