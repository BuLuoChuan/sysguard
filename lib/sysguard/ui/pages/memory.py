# -*- coding: utf-8 -*-
"""内存压缩与 swap 管理页：zram/zswap 检测、vm.swappiness 读写。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from ...core import memory
from ...core.shell import human_bytes
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)

        widgets.heading(self.frame.inner, "内存压缩与交换")

        # 功能说明
        explain = widgets.Card(self.frame.inner)
        ehead = tk.Frame(explain, bg=widgets.THEME["card_bg"])
        ehead.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(ehead, text="功能说明", style="Sub.TLabel").pack(side="left")
        self.explain_lang = "zh"
        self.explain_btn = ttk.Button(ehead, text="中文 / English",
                                      command=self._toggle_explain)
        self.explain_btn.pack(side="right")
        self.explain_zh = (
            "· vm.swappiness：控制把内存页换出到交换空间(swap)的倾向；0=尽量少用 swap、"
            "100=积极换出。桌面场景建议 10~30，避免频繁写盘卡顿。\n"
            "· zram：用内存模拟的「压缩块设备」——数据先压缩再放回内存，"
            "以少量 CPU 换更多可用内存，适合内存较小的机器。\n"
            "· zswap：在页面真正写入磁盘 swap 之前，先做一层压缩缓存；"
            "命中时直接读取压缩数据，减少磁盘交换读写，提升换出/换入速度。"
        )
        self.explain_en = (
            "· vm.swappiness: how aggressively the kernel swaps memory pages to disk; "
            "0 = avoid swap, 100 = swap eagerly. 10~30 is recommended for desktops.\n"
            "· zram: a RAM-backed compressed block device — data is compressed in memory, "
            "trading a little CPU for more usable RAM (good for low-memory machines).\n"
            "· zswap: a compressed cache in front of disk swap — hot swapped pages are "
            "read back from the cache, reducing disk I/O and speeding up swap."
        )
        self.explain_text = tk.StringVar(value=self.explain_zh)
        self.explain_label = ttk.Label(
            explain, textvariable=self.explain_text, style="CardMuted.TLabel",
            justify="left", wraplength=720)
        self.explain_label.pack(anchor="w", padx=12, pady=(4, 10))

        # 内存/交换概览
        grid = widgets.two_col(self.frame.inner)
        mem_card = widgets.Card(grid, pack=False)
        mem_card.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)
        self.mem_text = tk.StringVar()
        ttk.Label(mem_card, textvariable=self.mem_text,
                  style="Card.TLabel", justify="left").pack(
            anchor="w", padx=12, pady=10)
        swap_card = widgets.Card(grid, pack=False)
        swap_card.grid(row=0, column=1, sticky="nsew", padx=6, pady=4)
        self.swap_text = tk.StringVar()
        ttk.Label(swap_card, textvariable=self.swap_text,
                  style="Card.TLabel", justify="left").pack(
            anchor="w", padx=12, pady=10)

        # swappiness
        sw_card = widgets.Card(self.frame.inner)
        ttk.Label(sw_card, text="vm.swappiness（交换倾向）",
                  style="Sub.TLabel").pack(anchor="w", padx=12, pady=(10, 0))
        row = tk.Frame(sw_card, bg=widgets.THEME["card_bg"])
        row.pack(fill="x", padx=12, pady=8)
        self.sw_val = tk.StringVar()
        ttk.Spinbox(row, from_=0, to=100, textvariable=self.sw_val,
                    width=6).pack(side="left")
        ttk.Button(row, text="应用（需授权）",
                   command=self.apply_swappiness).pack(side="left", padx=8)
        ttk.Label(sw_card, style="CardMuted.TLabel",
                  text="0=尽量不用交换，100=积极换出；桌面建议 10~30。").pack(
            anchor="w", padx=12, pady=(0, 10))

        # zram
        zr_card = widgets.Card(self.frame.inner)
        ttk.Label(zr_card, text="zram（内存压缩块设备）",
                  style="Sub.TLabel").pack(anchor="w", padx=12, pady=(10, 0))
        self.zram_text = tk.StringVar()
        ttk.Label(zr_card, textvariable=self.zram_text,
                  style="Card.TLabel", justify="left").pack(
            anchor="w", padx=12, pady=(0, 10))

        # zswap
        zs_card = widgets.Card(self.frame.inner)
        ttk.Label(zs_card, text="zswap（交换页压缩缓存）",
                  style="Sub.TLabel").pack(anchor="w", padx=12, pady=(10, 0))
        self.zswap_text = tk.StringVar()
        ttk.Label(zs_card, textvariable=self.zswap_text,
                  style="Card.TLabel", justify="left").pack(
            anchor="w", padx=12, pady=(0, 10))

        ttk.Button(self.frame.inner, text="刷新",
                   command=self.refresh).pack(anchor="w", padx=18, pady=8)

        self.refresh()

    def _toggle_explain(self):
        self.explain_lang = "en" if self.explain_lang == "zh" else "zh"
        self.explain_btn.config(text="English" if self.explain_lang == "zh" else "中文")
        self.explain_text.set(
            self.explain_zh if self.explain_lang == "zh" else self.explain_en)

    def refresh(self):
        s = memory.summary()
        mem = s["memory"]
        swap = s["swap"]
        self.mem_text.set(
            f"内存：已用 {human_bytes(mem['used'])} / {human_bytes(mem['total'])}"
            f"（{mem['percent']}%）\n可用：{human_bytes(mem['available'])}")
        self.swap_text.set(
            f"交换：已用 {human_bytes(swap['used'])} / {human_bytes(swap['total'])}"
            f"（{swap['percent']}%）")
        self.sw_val.set(str(s["swappiness"]))

        zr = s["zram"]
        if zr["enabled"]:
            lines = [f"zram 已启用，共 {len(zr['devices'])} 个设备"]
            for d in zr["devices"]:
                lines.append(f"  {d['name']}: {human_bytes(d['size'] or 0)}")
        else:
            lines = ["zram 未启用"]
        self.zram_text.set("\n".join(lines))

        zs = s["zswap"]
        if zs["enabled"]:
            self.zswap_text.set(
                f"zswap 已启用\n压缩器：{zs['compressor']}\n"
                f"后端池：{zs['zpool']}\n上限：{zs['max_pool_percent']}%")
        else:
            self.zswap_text.set("zswap 未启用")

    def apply_swappiness(self):
        try:
            val = int(self.sw_val.get())
        except ValueError:
            messagebox.showwarning("输入错误", "请输入 0~100 的整数")
            return
        if not (0 <= val <= 100):
            messagebox.showwarning("输入错误", "请输入 0~100 的整数")
            return
        self.app.busy(True)
        try:
            ok, msg = memory.swappiness_set(val)
        finally:
            self.app.busy(False)
        messagebox.showinfo("结果", msg)
        self.refresh()