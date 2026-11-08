# -*- coding: utf-8 -*-
"""磁盘空间深度分析页：挂载点/大目录/大文件/inode。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from ...core import diskusage
from ...core.shell import human_bytes
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)

        widgets.heading(self.frame.inner, "磁盘空间深度分析")

        mnt_card = widgets.Card(self.frame.inner)
        ttk.Label(mnt_card, text="分区使用概况", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        self.mnt_tree = ttk.Treeview(
            mnt_card, columns=("fs", "size", "used", "avail", "pct", "mount"),
            show="headings", height=6)
        for c, t in (("fs", "文件系统"), ("size", "总大小"), ("used", "已用"),
                     ("avail", "可用"), ("pct", "使用率"), ("mount", "挂载点")):
            self.mnt_tree.heading(c, text=t)
        for c, w in (("fs", 120), ("size", 70), ("used", 70), ("avail", 70),
                     ("pct", 60), ("mount", 220)):
            self.mnt_tree.column(c, width=w, anchor="w")
        self.mnt_tree.pack(fill="x", padx=12, pady=6)

        scan_card = widgets.Card(self.frame.inner)
        ttk.Label(scan_card, text="大目录 / 大文件扫描", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        row = tk.Frame(scan_card, bg=widgets.THEME["card_bg"])
        row.pack(fill="x", padx=12, pady=8)
        ttk.Label(row, text="目录：", style="Card.TLabel").pack(side="left")
        self.path_var = tk.StringVar(value="/")
        self.path_box = ttk.Combobox(row, textvariable=self.path_var, width=40)
        self.path_box.pack(side="left")
        self.path_box["values"] = ["/"]
        ttk.Button(row, text="扫描大目录", command=self.scan_dirs).pack(side="left", padx=6)
        ttk.Button(row, text="扫描大文件", command=self.scan_files).pack(side="left")

        res_card = widgets.Card(self.frame.inner)
        head = tk.Frame(res_card, bg=widgets.THEME["card_bg"])
        head.pack(fill="x", padx=12, pady=(10, 0))
        self.res_title = ttk.Label(head, text="扫描结果", style="Sub.TLabel")
        self.res_title.pack(side="left")
        self.res_tree = ttk.Treeview(res_card, columns=("size", "path"),
                                     show="headings", height=12)
        self.res_tree.heading("size", text="大小")
        self.res_tree.heading("path", text="路径")
        self.res_tree.column("size", width=110, anchor="w")
        self.res_tree.column("path", width=560, anchor="w")
        self.res_tree.pack(fill="x", padx=12, pady=6)

        inode_card = widgets.Card(self.frame.inner)
        ttk.Label(inode_card, text="inode 使用", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        self.inode_tree = ttk.Treeview(
            inode_card, columns=("fs", "iused", "ifree", "ipct", "mount"),
            show="headings", height=5)
        for c, t in (("fs", "文件系统"), ("iused", "已用"), ("ifree", "可用"),
                     ("ipct", "使用率"), ("mount", "挂载点")):
            self.inode_tree.heading(c, text=t)
        for c, w in (("fs", 140), ("iused", 80), ("ifree", 80), ("ipct", 60),
                     ("mount", 220)):
            self.inode_tree.column(c, width=w, anchor="w")
        self.inode_tree.pack(fill="x", padx=12, pady=(0, 10))

        ttk.Button(self.frame.inner, text="刷新", command=self.refresh).pack(
            anchor="w", padx=18, pady=8)

        self.refresh()

    def refresh(self):
        self.mnt_tree.delete(*self.mnt_tree.get_children())
        mounts = diskusage.list_mounts()
        points = []
        for m in mounts:
            self.mnt_tree.insert("", "end", values=(
                m["fs"], m["size"], m["used"], m["avail"], m["pct"], m["mount"]))
            points.append(m["mount"])
        self.path_box["values"] = points or ["/"]
        self.inode_tree.delete(*self.inode_tree.get_children())
        for m in diskusage.inode_usage():
            self.inode_tree.insert("", "end", values=(
                m["fs"], m["iused"], m["ifree"], m["ipct"], m["mount"]))

    def _path(self):
        p = self.path_var.get().strip()
        if not p.startswith("/"):
            messagebox.showwarning("提示", "请输入绝对路径")
            return None
        return p

    def scan_dirs(self):
        p = self._path()
        if not p:
            return
        self.app.busy(True)
        try:
            rows = diskusage.top_dirs(p)
        finally:
            self.app.busy(False)
        self._show(rows, "大目录", lambda s: s)

    def scan_files(self):
        p = self._path()
        if not p:
            return
        self.app.busy(True)
        try:
            rows = diskusage.top_files(p)
        finally:
            self.app.busy(False)
        self._show(rows, "大文件（>100MB）", human_bytes)

    def _show(self, rows, title, fmt):
        self.res_title.config(text=f"扫描结果 · {title}")
        self.res_tree.delete(*self.res_tree.get_children())
        for r in rows:
            self.res_tree.insert("", "end", values=(fmt(r["size"]), r["path"]))