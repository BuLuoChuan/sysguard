# -*- coding: utf-8 -*-
"""垃圾清理页：先估算空间，再逐项确认清理。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from ...core import cleanup
from ...core.shell import human_bytes
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)

        widgets.heading(self.frame.inner, "垃圾清理")
        tip = ttk.Label(self.frame.inner, style="Muted.TLabel",
                        text="先估算各项目占用空间，确认后再执行清理；清理动作需授权。")
        tip.pack(anchor="w", padx=18, pady=(0, 4))

        self.rows = {}
        self._add_row("apt_cache", "APT 下载缓存", "清空缓存",
                      cleanup.clean_apt_cache)
        self._add_row("autoclean", "APT autoclean", "执行 autoclean",
                      cleanup.clean_apt_autoclean)
        self._add_row("autoremove", "不再需要的软件包 (autoremove)",
                      "自动清理", cleanup.clean_autoremove)
        self._add_row("journal", "systemd 日志 (journal)", "清理至 100M",
                      lambda: cleanup.clean_journal("100M"))
        self._add_row("tmp", "临时文件 (/tmp)", "清理", cleanup.clean_tmp)
        self._add_row("thumbnails", "缩略图缓存", "清理",
                      cleanup.clean_thumbnails)

        # 旧内核区
        kcard = widgets.Card(self.frame.inner)
        ttk.Label(kcard, text="旧内核镜像", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        self.kernel_text = tk.StringVar(value="计算中…")
        ttk.Label(kcard, textvariable=self.kernel_text,
                  style="CardMuted.TLabel", justify="left").pack(
            anchor="w", padx=12, pady=6)
        ttk.Button(kcard, text="刷新旧内核",
                   command=self.refresh_kernels).pack(anchor="w", padx=12,
                                                     pady=(0, 6))
        self.kernel_tree = ttk.Treeview(kcard, columns=("ver",),
                                        show="headings", height=5)
        self.kernel_tree.heading("ver", text="内核版本")
        self.kernel_tree.column("ver", width=300, anchor="w")
        self.kernel_tree.pack(fill="x", padx=12, pady=(0, 6))
        ttk.Button(kcard, text="卸载选中内核（谨慎）",
                   command=self.remove_kernel).pack(anchor="w", padx=12,
                                                   pady=(0, 10))

        ttk.Button(self.frame.inner, text="重新估算空间",
                   command=self.refresh).pack(anchor="w", padx=18, pady=8)

        self.refresh()

    def _add_row(self, key, title, btn_text, action):
        card = widgets.Card(self.frame.inner)
        row = tk.Frame(card, bg=widgets.THEME["card_bg"])
        row.pack(fill="x", padx=12, pady=10)
        ttk.Label(row, text=title, style="Card.TLabel").pack(side="left")
        var = tk.StringVar(value="…")
        ttk.Label(row, textvariable=var, style="CardMuted.TLabel").pack(
            side="left", padx=10)
        ttk.Button(row, text=btn_text,
                   command=lambda a=action, k=key: self._run(k, a)).pack(
            side="right")
        self.rows[key] = var

    def refresh(self):
        self.app.set_status("正在估算空间…")
        m = cleanup.measure()
        self.rows["apt_cache"].set(human_bytes(m["apt_cache"]))
        self.rows["autoclean"].set(human_bytes(m["apt_lists"]))
        ar = m["autoremove"]
        self.rows["autoremove"].set(
            f"{ar['packages']} 个包 / {human_bytes(ar['freed_bytes'])}")
        self.rows["journal"].set(human_bytes(m["journal"]))
        self.rows["tmp"].set(human_bytes(m["tmp"]))
        self.rows["thumbnails"].set(human_bytes(m["thumbnails"]))
        self.refresh_kernels()
        self.app.set_status("空间估算完成")

    def refresh_kernels(self):
        self.kernel_tree.delete(*self.kernel_tree.get_children())
        for ver in cleanup.old_kernels():
            self.kernel_tree.insert("", "end", values=(ver,))
        n = cleanup.old_kernels()
        self.kernel_text.set(f"发现 {len(n)} 个可卸载的旧内核（不含当前运行内核）")

    def _run(self, key, action):
        title = next((t for k, t in
                      [("apt_cache", "清空 APT 缓存"),
                       ("autoclean", "apt autoclean"),
                       ("autoremove", "autoremove"),
                       ("journal", "清理 journal"),
                       ("tmp", "清理 /tmp"),
                       ("thumbnails", "清理缩略图")] if k == key),
                     "清理")
        if not messagebox.askyesno("确认", f"确定执行「{title}」？"):
            return
        self.app.busy(True)
        try:
            ok, msg = action()
        finally:
            self.app.busy(False)
        messagebox.showinfo("结果", msg)
        self.refresh()

    def remove_kernel(self):
        sel = self.kernel_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选中一个旧内核")
            return
        ver = self.kernel_tree.item(sel[0], "values")[0]
        if not messagebox.askyesno("确认", f"确定卸载内核 {ver}？\n\n"
                                            "此操作不可逆，请确认这不是当前运行内核。"):
            return
        self.app.busy(True)
        try:
            ok, msg = cleanup.remove_kernel(ver)
        finally:
            self.app.busy(False)
        messagebox.showinfo("结果", msg)
        self.refresh()