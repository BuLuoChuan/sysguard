# -*- coding: utf-8 -*-
"""系统概览：实时仪表盘。"""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from ...core import sysinfo
from ...core.shell import human_bytes
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.root = app.root
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)
        self._alive = True

        widgets.heading(self.frame.inner, "系统概览")

        # 基本信息行
        info = sysinfo.os_info()
        info_lbl = ttk.Label(
            self.frame.inner,
            text=f"系统：{info['pretty']}  ·  架构：{sysinfo.cpu_info()['arch']}",
            style="Muted.TLabel")
        info_lbl.pack(anchor="w", padx=18, pady=(0, 6))

        # 指标卡片区（双列）
        grid = widgets.two_col(self.frame.inner)
        self.cpu_card, self.cpu_var = widgets.metric_card(grid, "CPU 使用率", "%")
        self.cpu_card.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)
        self.mem_card, self.mem_var = widgets.metric_card(grid, "内存使用率", "%")
        self.mem_card.grid(row=0, column=1, sticky="nsew", padx=6, pady=4)
        self.load_card, self.load_var = widgets.metric_card(grid, "负载 (1/5/15)")
        self.load_card.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        self.up_card, self.up_var = widgets.metric_card(grid, "运行时间")
        self.up_card.grid(row=1, column=1, sticky="nsew", padx=6, pady=4)
        self.rx_card, self.rx_var = widgets.metric_card(grid, "下行速率", "B/s")
        self.rx_card.grid(row=2, column=0, sticky="nsew", padx=6, pady=4)
        self.tx_card, self.tx_var = widgets.metric_card(grid, "上行速率", "B/s")
        self.tx_card.grid(row=2, column=1, sticky="nsew", padx=6, pady=4)
        self.temp_card, self.temp_var = widgets.metric_card(grid, "最高温度", "°C")
        self.temp_card.grid(row=3, column=0, sticky="nsew", padx=6, pady=4)
        self.swap_card, self.swap_var = widgets.metric_card(grid, "交换使用率", "%")
        self.swap_card.grid(row=3, column=1, sticky="nsew", padx=6, pady=4)

        # 磁盘使用卡片
        ttk.Label(self.frame.inner, text="磁盘使用",
                  style="Title.TLabel").pack(fill="x", padx=16, pady=(12, 4))
        self.disk_box = tk.Frame(self.frame.inner, bg=widgets.THEME["bg"])
        self.disk_box.pack(fill="x", padx=10)

        self.refresh()
        self._schedule()

    def _schedule(self):
        if self._alive and self.frame.winfo_exists():
            self.root.after(2000, self._tick)

    def _tick(self):
        if not self._alive or not self.frame.winfo_exists():
            return
        self.refresh()
        self._schedule()

    def destroy(self):
        self._alive = False
        self.frame.destroy()

    def refresh(self):
        try:
            d = sysinfo.dashboard()
        except Exception as e:
            self.app.set_status(f"获取概览失败：{e}")
            return
        self.cpu_var.set(f"{d['cpu']['usage']:.0f}")
        self.mem_var.set(f"{d['memory']['percent']:.0f}")
        ld = d["load"]
        self.load_var.set(f"{ld['1']:.2f} / {ld['5']:.2f} / {ld['15']:.2f}")
        up = int(d["uptime"])
        h, m, s = up // 3600, (up % 3600) // 60, up % 60
        self.up_var.set(f"{h}时{m:02d}分")
        self.rx_var.set(f"{d['network']['rx_rate']:,}")
        self.tx_var.set(f"{d['network']['tx_rate']:,}")
        self.temp_var.set(f"{d['temperature']['max']:.0f}")
        self.swap_var.set(f"{d['swap']['percent']:.0f}")

        for w in self.disk_box.winfo_children():
            w.destroy()
        if not d["disks"]:
            ttk.Label(self.disk_box, text="无挂载文件系统",
                      style="Muted.TLabel").pack(anchor="w", padx=8)
        for row in d["disks"][:8]:
            card = tk.Frame(self.disk_box, bg=widgets.THEME["card_bg"],
                            highlightbackground="#e0e0e0",
                            highlightthickness=1)
            card.pack(fill="x", pady=3)
            head = tk.Frame(card, bg=widgets.THEME["card_bg"])
            head.pack(fill="x", padx=10, pady=(6, 0))
            ttk.Label(head, text=row["mountpoint"], style="Card.TLabel").pack(
                side="left")
            ttk.Label(head,
                      text=f"{human_bytes(row['used'])} / "
                           f"{human_bytes(row['size'])}", style="CardMuted.TLabel").pack(
                side="right")
            bar = ttk.Progressbar(card, maximum=100, value=row["percent"],
                                  style="TProgressbar")
            bar.pack(fill="x", padx=10, pady=(2, 8))
        self.app.set_status("概览已刷新")