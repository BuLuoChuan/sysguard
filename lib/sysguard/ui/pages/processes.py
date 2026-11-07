# -*- coding: utf-8 -*-
"""进程与服务管理页。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from ...core import process
from ...core.shell import human_bytes
from .. import widgets


class Page:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=widgets.THEME["bg"])
        self.frame.pack(fill="both", expand=True)

        db = ttk.Frame(self.frame)
        db.pack(fill="x", padx=16, pady=(14, 0))
        ttk.Label(db, text="进程管理", style="Title.TLabel").pack(side="left")
        search_var = tk.StringVar()
        ent = ttk.Entry(db, textvariable=search_var, width=24)
        ent.pack(side="left", padx=12)
        ent.insert(0, "")
        ttk.Button(db, text="搜索",
                   command=lambda: self.reload(search_var.get())).pack(
            side="left", padx=4)
        self.sort_var = tk.StringVar(value="mem")
        ttk.Radiobutton(db, text="按内存", variable=self.sort_var, value="mem",
                        command=self._reload_current).pack(side="left", padx=6)
        ttk.Radiobutton(db, text="按CPU", variable=self.sort_var, value="cpu",
                        command=self._reload_current).pack(side="left", padx=6)
        ttk.Button(db, text="结束进程",
                   command=self.kill_selected).pack(side="right")
        ttk.Button(db, text="刷新",
                   command=self._reload_current).pack(side="right", padx=4)

        cols = ("pid", "user", "cpu", "mem", "rss", "comm", "args")
        heads = ("PID", "用户", "CPU%", "内存%", "RSS", "程序", "命令行")
        self.tree = ttk.Treeview(self.frame, columns=cols, show="headings",
                                 height=12)
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=90, anchor="w")
        self.tree.column("args", width=420)
        self.tree.column("comm", width=140)
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        ysb = ttk.Scrollbar(self.frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)

        # 服务区
        svc_head = ttk.Frame(self.frame)
        svc_head.pack(fill="x", padx=16, pady=(10, 0))
        ttk.Label(svc_head, text="系统服务 (systemd)",
                  style="Title.TLabel").pack(side="left")
        ttk.Button(svc_head, text="启动", command=lambda: self.svc("start")
                   ).pack(side="right")
        ttk.Button(svc_head, text="停止", command=lambda: self.svc("stop")
                   ).pack(side="right", padx=4)
        ttk.Button(svc_head, text="重启", command=lambda: self.svc("restart")
                   ).pack(side="right", padx=4)

        scols = ("unit", "active", "sub", "desc")
        sheads = ("服务", "状态", "子状态", "描述")
        self.svc_tree = ttk.Treeview(self.frame, columns=scols,
                                     show="headings", height=8)
        for c, h in zip(scols, sheads):
            self.svc_tree.heading(c, text=h)
            self.svc_tree.column(c, width=120, anchor="w")
        self.svc_tree.column("unit", width=260)
        self.svc_tree.column("desc", width=420)
        self.svc_tree.pack(fill="both", expand=True, padx=16, pady=8)

        self.search_var = search_var
        self.reload("")

    def _reload_current(self):
        self.reload(self.search_var.get())

    def reload(self, query):
        self.app.set_status("正在加载进程…")
        self.tree.delete(*self.tree.get_children())
        q = query.strip()
        rows = process.search(q) if q else process.list_processes(
            sort=self.sort_var.get())
        for r in rows[:300]:
            self.tree.insert("", "end", values=(
                r["pid"], r["user"], f"{r['cpu']:.1f}",
                f"{r['mem']:.1f}", human_bytes(r["rss"]),
                r["comm"], (r["args"] or "")[:120]))
        # 服务
        self.svc_tree.delete(*self.svc_tree.get_children())
        for s in process.list_services():
            self.svc_tree.insert("", "end", values=(
                s["unit"], s["active"], s["sub"], s["desc"]))
        self.app.set_status(f"进程 {len(rows)} 行（最多显示 300）")

    def kill_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个进程")
            return
        pid = self.tree.item(sel[0], "values")[0]
        if not messagebox.askyesno("确认", f"结束进程 PID {pid}？"):
            return
        self.app.busy(True)
        ok, msg = process.kill(int(pid), "TERM")
        self.app.busy(False)
        messagebox.showinfo("结果", msg + ("" if ok else "\n可尝试强制结束(KILL)"))
        self._reload_current()

    def svc(self, action):
        sel = self.svc_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个服务")
            return
        unit = self.svc_tree.item(sel[0], "values")[0]
        self.app.busy(True)
        try:
            ok, msg = process.service_action(unit, action)
        finally:
            self.app.busy(False)
        messagebox.showinfo("结果", msg)
        self._reload_current()