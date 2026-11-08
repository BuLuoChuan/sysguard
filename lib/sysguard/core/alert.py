# -*- coding: utf-8 -*-
"""资源阈值告警：CPU / 内存 / 交换 / 磁盘 / 温度 超限检测（只读）。"""
from __future__ import annotations

from . import sysinfo

# 默认阈值（百分比 / 摄氏度），允许用户在界面自行调整
DEFAULTS = {
    "cpu": 90,
    "memory": 90,
    "swap": 90,
    "disk": 90,
    "temp": 80,
}

LABELS = {
    "cpu": "CPU 占用",
    "memory": "内存占用",
    "swap": "交换分区",
    "disk": "磁盘使用",
    "temp": "核心温度",
}


def current_values() -> dict:
    """采集当前各项资源的关键数值。"""
    mem = sysinfo.memory_info()
    swap = sysinfo.swap_info()
    disks = sysinfo.disk_usage()
    disk_max = max((d["percent"] for d in disks), default=0.0)
    temp = sysinfo.temperature()
    return {
        "cpu": sysinfo.cpu_info()["usage"],
        "memory": mem["percent"],
        "swap": swap["percent"],
        "disk": disk_max,
        "temp": temp["max"],
    }


def check(thresholds=None) -> dict:
    """对比阈值，返回 {ok: bool, alerts: [...], values: {...}}。"""
    thr = dict(DEFAULTS)
    if thresholds:
        for k, v in thresholds.items():
            try:
                thr[k] = float(v)
            except (TypeError, ValueError):
                continue
    values = current_values()
    alerts = []
    for metric, value in values.items():
        limit = thr.get(metric)
        if limit is None:
            continue
        if value >= limit:
            alerts.append({
                "metric": metric,
                "label": LABELS.get(metric, metric),
                "value": round(value, 1),
                "threshold": limit,
                "message": f"{LABELS.get(metric, metric)}已达 {value:.1f}%，"
                           f"超过阈值 {limit:.0f}%",
            })
    return {"ok": not alerts, "alerts": alerts, "values": values}