# -*- coding: utf-8 -*-
"""网络优化与测试页：接口/连通性/速率/BBR/DNS/路由/WiFi 节能。"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from ...core import network
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.root = app.root
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)

        widgets.heading(self.frame.inner, "网络优化与测试")

        ttk.Label(self.frame.inner, text="网络接口",
                  style="Sub.TLabel").pack(anchor="w", padx=18, pady=(6, 0))
        self.iface_card = widgets.Card(self.frame.inner)
        self.iface_text = tk.StringVar(value="加载中…")
        ttk.Label(self.iface_card, textvariable=self.iface_text,
                  style="Card.TLabel", justify="left").pack(
            anchor="w", padx=12, pady=10)

        grid = widgets.two_col(self.frame.inner)
        rx_card, self.rx_var2 = widgets.metric_card(grid, "最大下行带宽", "MB/s")
        rx_card.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)
        tx_card, self.tx_var2 = widgets.metric_card(grid, "最大上行带宽", "MB/s")
        tx_card.grid(row=0, column=1, sticky="nsew", padx=6, pady=4)

        ttk.Button(self.frame.inner, text="测最大带宽",
                   command=self.measure_rate).pack(anchor="w", padx=18, pady=4)

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

        bbr_card = widgets.Card(self.frame.inner)
        head = tk.Frame(bbr_card, bg=widgets.THEME["card_bg"])
        head.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(head, text="TCP 拥塞控制 / BBR", style="Sub.TLabel").pack(side="left")
        self.bbr_var = tk.StringVar(value="检测中…")
        ttk.Label(bbr_card, textvariable=self.bbr_var,
                  style="Card.TLabel").pack(anchor="w", padx=12, pady=6)
        brow = tk.Frame(bbr_card, bg=widgets.THEME["card_bg"])
        brow.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(brow, text="启用 BBR", command=lambda: self.bbr(True)).pack(side="left")
        ttk.Button(brow, text="恢复默认(CUBIC)",
                   command=lambda: self.bbr(False)).pack(side="left", padx=6)

        route_card = widgets.Card(self.frame.inner)
        ttk.Label(route_card, text="路由表（ip route）", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        self.route_text = tk.StringVar(value="")
        ttk.Label(route_card, textvariable=self.route_text,
                  style="CardMuted.TLabel", justify="left").pack(
            anchor="w", padx=12, pady=(0, 10))

        wifi_card = widgets.Card(self.frame.inner)
        ttk.Label(wifi_card, text="WiFi 电源管理（节能/高能）", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        wrow = tk.Frame(wifi_card, bg=widgets.THEME["card_bg"])
        wrow.pack(fill="x", padx=12, pady=8)
        ttk.Label(wrow, text="接口：", style="Card.TLabel").pack(side="left")
        self.wifi_var = tk.StringVar()
        self.wifi_box = ttk.Combobox(wrow, textvariable=self.wifi_var,
                                     width=16, state="readonly")
        self.wifi_box.pack(side="left")
        ttk.Button(wrow, text="刷新", command=self.refresh_wifi).pack(side="left", padx=6)
        self.wifi_text = tk.StringVar(value="")
        ttk.Label(wifi_card, textvariable=self.wifi_text,
                  style="Card.TLabel").pack(anchor="w", padx=12, pady=6)
        wbtn = tk.Frame(wifi_card, bg=widgets.THEME["card_bg"])
        wbtn.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(wbtn, text="开启节能（省电）",
                   command=lambda: self.wifi_ps(True)).pack(side="left")
        ttk.Button(wbtn, text="关闭节能（高能）",
                   command=lambda: self.wifi_ps(False)).pack(side="left", padx=6)

        dns_card = widgets.Card(self.frame.inner)
        ttk.Label(dns_card, text="DNS 服务器", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        dns_servers = network.dns_servers()
        ttk.Label(dns_card, text="\n".join(dns_servers) or "（无）",
                  style="Card.TLabel").pack(anchor="w", padx=12, pady=(0, 10))

        self.refresh()
        self.refresh_wifi()
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
        self.route_text.set("\n".join(network.routes()) or "（无）")

    def refresh_wifi(self):
        wls = network.wifi_interfaces()
        self.wifi_box["values"] = wls
        if wls:
            self.wifi_box.current(0)
            self._show_wifi_status(wls[0])
        else:
            self.wifi_text.set("未检测到无线网卡（wlan*）")

    def _show_wifi_status(self, iface):
        st = network.wifi_powersave(iface)
        if st == "unknown":
            self.wifi_text.set(f"{iface}：状态未知（可能缺少 iw 工具）")
        else:
            self.wifi_text.set(f"{iface}：节能 {'开启' if st == 'on' else '关闭'}")

    def wifi_ps(self, on):
        iface = self.wifi_var.get()
        if not iface:
            messagebox.showinfo("提示", "未检测到无线网卡")
            return
        self.app.busy(True)
        try:
            ok, msg = network.wifi_powersave_set(iface, on)
        finally:
            self.app.busy(False)
        if ok:
            self.app.set_status(f"{iface} 节能已{'开启' if on else '关闭'}")
        else:
            messagebox.showwarning("失败", msg or "设置失败")
        self.refresh_wifi()

    def measure_rate(self):
        self.app.busy(True)
        self.app.set_status("正在测最大带宽（约 8 秒），请稍候…")
        threading.Thread(target=self._run_bandwidth, daemon=True).start()

    def _run_bandwidth(self):
        try:
            r = network.max_bandwidth(duration=5)
        except Exception:
            r = {"down_bps": None, "up_bps": None}
        self.root.after(0, lambda: self._finish_bandwidth(r))

    def _finish_bandwidth(self, r):
        self.app.busy(False)
        self.rx_var2.set(self._mbps(r.get("down_bps")))
        self.tx_var2.set(self._mbps(r.get("up_bps")))
        self.app.set_status(
            "最大带宽测速完成" if r.get("down_bps") else "下行测速失败")

    @staticmethod
    def _mbps(bps):
        return f"{bps / 8e6:.1f}" if bps else "—"

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