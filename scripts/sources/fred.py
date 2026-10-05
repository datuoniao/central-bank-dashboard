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
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
UA = "Mozilla/5.0"

# GitHub Actions runner（境外云 IP）访问 FRED 经常慢/偶发超时 → 放宽超时并多试几次。
# 注意：local/CI 均可用；超时值可通过环境变量 FRED_TIMEOUT 覆盖。
import os as _os
DEFAULT_TIMEOUT = int(_os.environ.get("FRED_TIMEOUT", "60"))
DEFAULT_RETRIES = int(_os.environ.get("FRED_RETRIES", "5"))


def _get(url, timeout=DEFAULT_TIMEOUT, retries=DEFAULT_RETRIES):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last = e
            if i < retries - 1:
                time.sleep(min(2.0 * (i + 1), 8.0))
    raise last


def fetch_series(series_id, timeout=DEFAULT_TIMEOUT):
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


def fetch_many(series_ids, max_workers=7, timeout=DEFAULT_TIMEOUT):
    """
    并发抓取多个 FRED 序列。
    返回 (results, failed)：
      results = { series_id: 原始日频/月频序列 dict }
      failed  = { series_id: 异常描述 }
    并发 + 放宽超时可显著缓解境外 runner 串行 7 次超时叠加的问题。
    """
    results, failed = {}, {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(fetch_series, sid, timeout): sid for sid in series_ids}
        for f in as_completed(futs):
            sid = futs[f]
            try:
                results[sid] = f.result()
            except Exception as e:  # noqa: BLE001
                failed[sid] = f"{type(e).__name__}: {e}"
    return results, failed


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
