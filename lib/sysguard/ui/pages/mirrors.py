# -*- coding: utf-8 -*-
"""镜像源页：检测发行版 / 测速 / 一键切换（apt 与 rpm）。"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from ...core import mirror
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)
        self._mirrors = []

        widgets.heading(self.frame.inner, "镜像源")

        info_card = widgets.Card(self.frame.inner)
        ttk.Label(info_card, text="系统信息", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        self.info_text = tk.StringVar()
        ttk.Label(info_card, textvariable=self.info_text,
                  style="Card.TLabel", justify="left").pack(
            anchor="w", padx=12, pady=(0, 10))

        list_card = widgets.Card(self.frame.inner)
        head = tk.Frame(list_card, bg=widgets.THEME["card_bg"])
        head.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(head, text="可选镜像", style="Sub.TLabel").pack(side="left")
        ttk.Button(head, text="刷新", command=self.refresh).pack(side="right")

        self.tree = ttk.Treeview(list_card, columns=("name", "base", "speed"),
                                 show="headings", height=8)
        self.tree.heading("name", text="名称")
        self.tree.heading("base", text="地址")
        self.tree.heading("speed", text="速度")
        self.tree.column("name", width=100, anchor="w")
        self.tree.column("base", width=400, anchor="w")
        self.tree.column("speed", width=140, anchor="w")
        self.tree.pack(fill="x", padx=12, pady=6)

        btn = tk.Frame(list_card, bg=widgets.THEME["card_bg"])
        btn.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(btn, text="测速选中", command=self.test_selected).pack(side="left")
        ttk.Button(btn, text="应用选中", command=self.apply_selected).pack(
            side="left", padx=(6, 0))

        op_card = widgets.Card(self.frame.inner)
        ttk.Label(op_card, text="备份与还原", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        ttk.Label(op_card, text="切换前会自动备份当前源，可随时一键还原。",
                  style="CardMuted.TLabel").pack(anchor="w", padx=12, pady=4)
        row = tk.Frame(op_card, bg=widgets.THEME["card_bg"])
        row.pack(fill="x", padx=12, pady=(4, 10))
        ttk.Button(row, text="立即备份", command=self.backup).pack(side="left")
        ttk.Button(row, text="还原备份", command=self.restore).pack(
            side="left", padx=(6, 0))

        self.refresh()

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个镜像")
            return None
        idx = self.tree.index(sel[0])
        if idx < 0 or idx >= len(self._mirrors):
            return None
        return self._mirrors[idx]["id"]

    def refresh(self):
        info = mirror.available()
        d = info["detect"]
        self._mirrors = info["mirrors"]
        pm = d["pm"] or "未检测到"
        fam = d["family"] or "未知"
        self.info_text.set(
            f"系统：{d['name']}\n包管理器：{pm}（家族：{fam}）")
        self.tree.delete(*self.tree.get_children())
        for m in self._mirrors:
            self.tree.insert("", "end", values=(m["name"], m["base"], "—"))

    def test_selected(self):
        mid = self._selected_id()
        if not mid:
            return
        self.app.busy(True)
        try:
            ok, res = mirror.test_mirror(mid)
        finally:
            self.app.busy(False)
        if ok:
            speed = f"{res['speed_mbps']} MB/s"
        else:
            speed = "不可达"
        self._update_speed(mid, speed)

    def _update_speed(self, mid, text):
        for item in self.tree.get_children():
            idx = self.tree.index(item)
            if idx < len(self._mirrors) and self._mirrors[idx]["id"] == mid:
                self.tree.item(item, values=(
                    self._mirrors[idx]["name"],
                    self._mirrors[idx]["base"], text))
                break

    def apply_selected(self):
        mid = self._selected_id()
        if not mid:
            return
        name = next(m["name"] for m in self._mirrors if m["id"] == mid)
        if not messagebox.askyesno(
                "确认切换", f"切换镜像源到「{name}」？\n\n"
                "将自动备份当前源并覆盖配置，可稍后一键还原。"):
            return
        self.app.busy(True)
        try:
            ok, msg = mirror.apply(mid)
        finally:
            self.app.busy(False)
        if ok:
            messagebox.showinfo("完成", f"已切换到 {name} 镜像，"
                                      "建议运行更新以刷新索引。")
        else:
            messagebox.showwarning("失败", str(msg))
        self.refresh()

    def backup(self):
        self.app.busy(True)
        try:
            ok, msg = mirror.backup()
        finally:
            self.app.busy(False)
        if ok:
            messagebox.showinfo("完成", f"已备份当前源到：\n{msg}")
        else:
            messagebox.showwarning("失败", str(msg))

    def restore(self):
        if not messagebox.askyesno("确认还原", "用备份覆盖当前镜像源配置？"):
            return
        self.app.busy(True)
        try:
            ok, msg = mirror.restore()
        finally:
            self.app.busy(False)
        if ok:
            messagebox.showinfo("完成", "已还原")
        else:
            messagebox.showwarning("失败", str(msg))
        self.refresh()