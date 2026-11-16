import json, sys, math

def sma(a, n):
    return [None if i < n - 1 else sum(a[i-n+1:i+1]) / n for i in range(len(a))]

def ema(a, n):
    k, out, e = 2 / (n + 1), [], None
    for x in a:
        e = x if e is None else x * k + e * (1 - k)
        out.append(e)
    return out

def rsi(c, n=14):
    out, g, l = [None] * len(c), 0.0, 0.0
    for i in range(1, len(c)):
        d = c[i] - c[i-1]
        up, dn = max(d, 0), max(-d, 0)
        if i <= n:
            g += up; l += dn
            if i == n:
                g /= n; l /= n
                out[i] = 100 - 100 / (1 + g / l) if l else 100
        else:
            g = (g * (n - 1) + up) / n; l = (l * (n - 1) + dn) / n
            out[i] = 100 - 100 / (1 + g / l) if l else 100
    return out

def analyze(d, rsi_lo=40, rsi_hi=50, idx=None):
    """d = [[날짜,시,고,저,종,거래량],...]. idx = 판정할 날(기본 마지막 날)."""
    o = [x[1] for x in d]; h = [x[2] for x in d]; l = [x[3] for x in d]; c = [x[4] for x in d]; v = [x[5] for x in d]
    i = len(d) - 1 if idx is None else idx
    if i < 130:
        return None
    m20, m60, m120 = sma(c, 20), sma(c, 60), sma(c, 120)
    r = rsi(c)
    macd = [a - b for a, b in zip(ema(c, 12), ema(c, 26))]
    sig = ema(macd, 9)
    hist = [a - b for a, b in zip(macd, sig)]
    v20 = sma(v, 20)
    # 1) 우상향
    trend = (m20[i] > m60[i] > m120[i]) and m60[i] > m60[i-10] and c[i] > m120[i]
    # 2) 눌림: 최근 60일 고점 대비 되돌림 0.236~0.618 또는 20/60일선 3% 안, 최근 5일 중 RSI 범위
    hi60 = max(h[i-59:i+1]); lo60 = min(l[i-59:i+1])
    retr = (hi60 - min(l[i-4:i+1])) / (hi60 - lo60) if hi60 > lo60 else 0
    near_ma = any(abs(min(l[i-4:i+1]) - m) / m <= 0.03 for m in (m20[i], m60[i]))
    rsi_dip = any(r[j] is not None and rsi_lo <= r[j] <= rsi_hi for j in range(i-4, i+1))
    pullback = (0.236 <= retr <= 0.618 or near_ma) and rsi_dip and c[i] < hi60 * 0.97
    # 3) 반등 신호 (오늘 기준, 2개 이상)
    sigs = []
    if c[i] > o[i] and v20[i] and v[i] > v20[i] * 1.2: sigs.append("거래량 실린 양봉")
    if c[i] > h[i-1]: sigs.append("전일 고가 돌파")
    if r[i] is not None and r[i-1] is not None and r[i] > r[i-1] and min(r[i-3:i]) <= rsi_hi: sigs.append("RSI 반등")
    if hist[i] > hist[i-1] and hist[i-1] <= hist[i-2]: sigs.append("MACD 히스토그램 상승 전환")
    bounce = len(sigs) >= 2
    stop = round(min(min(l[i-4:i+1]), m60[i]) * 0.98, 4)
    return {"date": d[i][0], "close": c[i], "trend": trend, "pullback": pullback, "bounce": bounce,
            "signals": sigs, "rsi": round(r[i], 1), "retrace": round(retr, 3),
            "ma20": round(m20[i], 4), "ma60": round(m60[i], 4), "ma120": round(m120[i], 4),
            "entry": c[i], "stop": stop, "target": round(hi60, 4),
            "rr": round((hi60 - c[i]) / (c[i] - stop), 2) if c[i] > stop else None}

def backtest(d, rsi_lo, rsi_hi, hold=15):
    """과거에 같은 신호가 났던 날마다: hold일 안에 목표(60일 고점)에 먼저 닿으면 승, 손절에 먼저 닿으면 패."""
    wins = losses = 0
    rets = []
    i = 130
    while i < len(d) - 1:
        a = analyze(d, rsi_lo, rsi_hi, i)
        if a and a["trend"] and a["pullback"] and a["bounce"]:
            res = None
            for j in range(i + 1, min(i + 1 + hold, len(d))):
                if d[j][3] <= a["stop"]: res = (a["stop"] / a["entry"] - 1); losses += 1; break
                if d[j][2] >= a["target"]: res = (a["target"] / a["entry"] - 1); wins += 1; break
            if res is None:
                j = min(i + hold, len(d) - 1); res = d[j][4] / a["entry"] - 1
                (wins := wins + 1) if res > 0 else (losses := losses + 1)
            rets.append(res); i += hold
        else:
            i += 1
    n = wins + losses
    return {"rsi_range": f"{rsi_lo}-{rsi_hi}", "trades": n, "win_rate": round(wins / n * 100, 1) if n else None,
            "avg_return_pct": round(sum(rets) / n * 100, 2) if n else None}

def scan(path, ranges=((35, 45), (40, 50), (45, 55))):
    data = json.load(open(path, encoding="utf-8"))
    out = []
    for code, b in data["bars"].items():
        if b.get("group") == "지수" or len(b["d"]) < 140:
            continue
        bts = [backtest(b["d"], lo, hi) for lo, hi in ranges]
        best = max(bts, key=lambda x: ((x["win_rate"] or 0) if x["trades"] >= 3 else -1, x["trades"]))
        lo, hi = map(int, best["rsi_range"].split("-")) if best["trades"] >= 3 else (40, 50)
        a = analyze(b["d"], lo, hi)
        if not a or not a["trend"]:
            continue
        tag = "🎯 진입 후보" if (a["pullback"] and a["bounce"]) else ("👀 관찰(반등 대기)" if a["pullback"] else None)
        if tag:
            out.append({"code": code, "name": b["name"], "group": b["group"], "tag": tag, **a,
                        "rsi_used": f"{lo}-{hi}", "backtest": best, "all_backtests": bts})
    out.sort(key=lambda x: (x["tag"] != "🎯 진입 후보", -(x["backtest"]["win_rate"] or 0)))
    return {"fetched_at_kst": data["fetched_at_kst"], "results": out, "errors": data.get("errors", {})}

if __name__ == "__main__":
    print(json.dumps(scan(sys.argv[1]), ensure_ascii=False, indent=1))
