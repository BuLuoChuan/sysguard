# -*- coding: utf-8 -*-
"""系统优化页：自启服务（含说明/开关/延时）、内核清理、建议。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ...core import optimize
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)

        widgets.heading(self.frame.inner, "系统优化")

        # 说明语言切换
        self.lang = "zh"
        lang_row = tk.Frame(self.frame.inner, bg=widgets.THEME["bg"])
        lang_row.pack(fill="x", padx=16, pady=(0, 4))
        ttk.Label(lang_row, text="说明语言：", style="Muted.TLabel").pack(side="left")
        self.lang_btn = ttk.Button(lang_row, text="中文 / English",
                                   command=self._toggle_lang)
        self.lang_btn.pack(side="left", padx=(2, 0))

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
        ttk.Label(head, text="开机自启服务（systemd）", style="Sub.TLabel").pack(side="left")
        ttk.Button(head, text="刷新", command=self.refresh).pack(side="right")
        self.svc_tree = ttk.Treeview(
            svc_card, columns=("unit", "desc", "delay"), show="headings", height=10)
        self.svc_tree.heading("unit", text="服务单元")
        self.svc_tree.heading("desc", text="说明")
        self.svc_tree.heading("delay", text="启动方式")
        self.svc_tree.column("unit", width=260, anchor="w")
        self.svc_tree.column("desc", width=320, anchor="w")
        self.svc_tree.column("delay", width=90, anchor="w")
        self.svc_tree.pack(fill="x", padx=12, pady=6)

        brow = tk.Frame(svc_card, bg=widgets.THEME["card_bg"])
        brow.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(brow, text="禁用自启", command=self.disable_service).pack(side="left")
        ttk.Button(brow, text="启用自启", command=self.enable_service).pack(side="left", padx=6)
        ttk.Button(brow, text="延时启动…", command=self.delay_service).pack(side="left")
        ttk.Button(brow, text="取消延时", command=self.cancel_delay).pack(side="left", padx=6)

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

        self.refresh()

    def _toggle_lang(self):
        self.lang = "en" if self.lang == "zh" else "zh"
        self.lang_btn.config(text="English" if self.lang == "zh" else "中文")
        self.refresh()

    def refresh(self):
        s = optimize.summary(lang=self.lang)
        hints = s["hints"]
        empty = "暂无需优化项" if self.lang == "zh" else "No optimization needed"
        self.hint_text.set("\n".join(f"· {h}" for h in hints) or empty)
        self.svc_tree.delete(*self.svc_tree.get_children())
        for r in s["enabled_services"]:
            mode = "延时启动" if r["delayed"] else "开机自启"
            self.svc_tree.insert("", "end", values=(
                r["unit"], r["description"] or "—", mode))
        kernels = s["kernels"]
        lines = []
        for k in kernels:
            mark = "（运行中）" if k["running"] else ""
            lines.append(f"{k['version']}{mark}")
        self.kernel_text.set("\n".join(lines) or "（无法读取内核信息）")

    def _selected_unit(self):
        sel = self.svc_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个服务")
            return None
        return self.svc_tree.item(sel[0], "values")[0]

    def _run_op(self, name, fn, msg):
        unit = self._selected_unit()
        if not unit:
            return
        if not messagebox.askyesno("确认", f"{msg} {unit}？"):
            return
        self.app.busy(True)
        try:
            ok, err = fn(unit)
        finally:
            self.app.busy(False)
        if ok:
            self.app.set_status(f"{name} {unit} 完成")
        else:
            messagebox.showwarning("失败", err or "操作失败")
        self.refresh()

    def enable_service(self):
        self._run_op("启用自启", optimize.enable_service, "启用开机自启：")

    def disable_service(self):
        self._run_op("禁用自启", optimize.disable_service, "禁用开机自启：")

    def delay_service(self):
        unit = self._selected_unit()
        if not unit:
            return
        seconds = simpledialog.askinteger(
            "延时启动", f"开机后延时多少秒启动 {unit}？\n（0 表示取消延时）",
            minvalue=0, maxvalue=86400, parent=self.app.root)
        if seconds is None:
            return
        self.app.busy(True)
        try:
            ok, err = optimize.delay_start(unit, seconds)
        finally:
            self.app.busy(False)
        if ok:
            self.app.set_status(f"已设置 {unit} 延时 {seconds}s")
        else:
            messagebox.showwarning("失败", err or "设置失败")
        self.refresh()

    def cancel_delay(self):
        unit = self._selected_unit()
        if not unit:
            return
        self.app.busy(True)
        try:
            ok, err = optimize.cancel_delay(unit)
        finally:
            self.app.busy(False)
        if ok:
            self.app.set_status(f"已取消 {unit} 延时")
        else:
            messagebox.showwarning("失败", err or "取消失败")
        self.refresh()

    def remove_kernel(self):
        from ...core import cleanup
        kernels = optimize.installed_kernels()
        running = [k for k in kernels if k["running"]]
        removable = [k for k in kernels if not k["running"]]
        if not removable:
            messagebox.showinfo("提示", "没有可卸载的内核")
            return
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