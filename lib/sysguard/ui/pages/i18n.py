# -*- coding: utf-8 -*-
"""中文环境检测页：字体 / 输入法 / locale（只读检测 + 给出安装指令）。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from ...core import i18n
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)

        widgets.heading(self.frame.inner, "中文环境检测")

        # 字体
        font_card = widgets.Card(self.frame.inner)
        head = tk.Frame(font_card, bg=widgets.THEME["card_bg"])
        head.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(head, text="中文字体", style="Sub.TLabel").pack(side="left")
        ttk.Button(head, text="刷新", command=self.refresh).pack(side="right")
        self.font_text = tk.StringVar(value="检测中…")
        ttk.Label(font_card, textvariable=self.font_text, style="Card.TLabel",
                  justify="left").pack(anchor="w", padx=12, pady=(4, 0))
        self.font_hint = tk.StringVar()
        self._hint_label(font_card, self.font_hint)

        # 输入法
        im_card = widgets.Card(self.frame.inner)
        ttk.Label(im_card, text="输入法框架", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        self.im_text = tk.StringVar(value="检测中…")
        ttk.Label(im_card, textvariable=self.im_text, style="Card.TLabel",
                  justify="left").pack(anchor="w", padx=12, pady=(4, 0))
        self.im_hint = tk.StringVar()
        self._hint_label(im_card, self.im_hint)

        # locale
        loc_card = widgets.Card(self.frame.inner)
        ttk.Label(loc_card, text="系统中文语言环境", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        self.loc_text = tk.StringVar(value="检测中…")
        ttk.Label(loc_card, textvariable=self.loc_text, style="Card.TLabel",
                  justify="left").pack(anchor="w", padx=12, pady=(4, 0))
        self.loc_hint = tk.StringVar()
        self._hint_label(loc_card, self.loc_hint)

        # 一键切换
        act_card = widgets.Card(self.frame.inner)
        ttk.Label(act_card, text="一键切换语言环境", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        ttk.Label(act_card, text="将系统 locale 切换为目标语言（生成中文 locale 并写入配置，需管理员密码，重新登录后生效）。",
                  style="CardMuted.TLabel", justify="left", wraplength=720).pack(
            anchor="w", padx=12, pady=(4, 2))
        arow = tk.Frame(act_card, bg=widgets.THEME["card_bg"])
        arow.pack(fill="x", padx=12, pady=(2, 10))
        ttk.Button(arow, text="切换为中文 (zh_CN.UTF-8)",
                   command=lambda: self._do_switch("zh")).pack(side="left")
        ttk.Button(arow, text="切换回英文 (en_US.UTF-8)",
                   command=lambda: self._do_switch("en")).pack(side="left", padx=6)

        # 说明
        note = widgets.Card(self.frame.inner)
        ttk.Label(note, text="说明：字体与输入法仅做检测、给出安装指令；"
                             "「一键切换语言环境」经授权后自动写入 locale 配置。",
                  style="CardMuted.TLabel",
                  justify="left", wraplength=720).pack(
            anchor="w", padx=12, pady=10)

        self.refresh()

    def _do_switch(self, lang):
        target = "中文" if lang == "zh" else "英文"
        if not messagebox.askyesno(
                "确认切换",
                f"确定将系统语言环境切换为{target}？\n\n"
                "将弹出管理员密码确认框，写入后需重新登录系统方可生效。"):
            return
        self.app.busy(True)
        try:
            ok, msg = i18n.switch_locale(lang)
        finally:
            self.app.busy(False)
        if ok:
            messagebox.showinfo("完成", msg)
        else:
            messagebox.showwarning("失败", msg)
        self.refresh()

    def _hint_label(self, parent, var):
        lbl = ttk.Label(parent, textvariable=var, style="CardMuted.TLabel",
                        justify="left", wraplength=720)
        lbl.pack(anchor="w", padx=12, pady=(0, 10))

    def _hint_visibility(self, var, fill):
        var.set(fill if fill else "")

    def refresh(self):
        s = i18n.summary()
        hints = i18n.install_hints()

        fonts = s["fonts"]
        if fonts:
            self.font_text.set("已安装：" + "、".join(fonts[:10]))
            self._hint_visibility(self.font_hint, "")
        else:
            self.font_text.set("未检测到中文字体")
            self._hint_visibility(self.font_hint, "安装指令：\n" + hints["fonts"])

        im_lines = []
        missing = False
        for im in s["input_methods"]:
            state = "已安装" if im["installed"] else "未安装"
            running = "，运行中" if im["running"] else ""
            im_lines.append(f"{im['name']}：{state}{running}")
            if not im["installed"]:
                missing = True
        self.im_text.set("\n".join(im_lines))
        if missing:
            self._hint_visibility(
                self.im_hint, "安装指令（fcitx5）：\n" + hints["fcitx5"])
        else:
            self._hint_visibility(self.im_hint, "")

        loc = s["locale"]
        if loc["is_zh"] and loc["zh_locales_available"]:
            self.loc_text.set(f"当前 LANG={loc['lang']}，已包含中文 locale："
                              f"{', '.join(loc['zh_locales_available'][:5])}")
            self._hint_visibility(self.loc_hint, "")
        else:
            self.loc_text.set(f"当前 LANG={loc['lang'] or '（未设置）'}，"
                              f"中文 locale 未就绪")
            self._hint_visibility(self.loc_hint, "配置指令：\n" + hints["locale"])