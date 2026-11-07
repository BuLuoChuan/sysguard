# -*- coding: utf-8 -*-
"""磁盘管理检修页：分区/挂载/SMART/温度/坏道。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from ...core import disk
from ...core.shell import human_bytes
from .. import widgets


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
                "mount", "temp", "power", "guard")
        heads = ("设备", "容量", "类型", "接口", "型号", "挂载点", "温度", "电源态", "状态")
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
            self.tree.insert("", "end", values=(
                d["name"], human_bytes(d.get("size_bytes") or 0), rota,
                is_usb, d.get("model") or "", ", ".join(d.get("mountpoints") or []),
                temp_s, ps, guard))

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
        self.app.busy(True)
        try:
            ok, data, err = disk.smart_report(d["path"])
        finally:
            self.app.busy(False)
        if not ok:
            messagebox.showwarning("失败", err or "无法读取 SMART")
            return
        win = tk.Toplevel(self.app.root)
        win.title(f"SMART 详情 - {d['name']}")
        win.geometry("760x520")
        st = scrolledtext.ScrolledText(win, font=(widgets.FONT_SANS, 9))
        st.pack(fill="both", expand=True, padx=8, pady=8)
        st.insert("1.0", data.get("report", ""))
        st.configure(state="disabled")