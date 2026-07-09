#!/usr/bin/env python3
"""
prepare_factor_quality.py — Step 0 机械化产出：因子质量文件

输入：股票代码
输出：factor_quality.json（bucket / in_index / 权重 / 因子方案）

纯机械判定——不依赖 LLM 推理。
"""
import argparse, json, os, sys

FACTOR_DIR = "/home/admin/agent-skills/factor-quality/data"
PANEL_DIR = os.path.join(FACTOR_DIR, "panels")

# ── 权重矩阵 ──
WEIGHT_MATRIX = {
    ("大盘(A500)", True):   (65, 35),
    ("大盘(A500)", False):  (55, 45),
    ("科技", True):         (55, 45),
    ("科技", False):        (40, 60),
    ("中小盘(中证500)", True):  (40, 60),
    ("中小盘(中证500)", False): (25, 75),
}

# ── 桶判定 ──
def classify_bucket(symbol: str, market_cap: float) -> str:
    """机械判定：代码前缀 + 市值阈值 → 桶名。"""
    if symbol.startswith(("688", "300", "301")):
        return "科技"
    if market_cap > 300e8:  # >300亿
        return "大盘(A500)"
    return "中小盘(中证500)"

# 桶名 → 面板桶名映射
BUCKET_TO_PANEL = {
    "科技":          "科技桶",
    "大盘(A500)":     "中证A500",
    "中小盘(中证500)": "中证500",
}

# ── 指数成分判定 ──
INDEX_MAP = {
    "科技":         ["000688", "399673"],   # 科创50 + 创业板50
    "大盘(A500)":    ["000510"],            # 中证A500
    "中小盘(中证500)": ["000905"],            # 中证500
}

def check_in_index(symbol: str, bucket: str) -> bool:
    """查该股是否在对应指数成分内。"""
    indices = INDEX_MAP.get(bucket, [])
    if not indices:
        return False
    try:
        import akshare as ak
        for idx_code in indices:
            df = ak.index_stock_cons(idx_code)
            if df is not None and not df.empty:
                codes = set(str(c).zfill(6) for c in df["品种代码"].astype(str))
                if symbol in codes:
                    return True
    except Exception:
        pass  # API 不可用 → 返回 False
    return False

# ── 总市值获取 ──
def get_market_cap(symbol: str) -> float:
    """从 TX 实时行情获取总市值。"""
    try:
        from a_share_market_middleware.stock.realtime import get_realtime_quote_batch
        r = get_realtime_quote_batch([symbol])
        if r.get("success"):
            q = r["data"].get(symbol, {})
            cap = q.get("总市值")
            if cap:
                return float(cap)
    except Exception:
        pass
    return 0.0

# ── 主流程 ──
def prepare(symbol: str) -> dict:
    # 1. 读个股因子
    stock_path = os.path.join(FACTOR_DIR, "stocks", f"{symbol}.json")
    if not os.path.exists(stock_path):
        return {"error": f"个股因子文件不存在: {stock_path}"}
    with open(stock_path) as f:
        stock_fq = json.load(f)

    # 2. 获取总市值
    market_cap = get_market_cap(symbol)

    # 3. 判定桶
    bucket = classify_bucket(symbol, market_cap)

    # 4. 查指数成分
    in_index = check_in_index(symbol, bucket)

    # 5. 读面板因子
    meta_path = os.path.join(PANEL_DIR, "_meta.json")
    if not os.path.exists(meta_path):
        return {"error": f"面板元数据不存在: {meta_path}"}
    with open(meta_path) as f:
        panel_meta = json.load(f)
    panel_file = panel_meta.get("latest", {}).get(BUCKET_TO_PANEL.get(bucket, bucket))
    if not panel_file:
        return {"error": f"面板桶 '{bucket}' 无数据"}
    panel_path = os.path.join(PANEL_DIR, panel_file)
    if not os.path.exists(panel_path):
        return {"error": f"面板文件不存在: {panel_path}"}
    with open(panel_path) as f:
        panel_fq = json.load(f)

    # 6. 取方案
    stock_es = stock_fq.get("effective_sets", {})
    panel_es = panel_fq.get("effective_sets", {})

    # 优先高区分，其次去冗余，最次稳定优先
    scheme_order = ["高区分", "去冗余", "稳定优先"]
    scheme_used = None
    for s in scheme_order:
        if s in stock_es or s in panel_es:
            scheme_used = s
            break

    priority_factors = stock_es.get(scheme_used, {}).get("factors", []) if scheme_used else []
    high_confidence_factors = stock_es.get("高区分", {}).get("factors", [])
    panel_factors = panel_es.get(scheme_used, {}).get("factors", []) if scheme_used else []

    # 7. 权重
    index_weight, stock_weight = WEIGHT_MATRIX.get((bucket, in_index), (50, 50))

    return {
        "symbol": symbol,
        "bucket": bucket,
        "in_index": in_index,
        "index_weight": index_weight,
        "stock_weight": stock_weight,
        "priority_factors": priority_factors,
        "high_confidence_factors": high_confidence_factors,
        "panel_factors": panel_factors,
        "scheme_used": scheme_used or "去冗余",
        "market_cap": market_cap,
        "generated_at": stock_fq.get("meta", {}).get("generated_at", ""),
    }


def main():
    parser = argparse.ArgumentParser(description="因子质量机械化产出")
    parser.add_argument("symbol", help="6位股票代码")
    parser.add_argument("--outdir", default=".", help="输出目录")
    args = parser.parse_args()

    result = prepare(args.symbol)
    if "error" in result:
        print(f"✗ {result['error']}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)
    out_path = os.path.join(args.outdir, "factor_quality.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✓ factor_quality.json → {out_path}")
    print(f"  bucket={result['bucket']} in_index={result['in_index']} "
          f"idx_w={result['index_weight']}% stock_w={result['stock_weight']}%")
    print(f"  scheme={result['scheme_used']} "
          f"priority={result['priority_factors']} "
          f"panel={result['panel_factors']}")


if __name__ == "__main__":
    main()
