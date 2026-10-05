#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_ifind_manual.py — 本地 iFinD 兜底通道（可选）。

背景：iFinD MCP 只能在本地会话（WorkBuddy）里调用，无法在 GitHub Actions 跑，
      因此它是「离线补数」通道：当某个公开源抓不到最新值（如 PI 后延、官网改版），
      本地跑这个脚本，把最新点写进 data/raw_ifind.json；transform.py 会把它当兜底合并。

用法（在 WorkBuddy 会话里由 AI 代跑）：
    node ".../alice-commodity-research-assistant/scripts/cli.mjs" apikey-set <KEY>   # 首次
    然后调用 iFinD 的 fetch_edb 取下列指标，落到 data/raw_ifind.json

需要抓取的 iFinD EDB 指标（名称已核实可用，勿用 search_edb 动态找——配额已满）：
    美国: 美联储总资产 / M2
    欧元区: ECB 总资产 / M2
    日本: 日本银行总资产 / M2
    中国: 货币当局总资产 / M2

本脚本只负责「把已获取的 iFinD 结果转成 raw_ifind.json 结构」，供 transform 合并。
实际取数由 AI 在会话内完成并写成本文件期望的 JSON。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))

# raw_ifind.json 目标结构（与 transform.py 读取的字段一致）：
TEMPLATE = {
    "cn": {"2026-08": None},        # 亿元
    "us": {"2026-08": None},        # 百万美元
    "ea": {"2026-08": None},        # 百万欧元
    "jp": {"2026-08": None},        # 日元
    "usdcny": {"2026-08": None},
    "usdjpy": {"2026-08": None},
    "eurusd": {"2026-08": None},
}


def main():
    path = os.path.join(DATA, "raw_ifind.json")
    if os.path.exists(path):
        d = json.load(open(path, encoding="utf-8"))
        print(f"已存在 {path}，包含 {len(d)} 个字段：{list(d)}")
        return
    # 写一个空模板（不产生垃圾数据：值为 None 会被 transform 忽略）
    os.makedirs(DATA, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2)  # 空对象 = 不参与兜底
    print(f"已初始化空兜底文件 {path}（空对象表示不使用 iFinD 兜底）")
    print("需要兜底时，由 AI 在会话内取 iFinD 数据后填入对应月份。")


if __name__ == "__main__":
    sys.exit(main())
