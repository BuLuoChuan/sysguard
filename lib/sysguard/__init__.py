# -*- coding: utf-8 -*-
"""SysGuard —— 面向 Linux 的系统管理 & 优化 GUI 工具。

以零第三方依赖（仅 Python 标准库 + Tkinter）实现，覆盖系统监控、
进程/服务、磁盘检修、USB 挂载/停转、网络、清理、内存、优化与安全审计。
GUI 以普通用户运行，所有需要 root 的操作统一通过 pkexec 调用特权入口
`sysguard-cli`，入口内部做命令白名单与设备守卫校验。
"""

__version__ = "1.2.1"
__app_name__ = "SysGuard"
__app_name_cn__ = "系统管家"