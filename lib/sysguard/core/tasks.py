# -*- coding: utf-8 -*-
"""定时任务审计：systemd timer + cron。"""
from __future__ import annotations

import glob
import os

from . import shell


def systemd_timers() -> list[dict]:
    """systemd 定时器（timer 单元）列表。"""
    rc, out, _ = shell.run(
        ["systemctl", "list-timers", "--all", "--no-pager", "--no-legend"],
        timeout=30)
    rows = []
    if rc != 0:
        return rows
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        if ":" not in parts[0] or len(parts[0]) < 4:
            continue
        nxt = f"{parts[0]} {parts[1]}" if len(parts) > 1 else parts[0]
        rows.append({"next": nxt, "unit": parts[-2], "activates": parts[-1]})
    return rows


def cron_jobs() -> list[dict]:
    """系统级 crontab（/etc/crontab + /etc/cron.d/*）任务。"""
    jobs = []
    jobs += _parse_cron(shell.read_file("/etc/crontab"), "/etc/crontab")
    for p in sorted(glob.glob("/etc/cron.d/*")):
        if os.path.isfile(p):
            jobs += _parse_cron(shell.read_file(p), p)
    return jobs


def _parse_cron(text, source):
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split(None, 6)
        if len(fields) < 7:
            continue
        first = fields[0]
        if "=" in first or first.startswith("@"):
            continue
        rows.append({
            "source": source,
            "schedule": " ".join(fields[:5]),
            "user": fields[5],
            "command": fields[6],
        })
    return rows