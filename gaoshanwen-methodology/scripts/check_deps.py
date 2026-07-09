"""gaoshanwen-methodology 依赖检查"""
import sys
import subprocess

MISSING = []

# 检查 akshare
try:
    import akshare
    print(f"✅ akshare {akshare.__version__}")
except ImportError:
    MISSING.append("akshare")

# 检查 playwright
try:
    import playwright
    ver = getattr(playwright, '__version__', None) or getattr(playwright, 'version', 'installed')
    print(f"✅ playwright ({ver})")
except ImportError:
    MISSING.append("playwright")

# 检查 pandas
try:
    import pandas
    print(f"✅ pandas {pandas.__version__}")
except ImportError:
    MISSING.append("pandas")

if MISSING:
    print(f"\n❌ 缺少依赖: {', '.join(MISSING)}")
    print("正在安装...")
    for pkg in MISSING:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
    print("安装完成。")

# playwright 需要额外安装浏览器
try:
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    try:
        b = p.chromium.launch(headless=True)
        b.close()
        print("✅ playwright chromium 已就绪")
    except Exception:
        print("⚠️ playwright chromium 未安装，正在安装...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("✅ playwright chromium 安装完成")
    p.stop()
except Exception as e:
    print(f"⚠️ playwright 浏览器检查失败: {e}")
