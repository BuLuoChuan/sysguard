# -*- coding: utf-8 -*-
"""主窗口：左侧导航 + 内容区，装载功能页。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..config import APP_NAME_CN, APP_VERSION, THEME
from . import widgets
from .pages import (dashboard, processes, disks, diskusage, usb, network,
                    cleanup, pkgfix, memory, optimize, bootanalyze, tasks,
                    power, alert, diagnostics, mirrors, security, i18n)


# 左侧导航：按大类分组（参考成品系统管家/火绒式的分类合并），组内再列子项。
GROUPS = [
    ("首页", [
        ("系统概览", dashboard.Page),
    ]),
    ("进程与启动", [
        ("进程服务", processes.Page),
        ("启动分析", bootanalyze.Page),
        ("定时任务", tasks.Page),
    ]),
    ("磁盘与管理", [
        ("磁盘检修", disks.Page),
        ("磁盘空间", diskusage.Page),
        ("USB 设备", usb.Page),
    ]),
    ("网络", [
        ("网络优化", network.Page),
        ("镜像源", mirrors.Page),
    ]),
    ("清理与优化", [
        ("垃圾清理", cleanup.Page),
        ("软件修复", pkgfix.Page),
        ("内存交换", memory.Page),
        ("系统优化", optimize.Page),
    ]),
    ("电源与告警", [
        ("电源电池", power.Page),
        ("资源告警", alert.Page),
    ]),
    ("安全与诊断", [
        ("安全中心", security.Page),
        ("日志诊断", diagnostics.Page),
        ("中文环境", i18n.Page),
    ]),
]


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME_CN} · SysGuard v{APP_VERSION}")
        self.root.geometry("1120x720")
        self.root.minsize(960, 600)
        widgets.apply_theme(root)

        top = tk.Frame(root, bg=THEME["accent"])
        top.pack(fill="x")
        tk.Label(top, text=f"  {APP_NAME_CN} · SysGuard", bg=THEME["accent"],
                 fg="#ffffff", font=(widgets.FONT_SANS, 13, "bold")).pack(
            side="left", padx=12, pady=8)

        body = tk.Frame(root, bg=THEME["bg"])
        body.pack(fill="both", expand=True)

        # 左侧导航（可滚动，容纳较多模块）
        self.sidebar = tk.Frame(body, bg=THEME["bg"], width=150)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.side_canvas = tk.Canvas(self.sidebar, bg=THEME["bg"],
                                     highlightthickness=0, width=150)
        self.side_vsb = ttk.Scrollbar(self.sidebar, orient="vertical",
                                      command=self.side_canvas.yview)
        self.side_canvas.configure(yscrollcommand=self.side_vsb.set)
        self.side_vsb.pack(side="right", fill="y")
        self.side_canvas.pack(side="left", fill="both", expand=True)
        self.side_inner = tk.Frame(self.side_canvas, bg=THEME["bg"])
        self._side_win = self.side_canvas.create_window(
            (0, 0), window=self.side_inner, anchor="nw")
        self.side_inner.bind("<Configure>", lambda e: self.side_canvas.configure(
            scrollregion=self.side_canvas.bbox("all")))
        self.side_canvas.bind("<Configure>", lambda e: self.side_canvas.itemconfigure(
            self._side_win, width=e.width))

        self.content = tk.Frame(body, bg=THEME["bg"])
        self.content.pack(side="left", fill="both", expand=True)

        self.status = tk.StringVar(value="就绪")
        bar = tk.Frame(root, bg="#e8eaed")
        bar.pack(fill="x", side="bottom")
        tk.Label(bar, textvariable=self.status, bg="#e8eaed",
                 fg="#5f6368", anchor="w",
                 font=(widgets.FONT_SANS, 9)).pack(fill="x", padx=10, pady=3)

        self.nav_buttons = {}
        self.current = None
        self.current_page = None
        self._flat = []
        for group_title, items in GROUPS:
            tk.Label(self.side_inner, text=group_title, bg=THEME["bg"],
                     fg="#9aa0a6", anchor="w",
                     font=(widgets.FONT_SANS, 9, "bold")).pack(
                fill="x", padx=12, pady=(9, 2))
            for label, cls in items:
                idx = len(self._flat)
                self._flat.append((label, cls))
                btn = ttk.Button(self.side_inner, text=label,
                                 style="Sidebar.TButton",
                                 command=lambda i=idx, c=cls: self.show_page(i, c))
                btn.pack(fill="x", padx=(8, 0))
                self.nav_buttons[idx] = btn

        self.show_page(0, self._flat[0][1])

    def set_status(self, text):
        self.status.set(text)
        self.root.update_idletasks()

    def busy(self, on=True):
        self.root.configure(cursor="watch" if on else "")
        self.root.update_idletasks()

    def show_page(self, idx, cls):
        if self.current is not None:
            self.nav_buttons[self.current].state(["!pressed"])
        self.nav_buttons[idx].state(["pressed"])
        self.current = idx
        if self.current_page is not None and hasattr(self.current_page, "on_hide"):
            self.current_page.on_hide()
        for w in self.content.winfo_children():
            w.destroy()
        self.current_page = cls(self.content, self)
        self.root.configure(cursor="")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())