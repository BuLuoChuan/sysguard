# -*- coding: utf-8 -*-
"""USB 设备页：挂载/卸载/机械硬盘停转（重点功能）。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from ...core import usb
from ...core.shell import human_bytes
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=widgets.THEME["bg"])
        self.frame.pack(fill="both", expand=True)

        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=16, pady=(14, 0))
        ttk.Label(bar, text="USB 设备与硬盘停转", style="Title.TLabel").pack(
            side="left")
        ttk.Button(bar, text="刷新", command=self.reload).pack(side="right")

        tip = ttk.Label(self.frame, style="Muted.TLabel",
                        text="仅对「机械盘 + 非系统盘」开放停转；系统盘与 SSD 一律不触碰，"
                             "停转前请先卸载该盘所有分区。")
        tip.pack(anchor="w", padx=18, pady=(6, 0))

        cols = ("name", "size", "model", "mount", "power", "temp", "note")
        heads = ("设备", "容量", "型号", "挂载点", "电源态", "温度", "说明")
        self.tree = ttk.Treeview(self.frame, columns=cols, show="headings",
                                 height=13)
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=110, anchor="w")
        self.tree.column("model", width=220)
        self.tree.column("mount", width=220)
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)

        btns = ttk.Frame(self.frame)
        btns.pack(fill="x", padx=16, pady=8)
        ttk.Button(btns, text="挂载", command=self.mount).pack(side="left")
        ttk.Button(btns, text="卸载全部", command=self.unmount_all).pack(
            side="left", padx=6)
        ttk.Button(btns, text="停转磁头", command=self.spindown).pack(
            side="left", padx=6)
        ttk.Button(btns, text="唤醒磁盘", command=self.spinup).pack(
            side="left", padx=6)
        ttk.Button(btns, text="加载电源状态", command=self.load_power).pack(
            side="right")

        self.reload()

    def reload(self):
        scan = usb.list_usb(with_power=False)
        self.disks = scan["disks"] if scan["ok"] else []
        self.app.set_status(f"发现 {len(self.disks)} 个 USB 存储设备")
        self._fill()

    def load_power(self):
        from ...core import disk
        self.app.busy(True)
        try:
            ok, disks, err = disk.scan_with_power()
        finally:
            self.app.busy(False)
        if not ok:
            messagebox.showwarning("授权失败", err or "无法读取电源状态")
            return
        self.disks = [d for d in disks if d.get("is_usb")]
        self._fill()
        self.app.set_status("电源状态已加载")

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        for d in self.disks:
            rot = d.get("rotational")
            system = d.get("is_system_disk")
            if system:
                note = "系统盘，禁操作"
            elif not rot:
                note = "SSD，禁停转"
            elif not d.get("by_id"):
                note = "无法确认身份"
            else:
                note = "可停转"
            temp = d.get("temperature")
            temp_s = f"{temp}°C" if temp is not None else "—"
            self.tree.insert("", "end", values=(
                d["name"], human_bytes(d.get("size_bytes") or 0),
                d.get("model") or "", ", ".join(d.get("mountpoints") or []),
                d.get("power_state") or "UNKNOWN", temp_s, note))

    def _sel(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个 USB 设备")
            return None
        name = self.tree.item(sel[0], "values")[0]
        return next((d for d in self.disks if d["name"] == name), None)

    def _guard(self, d):
        if d.get("is_system_disk"):
            messagebox.showwarning("禁止", "该盘包含系统挂载点，禁止操作")
            return False
        if not d.get("rotational"):
            messagebox.showwarning("禁止", "固态盘（SSD）不支持停转")
            return False
        if not d.get("by_id"):
            messagebox.showwarning("禁止", "该设备缺少稳定 by-id，身份无法确认")
            return False
        return True

    def mount(self):
        d = self._sel()
        if not d:
            return
        # 找第一个可分区的设备
        dev = d["partitions"][0]["path"] if d.get("partitions") else d["path"]
        self.app.busy(True)
        try:
            ok, data, err = usb.mount(dev)
        finally:
            self.app.busy(False)
        messagebox.showinfo("结果", f"挂载 {dev}：" +
                            (f"成功 @ {data.get('mountpoint')}" if ok else
                             f"失败：{err}"))
        self.reload()

    def unmount_all(self):
        d = self._sel()
        if not d:
            return
        mps = d.get("mountpoints") or []
        if not mps:
            messagebox.showinfo("提示", "该设备无挂载点")
            return
        for mp in mps:
            ok, _, err = usb.unmount(mp)
            if not ok:
                messagebox.showwarning("卸载失败", f"{mp}: {err}")
                return
        messagebox.showinfo("完成", "已卸载全部挂载点")
        self.reload()

    def spindown(self):
        d = self._sel()
        if not d or not self._guard(d):
            return
        if d.get("mountpoints"):
            if not messagebox.askyesno("确认", "该盘仍有挂载点，停转前需先卸载。是否继续（将中止）？"):
                return
        if not messagebox.askyesno("确认", f"确定停转 {d['name']} 的磁头？"):
            return
        self.app.set_status(f"正在停转 {d['name']}…")
        self.app.busy(True)
        try:
            ok, data, err = usb.spindown(d["by_id"])
        finally:
            self.app.busy(False)
        if ok:
            msg = (f"停转完成，最终电源态：{data.get('final_state')}\n"
                   f"效果：{data.get('effect')}")
        else:
            msg = f"停转失败：{err}"
        messagebox.showinfo("停转结果", msg)
        self.app.set_status("停转操作结束")
        self.reload()

    def spinup(self):
        d = self._sel()
        if not d or not self._guard(d):
            return
        self.app.busy(True)
        try:
            ok, data, err = usb.spinup(d["by_id"])
        finally:
            self.app.busy(False)
        messagebox.showinfo("结果", "已唤醒" if ok else f"唤醒失败：{err}")
        self.reload()