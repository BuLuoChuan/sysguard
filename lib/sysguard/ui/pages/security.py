# -*- coding: utf-8 -*-
"""安全中心页（火绒式，不做防病毒）：防火墙/端口审计/可疑进程/文件粉碎。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ...core import security
from ...core.shell import human_bytes
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)

        widgets.heading(self.frame.inner, "安全中心")

        # 防火墙
        fw_card = widgets.Card(self.frame.inner)
        head = tk.Frame(fw_card, bg=widgets.THEME["card_bg"])
        head.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(head, text="防火墙 (ufw)", style="Sub.TLabel").pack(
            side="left")
        self.fw_var = tk.StringVar(value="检测中…")
        ttk.Label(fw_card, textvariable=self.fw_var,
                  style="Card.TLabel").pack(anchor="w", padx=12, pady=6)
        row = tk.Frame(fw_card, bg=widgets.THEME["card_bg"])
        row.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(row, text="启用", command=self.fw_enable).pack(side="left")
        ttk.Button(row, text="停用", command=self.fw_disable).pack(
            side="left", padx=6)
        # 放行端口
        port_row = tk.Frame(fw_card, bg=widgets.THEME["card_bg"])
        port_row.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Label(port_row, text="放行端口 (如 22 或 443/tcp)：",
                  style="Card.TLabel").pack(side="left")
        self.port_var = tk.StringVar()
        ttk.Entry(port_row, textvariable=self.port_var,
                  width=12).pack(side="left", padx=4)
        ttk.Button(port_row, text="放行", command=self.fw_allow).pack(
            side="left", padx=2)
        ttk.Button(port_row, text="拒绝", command=self.fw_deny).pack(
            side="left", padx=2)

        # 监听端口
        port_card = widgets.Card(self.frame.inner)
        ttk.Label(port_card, text="监听端口审计", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        self.port_tree = ttk.Treeview(port_card,
                                      columns=("proto", "addr", "port", "proc"),
                                      show="headings", height=8)
        for c, h in zip(("proto", "addr", "port", "proc"),
                        ("协议", "地址", "端口", "进程")):
            self.port_tree.heading(c, text=h)
            self.port_tree.column(c, width=100, anchor="w")
        self.port_tree.column("proc", width=300)
        self.port_tree.pack(fill="x", padx=12, pady=6)

        # 可疑进程
        susp_card = widgets.Card(self.frame.inner)
        ttk.Label(susp_card, text="可疑进程（高 CPU / 高内存）",
                  style="Sub.TLabel").pack(anchor="w", padx=12, pady=(10, 0))
        self.susp_text = tk.StringVar()
        ttk.Label(susp_card, textvariable=self.susp_text,
                  style="Card.TLabel", justify="left").pack(
            anchor="w", padx=12, pady=(0, 10))

        # 文件粉碎
        shred_card = widgets.Card(self.frame.inner)
        ttk.Label(shred_card, text="文件粉碎（不可恢复）",
                  style="Sub.TLabel").pack(anchor="w", padx=12, pady=(10, 0))
        srow = tk.Frame(shred_card, bg=widgets.THEME["card_bg"])
        srow.pack(fill="x", padx=12, pady=(0, 10))
        self.path_var = tk.StringVar()
        ttk.Entry(srow, textvariable=self.path_var,
                  width=40).pack(side="left")
        ttk.Button(srow, text="浏览…", command=self.pick_file).pack(
            side="left", padx=4)
        ttk.Button(srow, text="粉碎", command=self.shred).pack(
            side="left", padx=4)

        ttk.Button(self.frame.inner, text="刷新",
                   command=self.refresh).pack(anchor="w", padx=18, pady=8)

        self.refresh()

    def refresh(self):
        fw = security.ufw_status()
        if not fw["installed"]:
            self.fw_var.set("ufw 未安装（请执行 sudo apt install ufw）")
        else:
            self.fw_var.set("防火墙已启用" if fw["active"] else "防火墙已停用")

        self.port_tree.delete(*self.port_tree.get_children())
        for p in security.listening_ports():
            self.port_tree.insert("", "end", values=(
                p["proto"], p["address"], p["port"], p["process"]))

        susp = security.suspicious_processes()
        if susp:
            lines = [f"{p['pid']} {p['user']} CPU {p['cpu']:.0f}% "
                     f"内存 {p['mem']:.0f}% {p['comm']}" for p in susp]
        else:
            lines = ["当前无可疑进程"]
        self.susp_text.set("\n".join(lines))

    def fw_enable(self):
        self._fw(security.ufw_enable, "启用")

    def fw_disable(self):
        self._fw(security.ufw_disable, "停用")

    def fw_allow(self):
        self._fw(lambda: security.ufw_allow(self.port_var.get().strip()), "放行")

    def fw_deny(self):
        self._fw(lambda: security.ufw_deny(self.port_var.get().strip()), "拒绝")

    def _fw(self, action, label):
        self.app.busy(True)
        try:
            ok, msg = action()
        finally:
            self.app.busy(False)
        if not ok:
            messagebox.showwarning("失败", msg)
        else:
            messagebox.showinfo("完成", f"防火墙「{label}」操作完成")
        self.refresh()

    def pick_file(self):
        path = filedialog.askopenfilename(title="选择要粉碎的文件")
        if path:
            self.path_var.set(path)

    def shred(self):
        path = self.path_var.get().strip()
        if not path:
            messagebox.showinfo("提示", "请先选择文件")
            return
        if not messagebox.askyesno("警告", f"粉碎后文件不可恢复，确定粉碎：\n{path}"):
            return
        self.app.busy(True)
        try:
            ok, msg = security.shred(path)
        finally:
            self.app.busy(False)
        messagebox.showinfo("结果", "文件已粉碎" if ok else f"失败：{msg}")