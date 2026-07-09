#!/usr/bin/env python3
"""
full_parse.py — 调 parse.py 内部函数，直接取全文 Markdown（不经过 print_summary 截断）

用法:
  python3 full_parse.py <file.pdf> > output.md
"""
import sys
import json
import importlib.util
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PARSE_PY = Path("/home/admin/agent-skills/textin-xparse/scripts/parse.py")
spec = importlib.util.spec_from_file_location("parse", str(PARSE_PY))
parse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parse)

file_path = sys.argv[1]
config = parse.load_config()
headers = parse.build_headers(config)
# parse.py 内部函数引用全局 config 变量，需注入
parse.config = config
result = parse.submit_job(file_path, config["sync_endpoint"], headers)

code = result.get("code", 0)
if code != 200:
    msg = result.get("message", "未知错误")
    print(f"解析失败 [{code}]: {msg}", file=sys.stderr)
    sys.exit(1)

md = result.get("data", result).get("markdown", "")
if not md:
    print("错误: 返回的 markdown 为空", file=sys.stderr)
    sys.exit(1)

print(md)
