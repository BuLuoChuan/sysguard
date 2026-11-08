# -*- coding: utf-8 -*-
"""磁盘管理检修页：分区/挂载/SMART/温度/坏道。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from ...core import disk
from ...core.shell import human_bytes
from .. import widgets


HEALTH_CN = {"ok": "正常", "warn": "警告⚠️", "bad": "异常❌"}
STATUS_CN = {"ok": "正常", "warn": "⚠️ 警告", "bad": "❌ 异常"}


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=widgets.THEME["bg"])
        self.frame.pack(fill="both", expand=True)

        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=16, pady=(14, 0))
        ttk.Label(bar, text="磁盘管理检修", style="Title.TLabel").pack(
            side="left")
        self.scan_btn = ttk.Button(bar, text="读取 SMART（需授权）",
                                   command=self.load_smart)
        self.scan_btn.pack(side="right")
        ttk.Button(bar, text="刷新", command=self.reload).pack(
            side="right", padx=4)
        ttk.Button(bar, text="SMART 详情",
                   command=self.smart_detail).pack(side="right", padx=4)

        cols = ("name", "size", "rota", "transport", "model",
                "mount", "temp", "power", "health", "guard")
        heads = ("设备", "容量", "类型", "接口", "型号", "挂载点", "温度", "电源态", "健康", "状态")
        self.tree = ttk.Treeview(self.frame, columns=cols, show="headings",
                                 height=14)
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=100, anchor="w")
        self.tree.column("model", width=200)
        self.tree.column("mount", width=200)
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)

        self.disks = []
        self.reload()

    def reload(self):
        scan = disk.scan_disks(with_power=False)
        self.disks = scan["disks"] if scan["ok"] else []
        self._fill(self.disks)
        self.app.set_status(f"发现 {len(self.disks)} 块磁盘（SMART 未加载）")

    def load_smart(self):
        self.app.busy(True)
        try:
            ok, disks, err = disk.scan_with_power()
        finally:
            self.app.busy(False)
        if not ok:
            messagebox.showwarning("授权失败", err or "无法读取 SMART")
            return
        self.disks = disks
        self._fill(disks)
        self.app.set_status("SMART 已加载")

    def _fill(self, disks):
        self.tree.delete(*self.tree.get_children())
        for d in disks:
            rota = "机械盘" if d.get("rotational") else "固态盘"
            is_usb = "USB" if d.get("is_usb") else d.get("transport") or ""
            guard = "受保护" if d.get("is_system_disk") else (
                "可停转" if d.get("rotational") and not d.get("is_system_disk")
                else "")
            temp = d.get("temperature")
            temp_s = f"{temp}°C" if temp is not None else "—"
            ps = d.get("power_state") or "UNKNOWN"
            health = d.get("health")
            health_s = HEALTH_CN.get(health, "—") if health else "—"
            self.tree.insert("", "end", values=(
                d["name"], human_bytes(d.get("size_bytes") or 0), rota,
                is_usb, d.get("model") or "", ", ".join(d.get("mountpoints") or []),
                temp_s, ps, health_s, guard))

    def _sel_disk(self):
        sel = self.tree.selection()
        if not sel:
            return None
        name = self.tree.item(sel[0], "values")[0]
        return next((d for d in self.disks if d["name"] == name), None)

    def smart_detail(self):
        d = self._sel_disk()
        if not d:
            messagebox.showinfo("提示", "请先选择一块磁盘")
            return
        attrs = d.get("smart_attrs") or []
        if not attrs:
            self.app.busy(True)
            try:
                ok, data, err = disk.smart_report(d["path"])
            finally:
                self.app.busy(False)
            if not ok:
                messagebox.showwarning("失败", err or "无法读取 SMART")
                return
            _, attrs = disk.analyze_smart(data.get("report", ""))
        if not attrs:
            messagebox.showinfo("提示", "未解析到 SMART 属性，请先点击「读取 SMART」")
            return
        health = d.get("health")
        health_fg = {"ok": "#1e8e3e", "warn": "#f9a825",
                     "bad": "#d93025"}.get(health, "#202124")
        win = tk.Toplevel(self.app.root)
        win.title(f"SMART 详情 - {d['name']}")
        win.geometry("860x560")
        win.configure(bg="#ffffff")
        tk.Label(win, text=f"整体健康：{HEALTH_CN.get(health, '未知')}",
                 bg="#ffffff", fg=health_fg,
                 font=(widgets.FONT_SANS, 14, "bold")).pack(
            anchor="w", padx=14, pady=(12, 4))
        cols = ("id", "name", "value", "worst", "thresh", "raw", "status")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        heads = ("ID", "SMART 项目（中文专有名词）", "当前值", "最差值", "阈值", "原始值", "状态")
        for c, h in zip(cols, heads):
            tree.heading(c, text=h)
        tree.column("id", width=46, anchor="w")
        tree.column("name", width=250, anchor="w")
        tree.column("value", width=64, anchor="center")
        tree.column("worst", width=64, anchor="center")
        tree.column("thresh", width=56, anchor="center")
        tree.column("raw", width=150, anchor="w")
        tree.column("status", width=96, anchor="center")
        tree.pack(fill="both", expand=True, padx=14, pady=6)
        for a in attrs:
            nm = a["name_cn"] if a["name_cn"] == a["name"] else \
                f"{a['name_cn']}（{a['name']}）"
            tree.insert("", "end", values=(
                a["id"], nm, a["value"], a["worst"], a["threshold"],
                a["raw"], STATUS_CN.get(a["status"], a["status"])))
        tk.Label(win, text="说明：❌ 红色为异常项（坏扇区/不可纠正错误等），⚠️ 黄色为警告项，建议持续关注或备份数据。",
                 bg="#ffffff", fg="#5f6368", anchor="w",
                 font=(widgets.FONT_SANS, 9)).pack(anchor="w", padx=14, pady=(0, 12))