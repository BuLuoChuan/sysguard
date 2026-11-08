# -*- coding: utf-8 -*-
"""镜像源页：检测发行版 / 一键测速延时 / 一键切换（apt 与 rpm）。

一键测速会对当前发行版的全部镜像同时测「网速 + 延时」，完成后按
综合评分（网速/延时权重）自动排序，无需手动逐个选择镜像。
"""
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
        self._testing = False
        self._supported = True

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
        ttk.Label(head, text="可选镜像（一键测速后按速度/延时自动排序）",
                  style="Sub.TLabel").pack(side="left")
        ttk.Button(head, text="刷新", command=self.refresh).pack(side="right")

        cols = ("name", "base", "speed", "latency")
        heads = ("名称", "地址", "下载速度", "延时")
        self.tree = ttk.Treeview(list_card, columns=cols, show="headings",
                                 height=8)
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
        self.tree.column("name", width=90, anchor="w")
        self.tree.column("base", width=300, anchor="w")
        self.tree.column("speed", width=110, anchor="w")
        self.tree.column("latency", width=90, anchor="w")
        self.tree.pack(fill="x", padx=12, pady=6)

        btn = tk.Frame(list_card, bg=widgets.THEME["card_bg"])
        btn.pack(fill="x", padx=12, pady=(0, 10))
        self.test_btn = ttk.Button(btn, text="一键测速（网速+延时）",
                                   command=self.start_test)
        self.test_btn.pack(side="left")
        ttk.Button(btn, text="应用选中", command=self.apply_selected).pack(
            side="right")

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
        self._supported = bool(info.get("supported", True))
        self._mirrors = [{"id": m["id"], "name": m["name"], "base": m["base"],
                          "speed": None, "latency": None}
                         for m in info["mirrors"]]
        pm = d["pm"] or "未检测到"
        fam = d["family"] or "未知"
        if not self._supported:
            self.info_text.set(
                f"系统：{d['name']}\n包管理器：{pm}（家族：{fam}）\n\n"
                "⚠ 当前发行版不在支持列表内。\n"
                "仅支持 Ubuntu / Debian / Fedora / Linux Mint 及其衍生版。")
        else:
            self.info_text.set(
                f"系统：{d['name']}\n包管理器：{pm}（家族：{fam}）")
        self._render()

    def _require_supported(self) -> bool:
        if self._supported:
            return True
        messagebox.showinfo(
            "暂不支持",
            "当前发行版不在支持列表内。\n仅支持 Ubuntu / Debian / Fedora / "
            "Linux Mint 及其衍生版。")
        return False

    def _render(self):
        self.tree.delete(*self.tree.get_children())
        for m in self._mirrors:
            self.tree.insert("", "end", values=(
                m["name"], m["base"], m["speed"] or "—", m["latency"] or "—"))

    def start_test(self):
        if self._testing:
            return
        if not self._require_supported():
            return
        if not self._mirrors:
            messagebox.showinfo("提示", "未检测到可用镜像")
            return
        self._testing = True
        self.test_btn.config(state="disabled")
        self.app.busy(True)
        self.app.set_status("正在测试全部镜像的网速与延时，请稍候…")
        threading.Thread(target=self._run_test, daemon=True).start()

    def _run_test(self):
        try:
            ok, data = mirror.test_all()
        except Exception as e:  # 兜底，避免线程内异常中断
            ok, data = False, {"error": str(e)}
        # 回主线程更新 UI
        self.app.root.after(0, lambda: self._finish_test(ok, data))

    def _finish_test(self, ok, data):
        self._testing = False
        self.test_btn.config(state="normal")
        self.app.busy(False)
        if not ok:
            messagebox.showwarning("失败", data.get("error", "测速失败"))
            self.app.set_status("测速失败")
            return
        results = data.get("results", [])
        new_mirrors = []
        for r in results:
            m = r["mirror"]
            if r["ok"]:
                speed = f"{r['speed_mbps']} MB/s"
                lat = f"{r['latency_ms']}ms" if r["latency_ms"] is not None else "—"
            else:
                speed, lat = "不可达", "—"
            new_mirrors.append({"id": m["id"], "name": m["name"],
                                "base": m["base"], "speed": speed,
                                "latency": lat, "score": r.get("score", -1)})
        self._mirrors = new_mirrors
        self._render()
        self.app.set_status("测速完成，已按网速/延时综合评分自动排序")

    def apply_selected(self):
        if not self._require_supported():
            return
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