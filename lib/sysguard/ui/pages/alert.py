# -*- coding: utf-8 -*-
"""资源阈值告警页：设置阈值、周期监测、超限弹窗/状态提示。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from ...core import alert
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)

        widgets.heading(self.frame.inner, "资源阈值告警")

        # 当前数值
        val_card = widgets.Card(self.frame.inner)
        head = tk.Frame(val_card, bg=widgets.THEME["card_bg"])
        head.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(head, text="当前资源占用", style="Sub.TLabel").pack(side="left")
        ttk.Button(head, text="立即检查", command=self.check_once).pack(side="right")
        self.val_text = tk.StringVar(value="点击“立即检查”开始")
        ttk.Label(val_card, textvariable=self.val_text, style="Card.TLabel",
                  justify="left").pack(anchor="w", padx=12, pady=(4, 10))

        # 阈值设置
        thr_card = widgets.Card(self.frame.inner)
        ttk.Label(thr_card, text="告警阈值（超过即提示）", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        self.thr_vars = {}
        grid = tk.Frame(thr_card, bg=widgets.THEME["card_bg"])
        grid.pack(fill="x", padx=12, pady=8)
        for i, (metric, label) in enumerate(alert.LABELS.items()):
            ttk.Label(grid, text=f"{label}：", style="Card.TLabel").grid(
                row=i, column=0, sticky="w", pady=3)
            var = tk.StringVar(value=str(alert.DEFAULTS[metric]))
            self.thr_vars[metric] = var
            ttk.Spinbox(grid, from_=1, to=100, width=6,
                        textvariable=var).grid(row=i, column=1, sticky="w")
            unit = "°C" if metric == "temp" else "%"
            ttk.Label(grid, text=unit, style="CardMuted.TLabel").grid(
                row=i, column=2, sticky="w", padx=4)

        # 监测控制
        ctrl = widgets.Card(self.frame.inner)
        row = tk.Frame(ctrl, bg=widgets.THEME["card_bg"])
        row.pack(fill="x", padx=12, pady=10)
        ttk.Label(row, text="监测间隔（秒）：", style="Card.TLabel").pack(side="left")
        self.interval_var = tk.StringVar(value="10")
        ttk.Spinbox(row, from_=3, to=600, width=6,
                    textvariable=self.interval_var).pack(side="left")
        self.toggle_btn = ttk.Button(row, text="开始监测",
                                     command=self.toggle)
        self.toggle_btn.pack(side="left", padx=8)

        self.result_card = widgets.Card(self.frame.inner)
        self.result_text = tk.StringVar(value="（尚未开始监测）")
        ttk.Label(self.result_card, textvariable=self.result_text,
                  style="CardMuted.TLabel", justify="left").pack(
            anchor="w", padx=12, pady=(10, 10))

        self._running = False
        self._after_id = None

    def _thresholds(self):
        thr = {}
        for metric, var in self.thr_vars.items():
            try:
                thr[metric] = float(var.get())
            except ValueError:
                thr[metric] = alert.DEFAULTS[metric]
        return thr

    def check_once(self):
        self.app.busy(True)
        try:
            res = alert.check(self._thresholds())
        finally:
            self.app.busy(False)
        self._show_result(res)

    def _show_result(self, res):
        vals = res["values"]
        lines = []
        for metric, value in vals.items():
            label = alert.LABELS.get(metric, metric)
            unit = "°C" if metric == "temp" else "%"
            lines.append(f"{label}：{value:.1f}{unit}")
        self.val_text.set("\n".join(lines))
        if res["alerts"]:
            msgs = "\n".join(a["message"] for a in res["alerts"])
            self.result_text.set("⚠ 告警：\n" + msgs)
            self.app.set_status("检测到资源超限")
        else:
            self.result_text.set("正常，未超过阈值")

    def toggle(self):
        if self._running:
            self._stop()
        else:
            self._start()

    def _start(self):
        self._running = True
        self.toggle_btn.configure(text="停止监测")
        self._poll()

    def _stop(self):
        self._running = False
        if self._after_id:
            self.app.root.after_cancel(self._after_id)
            self._after_id = None
        self.toggle_btn.configure(text="开始监测")

    def _poll(self):
        if not self._running:
            return
        res = alert.check(self._thresholds())
        self._show_result(res)
        if res["alerts"]:
            messagebox.showwarning(
                "资源告警",
                "\n".join(a["message"] for a in res["alerts"]),
                parent=self.app.root)
        try:
            interval = max(3, int(self.interval_var.get()))
        except ValueError:
            interval = 10
        if not self._running:
            return
        self._after_id = self.app.root.after(interval * 1000, self._poll)

    def on_hide(self):
        self._stop()