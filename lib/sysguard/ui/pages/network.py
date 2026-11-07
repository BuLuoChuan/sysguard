# -*- coding: utf-8 -*-
"""网络优化与测试页：接口/连通性/速率/BBR/DNS。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from ...core import network
from ...core.shell import human_bytes
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.root = app.root
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)

        widgets.heading(self.frame.inner, "网络优化与测试")

        # 接口列表
        ttk.Label(self.frame.inner, text="网络接口",
                  style="Sub.TLabel").pack(anchor="w", padx=18, pady=(6, 0))
        self.iface_card = widgets.Card(self.frame.inner)
        self.iface_text = tk.StringVar(value="加载中…")
        ttk.Label(self.iface_card, textvariable=self.iface_text,
                  style="Card.TLabel", justify="left").pack(
            anchor="w", padx=12, pady=10)

        # 实时速率
        grid = widgets.two_col(self.frame.inner)
        rx_card, self.rx_var2 = widgets.metric_card(grid, "实时下行", "B/s")
        rx_card.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)
        tx_card, self.tx_var2 = widgets.metric_card(grid, "实时上行", "B/s")
        tx_card.grid(row=0, column=1, sticky="nsew", padx=6, pady=4)

        ttk.Button(self.frame.inner, text="重新测速",
                   command=self.measure_rate).pack(anchor="w", padx=18, pady=4)

        # 连通性测试
        ping_card = widgets.Card(self.frame.inner)
        ttk.Label(ping_card, text="连通性测试 (ping)",
                  style="Sub.TLabel").pack(anchor="w", padx=12, pady=(10, 0))
        row = tk.Frame(ping_card, bg=widgets.THEME["card_bg"])
        row.pack(fill="x", padx=12, pady=8)
        ttk.Label(row, text="目标主机：", style="Card.TLabel").pack(side="left")
        self.host_var = tk.StringVar(value="1.1.1.1")
        ttk.Entry(row, textvariable=self.host_var, width=22).pack(side="left")
        ttk.Button(row, text="测试", command=self.ping).pack(side="left", padx=6)
        self.ping_text = tk.StringVar(value="（尚未测试）")
        ttk.Label(ping_card, textvariable=self.ping_text,
                  style="CardMuted.TLabel", justify="left").pack(
            anchor="w", padx=12, pady=(0, 10))

        # BBR
        bbr_card = widgets.Card(self.frame.inner)
        head = tk.Frame(bbr_card, bg=widgets.THEME["card_bg"])
        head.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(head, text="TCP 拥塞控制 / BBR", style="Sub.TLabel").pack(
            side="left")
        self.bbr_var = tk.StringVar(value="检测中…")
        ttk.Label(bbr_card, textvariable=self.bbr_var,
                  style="Card.TLabel").pack(anchor="w", padx=12, pady=6)
        brow = tk.Frame(bbr_card, bg=widgets.THEME["card_bg"])
        brow.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(brow, text="启用 BBR", command=lambda: self.bbr(True)).pack(
            side="left")
        ttk.Button(brow, text="恢复默认(CUBIC)",
                   command=lambda: self.bbr(False)).pack(side="left", padx=6)

        # DNS
        dns_card = widgets.Card(self.frame.inner)
        ttk.Label(dns_card, text="DNS 服务器", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        dns_servers = network.dns_servers()
        ttk.Label(dns_card, text="\n".join(dns_servers) or "（无）",
                  style="Card.TLabel").pack(anchor="w", padx=12, pady=(0, 10))

        self.refresh()
        self.measure_rate()

    def refresh(self):
        ifaces = network.interfaces()
        lines = []
        for i in ifaces:
            lines.append(f"{i['name']}  [{i['state']}]  "
                         f"IPv4:{i['inet'] or '—'}  IPv6:{i['inet6'] or '—'}"
                         f"  MAC:{i['mac'] or '—'}")
        self.iface_text.set("\n".join(lines) or "无网络接口")
        b = network.bbr_status()
        self.bbr_var.set(f"拥塞控制：{b['congestion_control']}  ·  "
                         f"qdisc：{b['default_qdisc']}  ·  "
                         f"BBR：{'已启用' if b['bbr'] else '未启用'}")

    def measure_rate(self):
        r = network.realtime_rate(0.8)
        self.rx_var2.set(f"{human_bytes(r['rx_rate'])}")
        self.tx_var2.set(f"{human_bytes(r['tx_rate'])}")

    def ping(self):
        host = self.host_var.get().strip()
        self.app.busy(True)
        try:
            ok, res = network.ping(host)
        finally:
            self.app.busy(False)
        if ok:
            rtt = res.get("rtt")
            self.ping_text.set(f"{host}：平均 {rtt['avg']} ms, "
                               f"丢包 {res['loss']}%" if rtt else
                               f"{host}：可达（丢包 {res['loss']}%）")
        else:
            self.ping_text.set(f"{host}：{res.get('error', '失败')}")

    def bbr(self, on):
        self.app.busy(True)
        try:
            ok, msg = network.bbr_set(on)
        finally:
            self.app.busy(False)
        if ok:
            self.app.set_status("BBR 设置成功")
        else:
            messagebox.showwarning("设置失败", msg)
        self.refresh()