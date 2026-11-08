# -*- coding: utf-8 -*-
"""软件包修复页：修复损坏依赖、孤儿包、版本锁定。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from ...core import pkgfix, cleanup
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)

        widgets.heading(self.frame.inner, "软件包修复（Debian/Ubuntu）")

        # 依赖状态
        card = widgets.Card(self.frame.inner)
        head = tk.Frame(card, bg=widgets.THEME["card_bg"])
        head.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(head, text="依赖状态", style="Sub.TLabel").pack(side="left")
        ttk.Button(head, text="刷新", command=self.refresh).pack(side="right")
        self.status_text = tk.StringVar(value="检测中…")
        ttk.Label(card, textvariable=self.status_text, style="Card.TLabel",
                  justify="left").pack(anchor="w", padx=12, pady=8)
        ttk.Button(card, text="修复损坏/半装依赖",
                   command=self.fix_broken).pack(anchor="w", padx=12, pady=(0, 10))

        # 孤儿包
        orph_card = widgets.Card(self.frame.inner)
        head = tk.Frame(orph_card, bg=widgets.THEME["card_bg"])
        head.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(head, text="可自动移除的孤立依赖", style="Sub.TLabel").pack(side="left")
        ttk.Button(head, text="检测", command=self.scan_orphans).pack(side="right")
        self.orph_text = tk.StringVar(value="（未检测）")
        ttk.Label(orph_card, textvariable=self.orph_text, style="Card.TLabel",
                  justify="left").pack(anchor="w", padx=12, pady=8)
        ttk.Button(orph_card, text="自动移除孤立包",
                   command=self.autoremove).pack(anchor="w", padx=12, pady=(0, 10))

        self.refresh()

    def refresh(self):
        st = pkgfix.status()
        parts = []
        if st["broken"]:
            parts.append("发现损坏/半装包：\n" +
                         "\n".join(f"· {b}" for b in st["broken"]))
        else:
            parts.append("未发现损坏或半装的包。")
        if st["held"]:
            parts.append("版本锁定(hold)的包：" + "、".join(st["held"]))
        self.status_text.set("\n\n".join(parts))

    def fix_broken(self):
        if not messagebox.askyesno("确认", "执行 dpkg --configure -a 与 "
                                           "apt --fix-broken 修复依赖？"):
            return
        self.app.busy(True)
        try:
            ok, data, err = pkgfix.fix_broken()
        finally:
            self.app.busy(False)
        if ok:
            self.app.set_status("依赖修复完成")
            messagebox.showinfo("完成", "依赖修复完成")
        else:
            messagebox.showwarning("失败", err or "修复失败")
        self.refresh()

    def scan_orphans(self):
        self.app.busy(True)
        try:
            ok, data, err = pkgfix.orphans()
        finally:
            self.app.busy(False)
        if ok:
            orphans = (data or {}).get("orphans", [])
            self.orph_text.set("\n".join(f"· {o}" for o in orphans)
                               or "（无可移除的孤立包）")
        else:
            self.orph_text.set(err or "检测失败")

    def autoremove(self):
        if not messagebox.askyesno("确认", "执行 apt-get autoremove 移除孤立依赖？"):
            return
        self.app.busy(True)
        try:
            ok, msg = cleanup.clean_autoremove()
        finally:
            self.app.busy(False)
        messagebox.showinfo("结果", msg)
        self.scan_orphans()