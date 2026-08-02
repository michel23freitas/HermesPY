"""Ferramentas Netdata: métricas de CPU, RAM, disco, temperatura, rede."""

import json
import requests

from hermes.config import NETDATA_URL
from hermes.tools.system_tools import run_cmd


def netdata_get(chart):
    try:
        r = requests.get(
            f"{NETDATA_URL}/api/v1/data",
            params={"chart": chart, "points": 1, "format": "json"},
            timeout=5,
        )
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def tool_netdata_metrics(metric="overview"):
    res = {}

    if metric in ("cpu", "overview"):
        d = netdata_get("system.cpu")
        if d and d.get("data"):
            labels = d.get("labels", [])
            vals = d["data"][0][1:]
            total = round(sum(v for v in vals if v), 2)
            res["cpu_uso_%"] = total
            res["cpu_detalhes"] = {labels[i]: round(vals[i], 2) for i in range(min(len(labels), len(vals)))}
        else:
            res["cpu"] = run_cmd("top -bn1 | grep 'Cpu' | head -1")

    if metric in ("ram", "overview"):
        d = netdata_get("system.ram")
        if d and d.get("data"):
            labels = d.get("labels", [])
            vals = d["data"][0][1:]
            res["ram_MB"] = {labels[i]: round(vals[i], 1) for i in range(min(len(labels), len(vals)))}
        else:
            res["ram"] = run_cmd("free -h")

    if metric in ("disk", "overview"):
        d = netdata_get("disk_space._")
        if d and d.get("data"):
            labels = d.get("labels", [])
            vals = d["data"][0][1:]
            res["disk_GB"] = {labels[i]: round(vals[i], 2) for i in range(min(len(labels), len(vals)))}
        else:
            res["disk"] = run_cmd("df -h /")

    if metric in ("temperature", "overview"):
        found = False
        for chart in [
            "sensors.cpu_thermal_zone0_temp_input",
            "sensors.thermal_zone0_temp_input",
            "sensors.rpi_cpu_thermal",
        ]:
            d = netdata_get(chart)
            if d and d.get("data"):
                res["temperatura_C"] = round(d["data"][0][1], 1)
                found = True
                break
        if not found:
            raw = run_cmd("cat /sys/class/thermal/thermal_zone0/temp")
            try:
                res["temperatura_C"] = round(int(raw) / 1000, 1)
            except Exception:
                res["temperatura_C"] = "indisponivel"

    if metric == "network":
        d = netdata_get("system.net")
        if d and d.get("data"):
            labels = d.get("labels", [])
            vals = d["data"][0][1:]
            res["rede_kbps"] = {labels[i]: round(vals[i], 2) for i in range(min(len(labels), len(vals)))}
        else:
            res["rede"] = run_cmd("cat /proc/net/dev | grep -v lo")

    return json.dumps(res, ensure_ascii=False, indent=2) if res else "Netdata indisponivel."
