# -*- coding: utf-8 -*-
"""定时任务审计页：systemd timer + cron。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...core import tasks
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)

        widgets.heading(self.frame.inner, "定时任务审计")

        timer_card = widgets.Card(self.frame.inner)
        head = tk.Frame(timer_card, bg=widgets.THEME["card_bg"])
        head.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(head, text="systemd 定时器", style="Sub.TLabel").pack(side="left")
        ttk.Button(head, text="刷新", command=self.refresh).pack(side="right")
        self.timer_tree = ttk.Treeview(
            timer_card, columns=("next", "unit", "act"), show="headings", height=8)
        self.timer_tree.heading("next", text="下次触发")
        self.timer_tree.heading("unit", text="计时器单元")
        self.timer_tree.heading("act", text="触发目标")
        self.timer_tree.column("next", width=180, anchor="w")
        self.timer_tree.column("unit", width=260, anchor="w")
        self.timer_tree.column("act", width=220, anchor="w")
        self.timer_tree.pack(fill="x", padx=12, pady=6)

        cron_card = widgets.Card(self.frame.inner)
        ttk.Label(cron_card, text="系统 cron 任务（/etc/crontab + /etc/cron.d）",
                  style="Sub.TLabel").pack(anchor="w", padx=12, pady=(10, 0))
        self.cron_tree = ttk.Treeview(
            cron_card, columns=("schedule", "user", "command", "source"),
            show="headings", height=12)
        self.cron_tree.heading("schedule", text="时间表")
        self.cron_tree.heading("user", text="用户")
        self.cron_tree.heading("command", text="命令")
        self.cron_tree.heading("source", text="来源")
        self.cron_tree.column("schedule", width=140, anchor="w")
        self.cron_tree.column("user", width=80, anchor="w")
        self.cron_tree.column("command", width=340, anchor="w")
        self.cron_tree.column("source", width=120, anchor="w")
        self.cron_tree.pack(fill="x", padx=12, pady=(0, 10))

        self.refresh()

    def refresh(self):
        self.timer_tree.delete(*self.timer_tree.get_children())
        for r in tasks.systemd_timers():
            self.timer_tree.insert("", "end", values=(
                r["next"], r["unit"], r["activates"]))
        self.cron_tree.delete(*self.cron_tree.get_children())
        for r in tasks.cron_jobs():
            self.cron_tree.insert("", "end", values=(
                r["schedule"], r["user"], r["command"], r["source"]))