#!/usr/bin/env python3
"""D7: ST 处罚记录采集 → penalties.json

调用 st_penalties.py 脚本（新浪爬虫），输出处罚记录。
用法: python3 collect_penalties.py --symbol 688386 --output /tmp/688386_20250622/data/penalties.json
"""

import argparse, json, subprocess, sys, os
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="D7 处罚记录采集")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    st_penalties = os.path.join(script_dir, "st_penalties.py")

    if not os.path.exists(st_penalties):
        output = {
            "success": False,
            "error": f"st_penalties.py 不存在: {st_penalties}",
            "data": [],
        }
    else:
        try:
            result = subprocess.run(
                ["python3", st_penalties, "--ts-code", args.symbol],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                output = {"success": True, "data": data}
            else:
                output = {
                    "success": False,
                    "error": result.stderr[:500] if result.stderr else f"exit code {result.returncode}",
                    "data": [],
                }
        except subprocess.TimeoutExpired:
            output = {"success": False, "error": "st_penalties.py 超时 (120s)", "data": []}
        except json.JSONDecodeError:
            output = {
                "success": False,
                "error": "st_penalties.py 输出非 JSON",
                "data": [],
                "raw": result.stdout[:1000] if 'result' in dir() else "",
            }
        except Exception as e:
            output = {"success": False, "error": str(e), "data": []}

    output["symbol"] = args.symbol
    output["collected_at"] = datetime.now().isoformat()

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    status = "OK" if output.get("success") else f"FAILED: {output.get('error','')[:80]}"
    print(f"penalties.json → {args.output} ({status})")


if __name__ == "__main__":
    main()
