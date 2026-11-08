# -*- coding: utf-8 -*-
"""错误日志与诊断报告页。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from ...core import logs
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = widgets.ScrollableFrame(parent)
        self.frame.pack(fill="both", expand=True)

        widgets.heading(self.frame.inner, "错误日志与诊断")

        jcard = widgets.Card(self.frame.inner)
        head = tk.Frame(jcard, bg=widgets.THEME["card_bg"])
        head.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(head, text="系统日志错误（journal -p err）",
                  style="Sub.TLabel").pack(side="left")
        ttk.Button(head, text="刷新", command=self.refresh).pack(side="right")
        _, self.journal_txt = self._text(jcard, 10)
        self.journal_txt.pack(fill="x", padx=12, pady=6)

        dcard = widgets.Card(self.frame.inner)
        ttk.Label(dcard, text="内核错误（dmesg -l err）", style="Sub.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0))
        _, self.dmesg_txt = self._text(dcard, 8)
        self.dmesg_txt.pack(fill="x", padx=12, pady=6)

        rcard = widgets.Card(self.frame.inner)
        head = tk.Frame(rcard, bg=widgets.THEME["card_bg"])
        head.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(head, text="一键诊断报告", style="Sub.TLabel").pack(side="left")
        ttk.Button(head, text="生成报告", command=self.gen_report).pack(side="right")
        self.report_frame, self.report_txt = self._text(rcard, 16)
        self.report_frame.pack(fill="x", padx=12, pady=6)
        brow = tk.Frame(rcard, bg=widgets.THEME["card_bg"])
        brow.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(brow, text="导出报告…", command=self.export_report).pack(side="left")

        self.refresh()

    def _text(self, parent, height):
        wrap = tk.Frame(parent, bg=widgets.THEME["card_bg"])
        txt = tk.Text(wrap, height=height, wrap="word", relief="flat")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        return wrap, txt

    def _fill(self, widget, content):
        widget.delete("1.0", "end")
        widget.insert("1.0", content)

    def refresh(self):
        je = logs.journal_errors()
        self._fill(self.journal_txt, "\n".join(je) or "（无错误日志）")
        de = logs.dmesg_errors()
        self._fill(self.dmesg_txt, "\n".join(de) or "（无内核错误，或需 root 读取）")

    def gen_report(self):
        self.app.busy(True)
        try:
            report = logs.diagnostics()
        finally:
            self.app.busy(False)
        self._fill(self.report_txt, report)

    def export_report(self):
        content = self.report_txt.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("提示", "请先生成报告")
            return
        path = filedialog.asksaveasfilename(
            parent=self.app.root, defaultextension=".txt",
            initialfile="sysguard-diagnostics.txt",
            filetypes=[("文本文件", "*.txt")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        messagebox.showinfo("完成", f"已导出到 {path}")