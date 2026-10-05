#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
worldbank.py — 从世界银行 Pink Sheet (CMO-Historical-Data-Monthly.xlsx) 抓黄金/铜/原油月度价。

实际结构（已实测）：
  Sheet 'Monthly Prices'：
    第 5 行 = 商品名（如 'Gold' / 'Copper' / 'Crude oil, Brent'）
    第 6 行 = 单位
    第 7 行起 = 数据，A 列 = '1960M01' 形式的月份
  ⚠️ 该文件更新有滞后（当前版本 "Updated on January 06, 2025"），黄金/铜可能落后数月。
     最新月份由 iFinD / FRED 兜底补位。

性能注意：openpyxl 在 read_only 模式下逐格 ws.cell(row, col) 是 O(n^2) 级慢；
         必须用一次 iter_rows(values_only=True) 把整表拉成元组列表再索引。
"""
import io
import time
import urllib.request

URL = (
    "https://thedocs.worldbank.org/en/doc/"
    "18675f1d1639c7a34d463f59263ba0a2-0050012025/"
    "related/CMO-Historical-Data-Monthly.xlsx"
)
UA = "Mozilla/5.0"
NAME_ROW = 5  # 1-based 行号

# 目标商品：逻辑名 -> Pink Sheet 第 5 行中的商品名（已小写去空格）
TARGETS = {
    "gold": "gold",
    "copper": "copper",
    "brent": "crude oil, brent",
}


def _download(timeout=90, retries=3):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return io.BytesIO(resp.read())
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2.0 * (i + 1))
    raise last


def _month_to_ym(tag):
    """'1960M01' -> '1960-01'；也兼容 datetime / '1960-01' / '1960-01-01'"""
    if tag is None:
        return None
    if hasattr(tag, "year"):  # datetime / date
        return f"{tag.year:04d}-{tag.month:02d}"
    tag = str(tag).strip()
    if len(tag) == 7 and tag[4] == "M" and tag[:4].isdigit():
        return f"{tag[:4]}-{tag[5:]}"
    if len(tag) >= 7 and tag[4] == "-" and tag[:4].isdigit():
        return tag[:7]
    return None


def fetch_pink_sheet():
    """返回 {'gold': {...}, 'copper': {...}, 'brent': {...}}，键为 'YYYY-MM'"""
    import openpyxl

    wb = openpyxl.load_workbook(_download(), data_only=True, read_only=True)
    ws = wb["Monthly Prices"]
    rows = list(ws.iter_rows(values_only=True))  # 一次拉全，避免逐格访问

    if len(rows) < NAME_ROW:
        raise RuntimeError("Pink Sheet 行数异常")

    # 建立 商品名(小写去空格) -> 0-based 列索引
    name_row = rows[NAME_ROW - 1]
    col_of = {}
    for idx, v in enumerate(name_row):
        if isinstance(v, str) and v.strip():
            col_of[v.strip().lower()] = idx

    used = {}
    for key, name in TARGETS.items():
        if name not in col_of:
            raise RuntimeError(f"Pink Sheet 未找到列: {key!r} -> {name!r}")
        used[key] = col_of[name]

    result = {k: {} for k in TARGETS}
    for r in rows[NAME_ROW:]:  # 数据从第 6 行(0-based 5) 开始（含单位行，month 解析会跳过）
        mon = _month_to_ym(r[0] if r else None)
        if not mon:
            continue
        for key, ci in used.items():
            val = r[ci] if ci < len(r) else None
            if isinstance(val, (int, float)):
                result[key][mon] = float(val)

    wb.close()
    return result


if __name__ == "__main__":
    d = fetch_pink_sheet()
    for k, v in d.items():
        ks = sorted(v)
        print(f"{k}: {len(v)} months, {ks[0]} -> {ks[-1]}, last={v[ks[-1]]}")
