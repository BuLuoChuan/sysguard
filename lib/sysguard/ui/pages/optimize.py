# -*- coding: utf-8 -*-
"""系统优化页：自启服务审计、内核清理、电源/交换建议。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from ...core import optimize
from ...core.shell import human_bytes
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)

        widgets.heading(self.frame.inner, "系统优化")

        # 建议
        hint_card = widgets.Card(self.frame.inner)
        ttk.Label(hint_card, text="优化建议", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        self.hint_text = tk.StringVar()
        ttk.Label(hint_card, textvariable=self.hint_text,
                  style="Card.TLabel", justify="left").pack(
            anchor="w", padx=12, pady=(0, 10))

        # 开机自启服务
        svc_card = widgets.Card(self.frame.inner)
        head = tk.Frame(svc_card, bg=widgets.THEME["card_bg"])
        head.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(head, text="开机自启服务（systemd enabled）",
                  style="Sub.TLabel").pack(side="left")
        ttk.Button(head, text="禁用选中",
                   command=self.disable_service).pack(side="right")
        self.svc_tree = ttk.Treeview(svc_card, columns=("unit", "state"),
                                     show="headings", height=8)
        self.svc_tree.heading("unit", text="单元")
        self.svc_tree.heading("state", text="状态")
        self.svc_tree.column("unit", width=340, anchor="w")
        self.svc_tree.column("state", width=120, anchor="w")
        self.svc_tree.pack(fill="x", padx=12, pady=6)

        # 内核
        kcard = widgets.Card(self.frame.inner)
        ttk.Label(kcard, text="已安装内核", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        self.kernel_text = tk.StringVar()
        ttk.Label(kcard, textvariable=self.kernel_text,
                  style="CardMuted.TLabel", justify="left").pack(
            anchor="w", padx=18, pady=6)
        ttk.Button(kcard, text="卸载选中内核（谨慎）",
                   command=self.remove_kernel).pack(anchor="w", padx=12,
                                                   pady=(0, 10))

        ttk.Button(self.frame.inner, text="刷新",
                   command=self.refresh).pack(anchor="w", padx=18, pady=8)

        self.refresh()

    def refresh(self):
        s = optimize.summary()
        hints = s["hints"]
        self.hint_text.set("\n".join(f"· {h}" for h in hints) or "暂无需优化项")
        self.svc_tree.delete(*self.svc_tree.get_children())
        for r in s["enabled_services"]:
            self.svc_tree.insert("", "end", values=(r["unit"], r["state"]))
        kernels = s["kernels"]
        lines = []
        for k in kernels:
            mark = "（运行中）" if k["running"] else ""
            lines.append(f"{k['version']}{mark}")
        self.kernel_text.set("\n".join(lines) or "（无法读取内核信息）")

    def disable_service(self):
        sel = self.svc_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个服务")
            return
        unit = self.svc_tree.item(sel[0], "values")[0]
        if not messagebox.askyesno("确认", f"禁用自启服务 {unit}？\n\n"
                                            "这会阻止其开机自动运行（仍可手动启动）。"):
            return
        self.app.busy(True)
        try:
            rc, out, err = optimize.disable_service(unit)
        finally:
            self.app.busy(False)
        if rc != 0:
            messagebox.showwarning("失败", (err or out).strip())
        else:
            messagebox.showinfo("完成", f"已禁用 {unit} 自启")
        self.refresh()

    def remove_kernel(self):
        from ...core import cleanup
        kernels = optimize.installed_kernels()
        running = [k for k in kernels if k["running"]]
        removable = [k for k in kernels if not k["running"]]
        if not removable:
            messagebox.showinfo("提示", "没有可卸载的内核")
            return
        # 简单列表选择
        ver = ask_choice(self.app.root, "选择要卸载的内核",
                         [k["version"] for k in removable])
        if not ver:
            return
        if any(k["running"] for k in running if k["version"] == ver):
            messagebox.showwarning("禁止", "不能卸载当前运行内核")
            return
        if not messagebox.askyesno("确认", f"卸载内核 {ver}？"):
            return
        self.app.busy(True)
        try:
            ok, msg = cleanup.remove_kernel(ver)
        finally:
            self.app.busy(False)
        messagebox.showinfo("结果", msg)
        self.refresh()


def ask_choice(parent, title, options):
    """简单单选对话框，返回所选字符串或 None。"""
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("360x300")
    win.transient(parent)
    win.grab_set()
    var = tk.StringVar()
    lb = tk.Listbox(win)
    lb.pack(fill="both", expand=True, padx=10, pady=10)
    for o in options:
        lb.insert("end", o)
    result = []

    def choose():
        sel = lb.curselection()
        if sel:
            result.append(options[sel[0]])
        win.destroy()

    ttk.Button(win, text="确定", command=choose).pack(pady=(0, 10))
    parent.wait_window(win)
    return result[0] if result else None