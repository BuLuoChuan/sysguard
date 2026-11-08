# -*- coding: utf-8 -*-
"""启动性能分析页。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...core import bootanalyze
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)

        widgets.heading(self.frame.inner, "启动性能分析")

        time_card = widgets.Card(self.frame.inner)
        ttk.Label(time_card, text="总启动时间", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        self.time_text = tk.StringVar(value="检测中…")
        ttk.Label(time_card, textvariable=self.time_text, style="Card.TLabel",
                  justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        blame_card = widgets.Card(self.frame.inner)
        head = tk.Frame(blame_card, bg=widgets.THEME["card_bg"])
        head.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(head, text="启动耗时 Top 服务", style="Sub.TLabel").pack(side="left")
        ttk.Button(head, text="刷新", command=self.refresh).pack(side="right")
        self.blame_tree = ttk.Treeview(blame_card, columns=("time", "unit"),
                                       show="headings", height=12)
        self.blame_tree.heading("time", text="耗时")
        self.blame_tree.heading("unit", text="服务单元")
        self.blame_tree.column("time", width=110, anchor="w")
        self.blame_tree.column("unit", width=520, anchor="w")
        self.blame_tree.pack(fill="x", padx=12, pady=6)

        chain_card = widgets.Card(self.frame.inner)
        ttk.Label(chain_card, text="关键启动路径", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        self.chain_text = tk.StringVar(value="")
        ttk.Label(chain_card, textvariable=self.chain_text,
                  style="CardMuted.TLabel", justify="left").pack(
            anchor="w", padx=12, pady=(0, 10))

        self.refresh()

    def refresh(self):
        self.app.busy(True)
        try:
            self.time_text.set(bootanalyze.boot_time() or "（无法读取）")
            self.blame_tree.delete(*self.blame_tree.get_children())
            for r in bootanalyze.blame():
                self.blame_tree.insert("", "end", values=(r["time"], r["unit"]))
            self.chain_text.set(bootanalyze.critical_chain() or "（无）")
        finally:
            self.app.busy(False)