# -*- coding: utf-8 -*-
"""主窗口：左侧导航 + 内容区，装载 9 个功能页。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..config import APP_NAME_CN, APP_VERSION, THEME
from . import widgets
from .pages import (dashboard, processes, disks, usb, network, cleanup,
                    memory, optimize, security, mirrors)


PAGES = [
    ("系统概览", dashboard.Page),
    ("进程服务", processes.Page),
    ("磁盘管理", disks.Page),
    ("USB 设备", usb.Page),
    ("网络优化", network.Page),
    ("垃圾清理", cleanup.Page),
    ("内存交换", memory.Page),
    ("系统优化", optimize.Page),
    ("镜像源", mirrors.Page),
    ("安全中心", security.Page),
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

        self.sidebar = tk.Frame(body, bg=THEME["bg"], width=150)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

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
        for idx, (label, cls) in enumerate(PAGES):
            btn = ttk.Button(self.sidebar, text=label, style="Sidebar.TButton",
                             command=lambda i=idx, c=cls: self.show_page(i, c))
            btn.pack(fill="x")
            self.nav_buttons[idx] = btn

        self.show_page(0, PAGES[0][1])

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
        for w in self.content.winfo_children():
            w.destroy()
        cls(self.content, self)
        self.root.configure(cursor="")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())