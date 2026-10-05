#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fred.py — 从 FRED 免 Key CSV 接口抓取序列。

接口：https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES_ID>
返回两列 CSV：observation_date, VALUE（缺失值为 "."）
"""
import csv
import io
import time
import urllib.request

BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
UA = "Mozilla/5.0"


def _get(url, timeout=30, retries=3):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def fetch_series(series_id, timeout=30):
    """返回 { 'YYYY-MM-DD': float }（已剔除缺失值）"""
    text = _get(BASE + series_id, timeout=timeout)

    out = {}
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    for row in reader:
        if len(row) < 2:
            continue
        d, v = row[0].strip(), row[1].strip()
        if v in (".", "", "NA"):
            continue
        try:
            out[d] = float(v)
        except ValueError:
            continue
    return out


def to_month_end(series):
    """
    把任意频率（日/周/月）序列聚合为「按月取最后一个观测值」。
    返回 { 'YYYY-MM': float }
    """
    by_month = {}
    for d, v in sorted(series.items()):
        by_month[d[:7]] = v  # 日期升序遍历，后面的覆盖前面的 => 取月末最后一个
    return by_month


def monthly_avg(series):
    """按自然月做算术平均（用于日频汇率）。返回 { 'YYYY-MM': float }"""
    acc = {}
    for d, v in sorted(series.items()):
        acc.setdefault(d[:7], []).append(v)
    return {m: sum(vs) / len(vs) for m, vs in acc.items()}


if __name__ == "__main__":
    for sid in ["WALCL", "M2SL", "DEXCHUS"]:
        s = fetch_series(sid)
        ks = sorted(s)
        print(f"{sid}: {len(s)} obs, {ks[0]} -> {ks[-1]}, last={s[ks[-1]]}")
