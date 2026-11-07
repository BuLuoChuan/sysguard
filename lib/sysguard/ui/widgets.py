# -*- coding: utf-8 -*-
"""通用 UI 组件与样式。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..config import THEME


FONT_SANS = "DejaVu Sans"


def apply_theme(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    bg, card, accent = THEME["bg"], THEME["card_bg"], THEME["accent"]

    style.configure(".", background=bg, foreground="#202124",
                    font=(FONT_SANS, 10))
    style.configure("TFrame", background=bg)
    style.configure("Card.TFrame", background=card)
    style.configure("TLabel", background=bg, foreground="#202124")
    style.configure("Card.TLabel", background=card, foreground="#202124")
    style.configure("Muted.TLabel", background=bg, foreground="#5f6368")
    style.configure("CardMuted.TLabel", background=card, foreground="#5f6368")
    style.configure("Title.TLabel", background=bg, foreground="#202124",
                    font=(FONT_SANS, 18, "bold"))
    style.configure("Sub.TLabel", background=card, foreground="#202124",
                    font=(FONT_SANS, 12, "bold"))
    style.configure("Big.TLabel", background=card, foreground=accent,
                    font=(FONT_SANS, 22, "bold"))

    style.configure("TButton", font=(FONT_SANS, 10), padding=6)
    style.configure("Accent.TButton", background=accent,
                    foreground="#ffffff", font=(FONT_SANS, 10, "bold"))
    style.map("Accent.TButton", background=[("active", "#1f5fd6")])

    style.configure("Sidebar.TButton", background=bg, foreground="#202124",
                    font=(FONT_SANS, 10), anchor="w", padding=10, relief="flat")
    style.map("Sidebar.TButton",
              background=[("active", "#e8eaed")],
              foreground=[("active", accent)])

    style.configure("Treeview", rowheight=24, font=(FONT_SANS, 10),
                    background="#ffffff", fieldbackground="#ffffff")
    style.configure("Treeview.Heading", font=(FONT_SANS, 10, "bold"))
    style.configure("TProgressbar", troughcolor="#e8eaed",
                    background=accent, thickness=8)
    return style


class Card(tk.Frame):
    """白色圆角矮阴影卡片（用浅边框近似）。"""

    def __init__(self, parent, pack=True, **pack_kw):
        super().__init__(parent, bg=THEME["card_bg"], bd=0,
                         highlightbackground="#e0e0e0", highlightthickness=1)
        if pack:
            self.pack(fill="x", padx=14, pady=6, **pack_kw)


def heading(parent, text, anchor="nw"):
    lbl = ttk.Label(parent, text=text, style="Title.TLabel")
    lbl.pack(fill="x", padx=16, pady=(14, 4), anchor=anchor)
    return lbl


class ScrollableFrame(tk.Frame):
    """带垂直滚动条的内容容器。"""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=THEME["bg"], **kw)
        self.canvas = tk.Canvas(self, bg=THEME["bg"], highlightthickness=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical",
                                 command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=THEME["bg"])
        self._win = self.canvas.create_window((0, 0), window=self.inner,
                                              anchor="nw")
        self.inner.bind("<Configure>", self._on_configure)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._win, width=e.width))
        # 鼠标滚轮
        self.canvas.bind_all("<MouseWheel>", self._on_wheel, add="+")

    def _on_configure(self, e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_wheel(self, e):
        if self.winfo_exists():
            self.canvas.yview_scroll(int(-e.delta / 120), "units")


def metric_card(parent, title, unit=""):
    """返回 (frame, value_var) 便于动态刷新一个指标。"""
    card = Card(parent, pack=False)
    ttk.Label(card, text=title, style="CardMuted.TLabel").pack(
        anchor="w", padx=12, pady=(10, 0))
    var = tk.StringVar(value="—")
    row = tk.Frame(card, bg=THEME["card_bg"])
    row.pack(fill="x", padx=12, pady=(0, 10))
    ttk.Label(row, textvariable=var, style="Big.TLabel").pack(side="left")
    if unit:
        ttk.Label(row, text=unit, style="CardMuted.TLabel").pack(
            side="left", padx=(4, 0), anchor="s", pady=(0, 6))
    return card, var


def progress_row(parent, label_text, value, color=None):
    """带百分比标签的进度条行，返回 (frame, bar, pct_var)。"""
    row = tk.Frame(parent, bg=THEME["card_bg"])
    row.pack(fill="x", padx=12, pady=8)
    ttk.Label(row, text=label_text, style="Card.TLabel").pack(
        side="left", anchor="w")
    pct_var = tk.StringVar(value=f"{int(value)}%")
    ttk.Label(row, textvariable=pct_var, style="CardMuted.TLabel").pack(
        side="right", padx=(6, 0))
    bar = ttk.Progressbar(row, orient="horizontal", mode="determinate",
                          maximum=100, value=value,
                          style="TProgressbar")
    bar.pack(fill="x", pady=(4, 0))
    return row, bar, pct_var


def two_col(container):
    """双列网格布局容器。"""
    grid = tk.Frame(container, bg=THEME["bg"])
    grid.pack(fill="both", expand=True, padx=4, pady=4)
    grid.columnconfigure(0, weight=1, uniform="col")
    grid.columnconfigure(1, weight=1, uniform="col")
    return grid