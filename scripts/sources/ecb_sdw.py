#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ecb_sdw.py — 从欧洲央行数据门户 (ECB Data Portal / SDW) 抓取序列。

接口：https://data-api.ecb.europa.eu/service/data/{FLOW}/{KEY}?format=csvdata
返回长表 CSV：包含 TIME_PERIOD 与 OBS_VALUE 等列。
"""
import csv
import io
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


def fetch_dataflow(flow, key, timeout=40):
    """
    返回 { 'YYYY-MM-DD': float }（按 TIME_PERIOD 升序）。
    常见：
      欧元区 M2  = flow='BSI', key='M.U2.Y.V.M20.X.1.U2.2300.Z01.E'
    """
    url = f"https://data-api.ecb.europa.eu/service/data/{flow}/{key}?format=csvdata"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/csv"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8", errors="replace")

    out = {}
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        tp = (row.get("TIME_PERIOD") or "").strip()
        ov = (row.get("OBS_VALUE") or "").strip()
        if not tp or not ov:
            continue
        # TIME_PERIOD 可能是 YYYY / YYYY-MM / YYYY-MM-DD
        if len(tp) == 4:
            tp = tp + "-12-31"
        elif len(tp) == 7:
            tp = tp + "-01"
        try:
            out[tp] = float(ov)
        except ValueError:
            continue
    return dict(sorted(out.items()))


def to_month_end(series):
    by_month = {}
    for d, v in sorted(series.items()):
        by_month[d[:7]] = v
    return by_month


if __name__ == "__main__":
    s = fetch_dataflow("BSI", "M.U2.Y.V.M20.X.1.U2.2300.Z01.E")
    ks = sorted(s)
    print(f"EA M2: {len(s)} obs, {ks[0]} -> {ks[-1]}, last={s[ks[-1]]}")
