/* ============================================================
   G4 央行资产负债表 · M2 · 大宗商品 联动看板 — 前端渲染
   依赖：ECharts 5（本地内置 assets/vendor/ + 多 CDN 兜底）
   数据：data/dashboard.json
   图表清单：
     1. G4 央行总资产（合计）
     2. 四国央行总资产（分国对比）
     3. 央行总资产 · 同比
     4. 央行总资产结构占比（堆叠面积）
     5. 美/欧/日 央行总资产（分国小图）
     6. G4 M2 总量 + 同比
     7. 四经济体 M2 分列
     8. 大宗商品：Brent / 黄金 / 铜（归一化指数）
     9. 黄金 vs G4 央行资产同比（双轴对照）
    10. 铜 vs 中国央行资产同比
    11. 自由对照：商品 × 央行（可交互切换，支持 URL 深链）
    12. 全部商品 × 央行 相关系数矩阵（可点击切换）
    13. 相关性简表
   ============================================================ */
(function () {
  "use strict";

  var GCOLOR = { cn: "#d93636", us: "#2f6fed", ea: "#7a4fd0", jp: "#e08a1e", g4: "#111827" };
  var GNAME = { cn: "中国", us: "美国", ea: "欧元区", jp: "日本", g4: "G4 合计" };
  var PCOLOR = { brent: "#2c3e50", gold: "#d4a017", copper: "#b06a3b" };
  var PNAME = { brent: "Brent 原油", gold: "黄金", copper: "铜" };
  var FNAME = { usdcny: "USD/CNY", usdjpy: "USD/JPY", eurusd: "EUR/USD" };

  // 自由对照可选维度（商品 × 央行）
  var PRICE_KEYS = ["gold", "copper", "brent"];
  var BAL_KEYS = ["g4", "cn", "us", "ea", "jp"];
  var FREE = { price: "gold", bal: "g4" };   // 自由对照当前选择

  var DATA = null;
  var charts = [];

  // ---------------------------------------------------------- 工具
  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  function isDark() { return document.documentElement.getAttribute("data-theme") === "dark"; }
  function fmt(v, d) {
    if (v === null || v === undefined || isNaN(v)) return "—";
    d = d === undefined ? 1 : d;
    return Number(v).toLocaleString("zh-CN", { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function pct(v) {
    if (v === null || v === undefined || isNaN(v)) return "—";
    return (v >= 0 ? "+" : "") + Number(v).toFixed(2) + "%";
  }
  function cls(v) {
    if (v === null || v === undefined || isNaN(v)) return "flat";
    return v > 0 ? "up" : v < 0 ? "down" : "flat";
  }
  function arrow(v) {
    if (v === null || v === undefined || isNaN(v)) return "";
    return v > 0 ? "▲ " : v < 0 ? "▼ " : "— ";
  }
  function months(series) { return series.map(function (r) { return r.m; }); }
  function vals(series) { return series.map(function (r) { return r.v; }); }
  function yoys(series) { return series.map(function (r) { return r.yoy; }); }

  function sliceFrom(series, from) {
    return series.filter(function (r) { return r.m >= from; });
  }
  // 把 {m: 值} 序列对齐到给定月份轴
  function alignTo(series, axis) {
    var map = {};
    series.forEach(function (r) { map[r.m] = r; });
    return axis.map(function (m) {
      var r = map[m];
      return r ? r.v : null;
    });
  }

  // ---------------------------------------------------------- 主题
  function themeBase() {
    var dark = isDark();
    return {
      textStyle: { color: dark ? "#e8ecf2" : "#1a1d24", fontFamily: "inherit" },
      grid: { left: 58, right: 24, top: 42, bottom: 42, containLabel: false },
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: dark ? "rgba(23,27,34,.95)" : "rgba(255,255,255,.97)",
        borderColor: dark ? "#2a313c" : "#e3e6ec",
        borderWidth: 1,
        textStyle: { color: dark ? "#e8ecf2" : "#1a1d24", fontSize: 12 },
        axisPointer: { type: "line", lineStyle: { color: dark ? "#3a4250" : "#c8cdd8" } },
        extraCssText: "border-radius:10px;box-shadow:0 6px 22px rgba(0,0,0,.14);"
      },
      legend: {
        top: 6, right: 8, left: 8,
        textStyle: { color: dark ? "#a8b1c0" : "#5a6272", fontSize: 11.5 },
        icon: "roundRect", itemWidth: 12, itemHeight: 8
      },
      xAxis: axisX(),
      yAxis: axisY()
    };
  }
  function axisX() {
    var dark = isDark();
    return {
      type: "category", boundaryGap: false,
      axisLine: { lineStyle: { color: dark ? "#2a313c" : "#dfe3ea" } },
      axisTick: { show: false },
      axisLabel: { color: dark ? "#8b94a6" : "#8b94a6", fontSize: 11 },
      splitLine: { show: false }
    };
  }
  function axisY(fmtStr) {
    var dark = isDark();
    return {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: dark ? "#8b94a6" : "#8b94a6", fontSize: 11,
        formatter: fmtStr || function (v) { return bigNum(v); }
      },
      splitLine: { lineStyle: { color: dark ? "rgba(255,255,255,.06)" : "rgba(20,25,40,.06)" } }
    };
  }
  function bigNum(v) {
    var a = Math.abs(v);
    if (a >= 1e4) return (v / 1e4).toFixed(a >= 1e5 ? 0 : 1) + "万";
    return v.toFixed(0);
  }

  function mk(dom, option) {
    var c = echarts.init(dom, null, { renderer: "canvas" });
    c.setOption(option);
    charts.push(c);
    return c;
  }

  // ---------------------------------------------------------- 图表
  // 1. G4 央行总资产（合计，单线突出扩表/缩表大趋势）
  function chartG4Assets() {
    var b = DATA.balance;
    var g4 = b.g4 || [];
    var opt = themeBase();
    opt.grid = { left: 62, right: 26, top: 44, bottom: 42 };
    opt.tooltip.valueFormatter = function (v) { return v == null ? "—" : fmt(v, 0) + " 亿美元"; };
    opt.legend.data = ["G4 央行总资产合计"];
    var axis = months(g4);
    opt.xAxis.data = axis;
    opt.yAxis = axisY();
    opt.series = [{
      name: "G4 央行总资产合计", type: "line", data: vals(g4),
      smooth: true, symbol: "none",
      lineStyle: { width: 2.8, color: GCOLOR.g4 },
      areaStyle: { color: isDark() ? "rgba(232,236,242,.10)" : "rgba(17,24,39,.07)" }
    }];
    mk(document.getElementById("c-g4assets"), opt);
  }

  // 1b. 四国央行总资产（去掉合计，让四国差异看得清）
  function chartCountries() {
    var b = DATA.balance;
    var axis = months(b.g4 || []);
    var opt = themeBase();
    opt.grid = { left: 62, right: 26, top: 44, bottom: 42 };
    opt.tooltip.valueFormatter = function (v) { return v == null ? "—" : fmt(v, 0) + " 亿美元"; };
    opt.legend.data = ["中国", "美国", "欧元区", "日本"];
    opt.xAxis.data = axis;
    opt.yAxis = axisY();
    opt.series = ["cn", "us", "ea", "jp"].map(function (k) {
      return {
        name: GNAME[k], type: "line", smooth: true, symbol: "none",
        lineStyle: { width: 2.1, color: GCOLOR[k] },
        data: alignTo(b[k], axis)
      };
    });
    mk(document.getElementById("c-countries"), opt);
  }

  // 2. G4 央行总资产 · 同比
  function chartG4Yoy() {
    var b = DATA.balance;
    var g4 = b.g4 || [];
    var opt = themeBase();
    opt.tooltip.valueFormatter = function (v) { return v == null ? "—" : fmt(v, 2) + "%"; };
    opt.legend.data = ["G4 同比", "中国", "美国", "欧元区", "日本"];
    opt.xAxis.data = months(g4);
    opt.yAxis = axisY(function (v) { return v.toFixed(0) + "%"; });
    opt.series = [
      { name: "G4 同比", type: "line", data: yoys(g4), smooth: true, symbol: "none",
        lineStyle: { width: 2.6, color: GCOLOR.g4 } },
      { name: "中国", type: "line", data: yoys(b.cn), smooth: true, symbol: "none", lineStyle: { width: 1.5, color: GCOLOR.cn } },
      { name: "美国", type: "line", data: yoys(b.us), smooth: true, symbol: "none", lineStyle: { width: 1.5, color: GCOLOR.us } },
      { name: "欧元区", type: "line", data: yoys(b.ea), smooth: true, symbol: "none", lineStyle: { width: 1.5, color: GCOLOR.ea } },
      { name: "日本", type: "line", data: yoys(b.jp), smooth: true, symbol: "none", lineStyle: { width: 1.5, color: GCOLOR.jp } }
    ];
    mk(document.getElementById("c-g4yoy"), opt);
  }

  // 3. 结构占比（堆叠面积）
  function chartStructure() {
    var b = DATA.balance;
    var axis = months(b.g4 || []);
    var opt = themeBase();
    opt.tooltip.valueFormatter = function (v) { return v == null ? "—" : fmt(v, 0) + " 亿美元"; };
    opt.legend.data = ["中国", "美国", "欧元区", "日本"];
    opt.xAxis.data = axis;
    opt.yAxis = axisY();
    function area(name, key) {
      return {
        name: name, type: "line", stack: "g4", smooth: true, symbol: "none",
        areaStyle: { opacity: .82 }, lineStyle: { width: 0 },
        emphasis: { focus: "series" },
        itemStyle: { color: GCOLOR[key] },
        data: alignTo(b[key], axis)
      };
    }
    opt.series = [area("中国", "cn"), area("美国", "us"), area("欧元区", "ea"), area("日本", "jp")];
    mk(document.getElementById("c-structure"), opt);
  }

  // 4. 分国小图（美/欧/日）
  function chartOthers() {
    var b = DATA.balance;
    var axis = months(b.us || []);
    var opt = themeBase();
    opt.grid = { left: 58, right: 20, top: 30, bottom: 34 };
    opt.legend.data = ["美国", "欧元区", "日本"];
    opt.xAxis.data = axis;
    opt.yAxis = axisY();
    opt.tooltip.valueFormatter = function (v) { return v == null ? "—" : fmt(v, 0) + " 亿美元"; };
    opt.series = ["us", "ea", "jp"].map(function (k) {
      return {
        name: GNAME[k], type: "line", smooth: true, symbol: "none",
        lineStyle: { width: 1.9, color: GCOLOR[k] },
        data: alignTo(b[k], axis)
      };
    });
    mk(document.getElementById("c-others"), opt);
  }

  // 5. G4 M2 总量 + 同比
  function g4M2() {
    var m2 = DATA.m2;
    var keys = Object.keys(m2).filter(function (k) { return m2[k] && m2[k].length; });
    var map = {};
    keys.forEach(function (k) { m2[k].forEach(function (r) { map[r.m] = map[r.m] || {}; map[r.m][k] = r.v; }); });
    var axis = Object.keys(map).sort();
    var total = axis.map(function (m) {
      var s = 0, n = 0;
      keys.forEach(function (k) { if (map[m][k] != null) { s += map[m][k]; n++; } });
      return n === keys.length ? s : null;
    });
    var totSeries = axis.map(function (m, i) { return { m: m, v: total[i] }; });
    return { axis: axis, total: totSeries, keys: keys };
  }

  function chartM2Total() {
    var g = g4M2();
    var opt = themeBase();
    opt.legend.data = ["G4 M2 合计", "同比（右）"];
    opt.xAxis.data = g.axis;
    opt.yAxis = [axisY(), {
      type: "value", position: "right", axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: isDark() ? "#8b94a6" : "#8b94a6", fontSize: 11, formatter: function (v) { return v.toFixed(0) + "%"; } },
      splitLine: { show: false }
    }];
    opt.tooltip.valueFormatter = function (v) { return v == null ? "—" : (Math.abs(v) < 100 ? fmt(v, 2) + "%" : fmt(v, 0)); };
    var yoyArr = g.total.map(function (r, i) {
      var j = g.axis.indexOf(addMonth(r.m, -12));
      if (j < 0 || !g.total[j] || g.total[j].v == null || r.v == null) return null;
      return +(((r.v / g.total[j].v) - 1) * 100).toFixed(2);
    });
    opt.series = [
      { name: "G4 M2 合计", type: "line", data: g.total.map(function (r) { return r.v; }),
        smooth: true, symbol: "none", lineStyle: { width: 2.6, color: "#0f766e" },
        areaStyle: { color: isDark() ? "rgba(15,118,110,.12)" : "rgba(15,118,110,.08)" } },
      { name: "同比（右）", type: "line", yAxisIndex: 1, data: yoyArr,
        smooth: true, symbol: "none", lineStyle: { width: 1.8, color: "#e11d48", type: "dashed" } }
    ];
    mk(document.getElementById("c-m2total"), opt);
  }

  // 6. 四经济体 M2
  function chartM2ByG() {
    var m2 = DATA.m2;
    var keys = ["cn", "us", "ea", "jp"].filter(function (k) { return m2[k] && m2[k].length; });
    var axis = [];
    keys.forEach(function (k) { months(m2[k]).forEach(function (m) { if (axis.indexOf(m) < 0) axis.push(m); }); });
    axis.sort();
    var opt = themeBase();
    opt.legend.data = keys.map(function (k) { return GNAME[k]; });
    opt.tooltip.valueFormatter = function (v) { return v == null ? "—" : fmt(v, 0) + " 亿美元"; };
    opt.xAxis.data = axis;
    opt.yAxis = axisY();
    opt.series = keys.map(function (k) {
      return {
        name: GNAME[k], type: "line", smooth: true, symbol: "none",
        lineStyle: { width: 1.9, color: GCOLOR[k] },
        data: alignTo(m2[k], axis)
      };
    });
    mk(document.getElementById("c-m2g"), opt);
  }

  // 7. 商品归一化指数（首月=100）
  function chartPrices() {
    var p = DATA.prices;
    var keys = ["brent", "gold", "copper"].filter(function (k) { return p[k] && p[k].length; });
    var axis = [];
    keys.forEach(function (k) { months(p[k]).forEach(function (m) { if (axis.indexOf(m) < 0) axis.push(m); }); });
    axis.sort();
    var opt = themeBase();
    opt.legend.data = keys.map(function (k) { return PNAME[k]; });
    opt.tooltip.valueFormatter = function (v) { return v == null ? "—" : fmt(v, 1); };
    opt.xAxis.data = axis;
    opt.yAxis = axisY(function (v) { return v.toFixed(0); });
    opt.series = keys.map(function (k) {
      var arr = alignTo(p[k], axis);
      var base = null;
      for (var i = 0; i < arr.length; i++) { if (arr[i] != null) { base = arr[i]; break; } }
      return {
        name: PNAME[k], type: "line", smooth: true, symbol: "none",
        lineStyle: { width: 2.1, color: PCOLOR[k] },
        data: arr.map(function (v) { return v == null || !base ? null : +((v / base) * 100).toFixed(1); })
      };
    });
    mk(document.getElementById("c-prices"), opt);
  }

  // 8/9. 双轴对照：某国央行资产同比 vs 商品同比
  //      返回该对照的皮尔逊相关系数（基于对齐后的同比序列）
  function chartPair(domId, balKey, priceKey) {
    var b = DATA.balance, p = DATA.prices;
    var dom = document.getElementById(domId);
    if (!dom) return null;
    if (!p[priceKey] || !(b[balKey] || b.g4)) {
      dom.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-3)">该组合暂无数据</div>';
      return null;
    }
    // 合并两者月份轴，避免因天数不同错位（价格通常比央行资产多 1 个月）
    var axis = [];
    months(b[balKey] || b.g4).forEach(function (m) { if (axis.indexOf(m) < 0) axis.push(m); });
    months(p[priceKey]).forEach(function (m) { if (axis.indexOf(m) < 0) axis.push(m); });
    axis.sort();
    var opt = themeBase();
    opt.legend.data = [GNAME[balKey] + " 资产同比", PNAME[priceKey] + " 同比"];
    opt.xAxis.data = axis;
    opt.yAxis = [
      axisY(function (v) { return v.toFixed(0) + "%"; }),
      { type: "value", position: "right", axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: isDark() ? "#8b94a6" : "#8b94a6", fontSize: 11, formatter: function (v) { return v.toFixed(0) + "%"; } },
        splitLine: { show: false } }
    ];
    opt.tooltip.valueFormatter = function (v) { return v == null ? "—" : fmt(v, 2) + "%"; };
    // 按 axis 对齐同比值（用 map 而非索引）
    function alignYoY(series) {
      var map = {};
      series.forEach(function (r) { map[r.m] = r.yoy; });
      return axis.map(function (m) { return map.hasOwnProperty(m) ? map[m] : null; });
    }
    var a1 = alignYoY(b[balKey] || b.g4);
    var a2 = alignYoY(p[priceKey]);
    opt.series = [
      { name: GNAME[balKey] + " 资产同比", type: "line", data: a1,
        smooth: true, symbol: "none", lineStyle: { width: 2.2, color: GCOLOR[balKey] } },
      { name: PNAME[priceKey] + " 同比", type: "line", yAxisIndex: 1, data: a2,
        smooth: true, symbol: "none", lineStyle: { width: 2.2, color: PCOLOR[priceKey] } }
    ];
    mk(dom, opt);
    return pearson(a1, a2);
  }

  // 皮尔逊相关系数（跳过任一侧为 null 的月份）
  function pearson(xs, ys) {
    var n = 0, sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0;
    for (var i = 0; i < xs.length; i++) {
      var x = xs[i], y = ys[i];
      if (x == null || y == null || isNaN(x) || isNaN(y)) continue;
      n++; sx += x; sy += y; sxx += x * x; syy += y * y; sxy += x * y;
    }
    if (n < 3) return null;
    var num = n * sxy - sx * sy;
    var den = Math.sqrt((n * sxx - sx * sx) * (n * syy - sy * sy));
    return den === 0 ? null : num / den;
  }

  // 11. 自由对照：商品 × 央行（可交互切换）
  function chartFree() {
    var r = chartPair("c-pairfree", FREE.bal, FREE.price);
    var box = document.getElementById("pk-corr");
    if (box) {
      if (r == null) {
        box.innerHTML = "—";
      } else {
        var abs = Math.abs(r);
        var strength = abs >= .6 ? "强" : abs >= .3 ? "中等" : abs >= .15 ? "弱" : "几乎无";
        var dir = r >= 0 ? "正相关" : "负相关";
        box.innerHTML = "同比相关系数 r = <b class='" + cls(r) + "'>" + r.toFixed(3) +
          "</b>（" + strength + dir + "）· " + PNAME[FREE.price] + " × " + GNAME[FREE.bal];
      }
    }
    // 高亮矩阵中对应单元格
    var cells = document.querySelectorAll("#corr-matrix td");
    cells.forEach(function (td) {
      td.classList.toggle("on", td.dataset.price === FREE.price && td.dataset.bal === FREE.bal);
    });
    writeHash();
  }

  // 12. 全部商品 × 央行 相关系数矩阵（可点击切换）
  function renderCorrMatrix() {
    var box = document.getElementById("corr-matrix");
    if (!box) return;
    var b = DATA.balance, p = DATA.prices;
    // 预取各序列的同比 map
    function yoyMap(series) {
      var m = {};
      if (series) series.forEach(function (r) { m[r.m] = r.yoy; });
      return m;
    }
    var balYo = {}; BAL_KEYS.forEach(function (k) { balYo[k] = yoyMap(b[k]); });
    var priYo = {}; PRICE_KEYS.forEach(function (k) { priYo[k] = yoyMap(p[k]); });

    function corrOf(bk, pk) {
      var bm = balYo[bk], pm = priYo[pk];
      // 取并集月份，逐月取同比
      var axis = Object.keys(bm);
      Object.keys(pm).forEach(function (m) { if (axis.indexOf(m) < 0) axis.push(m); });
      var xs = [], ys = [];
      axis.forEach(function (m) {
        var x = bm[m], y = pm[m];
        if (x == null || y == null) return;
        xs.push(x); ys.push(y);
      });
      return pearson(xs, ys);
    }

    var html = '<table><thead><tr><th class="rowh">央行 \\ 商品</th>';
    PRICE_KEYS.forEach(function (pk) {
      html += '<th><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:' +
        PCOLOR[pk] + ';margin-right:5px"></span>' + PNAME[pk] + '</th>';
    });
    html += "</tr></thead><tbody>";
    BAL_KEYS.forEach(function (bk) {
      html += '<tr><th class="rowh"><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:' +
        GCOLOR[bk] + ';margin-right:5px"></span>' + GNAME[bk] + '</th>';
      PRICE_KEYS.forEach(function (pk) {
        var r = corrOf(bk, pk);
        if (r == null) {
          html += '<td class="na" data-bal="' + bk + '" data-price="' + pk + '">—</td>';
        } else {
          // 背景强度：|r| 越大越深；涨红跌绿
          var alpha = Math.min(Math.abs(r), 1) * 0.42 + 0.08;
          var base = r >= 0 ? "217,54,54" : "20,154,90";
          html += '<td data-bal="' + bk + '" data-price="' + pk + '" class="' + cls(r) +
            '" style="background:rgba(' + base + ',' + alpha.toFixed(2) + ')">' + r.toFixed(3) + '</td>';
        }
      });
      html += "</tr>";
    });
    html += "</tbody></table>";
    box.innerHTML = html;

    // 点击切换上方自由对照图
    box.querySelectorAll("td[data-bal]").forEach(function (td) {
      td.addEventListener("click", function () {
        if (td.classList.contains("na")) return;
        FREE.bal = td.dataset.bal;
        FREE.price = td.dataset.price;
        syncPickerButtons();
        redrawFree();
      });
    });
  }

  // 重建「自由对照」相关图表（切换选择时调用，不动其它图）
  function redrawFree() {
    disposeByDom("c-pairfree");
    chartFree();
  }

  // 只销毁某个 dom 上的实例，保留其它图表
  function disposeByDom(domId) {
    var dom = document.getElementById(domId);
    if (!dom) return;
    for (var i = charts.length - 1; i >= 0; i--) {
      var c = charts[i];
      var cd = null;
      try { cd = c.getDom ? c.getDom() : null; } catch (e) { cd = null; }
      if (cd === dom) {
        try { c.dispose(); } catch (e) { /* noop */ }
        charts.splice(i, 1);
      }
    }
  }

  // 同步分段按钮的 active 状态
  function syncPickerButtons() {
    var pw = document.getElementById("pk-price");
    var bw = document.getElementById("pk-bal");
    if (pw) [].forEach.call(pw.querySelectorAll("button"), function (btn) {
      btn.classList.toggle("active", btn.dataset.k === FREE.price);
    });
    if (bw) [].forEach.call(bw.querySelectorAll("button"), function (btn) {
      btn.classList.toggle("active", btn.dataset.k === FREE.bal);
    });
  }

  // 构建分段选择器
  function buildPicker() {
    var pw = document.getElementById("pk-price");
    var bw = document.getElementById("pk-bal");
    if (pw) {
      pw.innerHTML = PRICE_KEYS.map(function (k) {
        return '<button data-k="' + k + '">' + PNAME[k] + "</button>";
      }).join("");
      pw.addEventListener("click", function (e) {
        var btn = e.target.closest("button[data-k]");
        if (!btn) return;
        FREE.price = btn.dataset.k;
        syncPickerButtons();
        redrawFree();
      });
    }
    if (bw) {
      bw.innerHTML = BAL_KEYS.map(function (k) {
        return '<button data-k="' + k + '">' + (k === "g4" ? "G4" : GNAME[k]) + "</button>";
      }).join("");
      bw.addEventListener("click", function (e) {
        var btn = e.target.closest("button[data-k]");
        if (!btn) return;
        FREE.bal = btn.dataset.k;
        syncPickerButtons();
        redrawFree();
      });
    }
    syncPickerButtons();
  }

  // 支持 URL hash 深链：index.html#price=copper&bal=cn
  // 便于分享特定对照，也便于自动化截图验证。
  function applyHash() {
    var h = (location.hash || "").replace(/^#/, "");
    if (!h) return;
    var q = {};
    h.split("&").forEach(function (kv) {
      var i = kv.indexOf("=");
      if (i > 0) q[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1));
    });
    if (q.price && PRICE_KEYS.indexOf(q.price) >= 0) FREE.price = q.price;
    if (q.bal && BAL_KEYS.indexOf(q.bal) >= 0) FREE.bal = q.bal;
  }

  // 把当前选择写回 hash（不产生历史记录）
  function writeHash() {
    try {
      var s = "#price=" + FREE.price + "&bal=" + FREE.bal;
      if (history.replaceState) history.replaceState(null, "", s);
    } catch (e) { /* noop */ }
  }

  // 10. 相关性表
  function renderCorr() {
    var c = DATA.correlations || {};
    var rows = [
      ["g4_yoy_vs_gold_yoy", "G4 央行资产同比 ↔ 金价同比"],
      ["g4_yoy_vs_copper_yoy", "G4 央行资产同比 ↔ 铜价同比"],
      ["g4_yoy_vs_brent_yoy", "G4 央行资产同比 ↔ 布伦特同比"],
      ["us_yoy_vs_gold_yoy", "美国央行资产同比 ↔ 金价同比"],
      ["cn_yoy_vs_copper_yoy", "中国央行资产同比 ↔ 铜价同比"],
      ["m2_g4_yoy_vs_gold_yoy", "G4 M2 同比 ↔ 金价同比"]
    ];
    var html = '<table class="corr-table"><thead><tr><th>关系</th><th style="width:80px">相关系数</th><th style="width:150px">强度</th><th style="width:60px">样本</th></tr></thead><tbody>';
    rows.forEach(function (r) {
      var o = c[r[0]];
      if (!o) { html += '<tr><td>' + r[1] + '</td><td class="r">—</td><td>—</td><td>—</td></tr>'; return; }
      var v = o.r;
      var w = Math.min(Math.abs(v) * 50, 50);
      var dir = v >= 0 ? "left" : "left";
      var style = v >= 0
        ? 'left:50%;width:' + w + '%;background:' + (v >= 0 ? "var(--up)" : "var(--down)") + ';'
        : 'right:50%;left:auto;width:' + w + '%;background:var(--down);';
      var strength = Math.abs(v) >= .6 ? "强" : Math.abs(v) >= .3 ? "中等" : Math.abs(v) >= .15 ? "弱" : "几乎无";
      html += '<tr><td>' + r[1] + '</td>' +
        '<td class="r ' + cls(v) + '">' + v.toFixed(3) + '</td>' +
        '<td><div class="corr-bar"><i style="' + style + '"></i></div></td>' +
        '<td style="color:var(--text-3)">' + o.n + '</td></tr>';
    });
    html += "</tbody></table>";
    document.getElementById("corr-box").innerHTML = html;
  }

  function addMonth(ym, n) {
    var y = +ym.slice(0, 4), m = +ym.slice(5, 7);
    var t = y * 12 + (m - 1) + n;
    return String(Math.floor(t / 12)).padStart(4, "0") + "-" + String((t % 12) + 1).padStart(2, "0");
  }

  // ---------------------------------------------------------- KPI
  function renderKpis() {
    var b = DATA.balance, m2 = DATA.m2, p = DATA.prices;
    var items = [];

    function lastOf(s) { return s && s.length ? s[s.length - 1] : null; }

    var g4 = lastOf(b.g4);
    if (g4) items.push({ c: GCOLOR.g4, l: "G4 央行总资产", v: fmt(g4.v, 0), u: "亿美元", m: g4.m, yoy: g4.yoy });
    ["cn", "us", "ea", "jp"].forEach(function (k) {
      var r = lastOf(b[k]);
      if (r) items.push({ c: GCOLOR[k], l: GNAME[k] + " 央行资产", v: fmt(r.v, 0), u: "亿美元", m: r.m, yoy: r.yoy });
    });
    var g = g4M2();
    var gt = g.total[g.total.length - 1];
    if (gt) {
      var j = g.axis.indexOf(addMonth(gt.m, -12));
      var yv = (j >= 0 && g.total[j] && g.total[j].v) ? ((gt.v / g.total[j].v - 1) * 100) : null;
      items.push({ c: "#0f766e", l: "G4 M2 合计", v: fmt(gt.v, 0), u: "亿美元", m: gt.m, yoy: yv });
    }
    [["gold", "黄金", PCOLOR.gold, "$/oz"], ["copper", "铜", PCOLOR.copper, "$/t"], ["brent", "Brent 原油", PCOLOR.brent, "$/bbl"]].forEach(function (t) {
      var r = lastOf(p[t[0]]);
      if (r) items.push({ c: t[2], l: t[1], v: fmt(r.v, r.v > 1000 ? 0 : 1), u: t[3], m: r.m, yoy: r.yoy, price: true });
    });

    var html = items.map(function (it) {
      return '<div class="kpi" style="--kcolor:' + it.c + '">' +
        '<div class="k-label">' + it.l + ' <span style="color:var(--text-3)">· ' + it.m + '</span></div>' +
        '<div class="k-value">' + it.v + '<span class="k-unit">' + it.u + '</span></div>' +
        '<div class="k-sub"><span class="' + cls(it.yoy) + '">' + arrow(it.yoy) + pct(it.yoy) + '</span>' +
        '<span style="color:var(--text-3)">同比</span></div></div>';
    }).join("");
    document.getElementById("kpis").innerHTML = html;
  }

  function renderHeaderMeta() {
    var m = DATA.meta;
    document.getElementById("gen-time").textContent = (m.generated_at || "").replace("T", " ").slice(0, 16);
    document.getElementById("latest-balance").textContent = m.latest_balance || "—";
    document.getElementById("latest-m2").textContent = m.latest_m2 || "—";
    document.getElementById("latest-price").textContent = m.latest_price || "—";
    document.getElementById("unit-note").textContent = m.unit || "";
  }

  // ---------------------------------------------------------- 初始化
  function buildAll() {
    charts.forEach(function (c) { c.dispose(); });
    charts = [];
    renderKpis();
    chartG4Assets();
    chartCountries();
    chartG4Yoy();
    chartStructure();
    chartOthers();
    chartM2Total();
    chartM2ByG();
    chartPrices();
    chartPair("c-gold", "g4", "gold");
    chartPair("c-copper", "cn", "copper");
    applyHash();
    buildPicker();
    chartFree();
    renderCorrMatrix();
    renderCorr();
  }

  function initTheme() {
    var saved = localStorage.getItem("cbdash-theme");
    var theme = saved || (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", theme);
    updateThemeBtn();
  }
  function updateThemeBtn() {
    var btn = document.getElementById("theme-btn");
    if (btn) btn.textContent = isDark() ? "☀" : "☾";
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTheme();
    document.getElementById("theme-btn").addEventListener("click", function () {
      var next = isDark() ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("cbdash-theme", next);
      updateThemeBtn();
      if (DATA && window.echarts) buildAll();
    });
    window.addEventListener("resize", function () {
      charts.forEach(function (c) { c.resize(); });
    });

    // ---- 1) 先确保 ECharts 就绪（index.html 里已做本地+多CDN兜底加载）----
    var echartsReady = new Promise(function (resolve) {
      if (window.echarts) return resolve();
      // 已加载完成但 echarts 缺失（全部失败）的情况，事件会立即派发
      window.addEventListener("echarts-ready", function () { resolve(); });
    });

    // ---- 2) 再取数据 ----
    var dataReady = fetch("data/dashboard.json", { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });

    // ---- 3) 两者都就绪后才渲染（避免 echarts 未定义时抛错）----
    Promise.all([echartsReady, dataReady])
      .then(function (res) {
        var d = res[1];
        DATA = d;
        renderHeaderMeta();
        if (!window.echarts) {
          // ECharts 实在加载不出来：仍展示 KPI 与相关性表等非图表内容
          document.getElementById("loading").innerHTML =
            '<div style="color:var(--up)">图表库（ECharts）加载失败，图表无法渲染。' +
            '<br><span style="color:var(--text-3);font-size:13px">已改用本地 assets/vendor/echarts.min.js，请确认该文件存在；' +
            'KPI 与相关性数据仍可正常查看。</span></div>';
          renderKpis();
          renderCorrMatrix();
          renderCorr();
          return;
        }
        buildAll();
        document.getElementById("loading").style.display = "none";
      })
      .catch(function (e) {
        document.getElementById("loading").innerHTML =
          '<div style="color:var(--up)">数据加载失败：' + e.message +
          '<br><span style="color:var(--text-3);font-size:13px">请确认 data/dashboard.json 存在，并通过 http 服务打开本页</span></div>';
      });
  });
})();
