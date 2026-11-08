# -*- coding: utf-8 -*-
"""电源与电池页：电池健康、能效三档切换。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from ...core import power
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)

        widgets.heading(self.frame.inner, "电源与电池")

        bat_card = widgets.Card(self.frame.inner)
        ttk.Label(bat_card, text="电池健康", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        self.bat_text = tk.StringVar(value="检测中…")
        ttk.Label(bat_card, textvariable=self.bat_text, style="Card.TLabel",
                  justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        # 能效三档
        prof_card = widgets.Card(self.frame.inner)
        head = tk.Frame(prof_card, bg=widgets.THEME["card_bg"])
        head.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(head, text="能效模式（power-profiles-daemon）",
                  style="Sub.TLabel").pack(side="left")
        ttk.Button(head, text="刷新", command=self.refresh).pack(side="right")
        self.prof_text = tk.StringVar(value="")
        ttk.Label(prof_card, textvariable=self.prof_text, style="Card.TLabel",
                  justify="left").pack(anchor="w", padx=12, pady=8)
        brow = tk.Frame(prof_card, bg=widgets.THEME["card_bg"])
        brow.pack(fill="x", padx=12, pady=(0, 10))
        for p, label in (("performance", "高性能"), ("balanced", "平衡"),
                         ("power-saver", "省电")):
            ttk.Button(brow, text=label,
                       command=lambda pp=p: self.set_profile(pp)).pack(side="left", padx=4)

        self.refresh()

    def refresh(self):
        b = power.battery_info()
        if b["present"]:
            parts = []
            if b["model"]:
                parts.append(f"型号：{b['model']}")
            if b["percentage"] is not None:
                parts.append(f"电量：{b['percentage']}%")
            if b["state"]:
                parts.append(f"状态：{b['state']}")
            if b["health"] is not None:
                parts.append(f"健康度：{b['health']}%")
            self.bat_text.set("\n".join(parts) or "（电池信息未知）")
        else:
            self.bat_text.set("未检测到电池（可能是台式机或无电池设备）")

        ac = power.ac_state()
        if power.has_daemon():
            cur = power.current_profile()
            lines = []
            for r in power.profiles_status():
                mark = " ← 当前" if r["current"] else ""
                lines.append(f"{r['label']}（{r['profile']}）{mark}")
            if ac:
                lines.insert(0, f"供电状态：{ac}")
            self.prof_text.set("\n".join(lines))
        else:
            self.prof_text.set("未安装 power-profiles-daemon，无法切换能效模式。\n"
                               "可安装：sudo apt install power-profiles-daemon")

    def set_profile(self, profile):
        self.app.busy(True)
        try:
            ok, msg = power.set_profile(profile)
        finally:
            self.app.busy(False)
        if ok:
            self.app.set_status(f"已切换能效为 {profile}")
        else:
            messagebox.showwarning("失败", msg or "切换失败")
        self.refresh()