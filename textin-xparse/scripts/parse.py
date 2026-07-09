#!/usr/bin/env python3
"""
TextIn xParse API Wrapper — 文档解析 / 抽取。

用法:
  python3 parse.py sync <file_path>        # 同步解析本地文件
  python3 parse.py sync <url>              # 同步解析 URL
  python3 parse.py async <file_path>       # 异步解析，轮询等待结果
  python3 parse.py async <url>
  python3 parse.py async <file_path> --no-wait  # 异步提交，仅返回 task_id
  python3 parse.py result <task_id>        # 查询异步任务结果
  python3 parse.py extract <file> --schema '{"properties":...}'   # 字段抽取
  python3 parse.py extract <file> --schema-file schema.json       # 从文件加载 schema
  python3 parse.py bill <file>               # 票据识别（20+种票据，零配置）
  python3 parse.py bill <file> --json        # + 完整 JSON
  python3 parse.py bill <file> --crop-images --crop-fields  # + 裁切图
  python3 parse.py download <image_url>    # 下载解析出的图片
"""

import json
import os
import sys
import time
import base64
import urllib.request
import urllib.error
import uuid
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = SKILL_DIR / "config.json"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def build_headers(config):
    return {
        "x-ti-app-id": config["app_id"],
        "x-ti-secret-code": config["secret_code"],
    }


def upload_file(file_path, endpoint, headers, extra_fields=None):
    """Upload a file to the API using multipart/form-data."""
    boundary = f"----FormBoundary{uuid.uuid4().hex[:16]}"
    
    # Read file
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    with open(file_path, "rb") as f:
        file_data = f.read()
    
    filename = file_path.name
    
    # Build multipart body
    body = b""
    
    # File part
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    body += b"Content-Type: application/octet-stream\r\n\r\n"
    body += file_data
    body += b"\r\n"
    
    # Extra fields
    if extra_fields:
        for key, value in extra_fields.items():
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
            body += str(value).encode()
            body += b"\r\n"
    
    body += f"--{boundary}--\r\n".encode()
    
    # Build request
    all_headers = {
        **headers,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    
    url = f"{config['api_base']}{endpoint}"
    req = urllib.request.Request(url, data=body, headers=all_headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        raise RuntimeError(f"API 错误 [{e.code}]: {error_body}")


def upload_url(document_url, endpoint, headers, extra_fields=None):
    """Submit a document URL to the API via multipart form."""
    boundary = f"----FormBoundary{uuid.uuid4().hex[:16]}"
    
    body = b""
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="file_url"\r\n\r\n'
    body += document_url.encode()
    body += b"\r\n"
    
    if extra_fields:
        for key, value in extra_fields.items():
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
            body += str(value).encode()
            body += b"\r\n"
    
    body += f"--{boundary}--\r\n".encode()
    
    all_headers = {
        **headers,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    
    url = f"{config['api_base']}{endpoint}"
    req = urllib.request.Request(url, data=body, headers=all_headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        raise RuntimeError(f"API 错误 [{e.code}]: {error_body}")


def is_url(path):
    return path.startswith(("http://", "https://"))


def json_request(endpoint, payload, headers):
    """Send a JSON POST request and return the parsed response."""
    url = f"{config['api_base']}{endpoint}"
    body = json.dumps(payload).encode("utf-8")
    req_headers = {
        **headers,
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        raise RuntimeError(f"API 错误 [{e.code}]: {error_body}")


def file_to_base64(file_path):
    """Read a local file and return its base64-encoded string."""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def submit_job(file_path, endpoint, headers):
    """Submit a file or URL for parsing. Returns API response."""
    extra_fields = {
        "engine": "textin",  # 默认引擎
    }
    
    if is_url(file_path):
        return upload_url(file_path, endpoint, headers, extra_fields)
    else:
        return upload_file(file_path, endpoint, headers, extra_fields)


def poll_task(task_id, config, headers):
    """Poll for async task completion. Returns the final parse result."""
    poll_url = f"{config['api_base']}{config['async_endpoint']}/{task_id}"
    
    for attempt in range(config["max_poll_attempts"]):
        req = urllib.request.Request(poll_url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            raise RuntimeError(f"轮询错误 [{e.code}]: {error_body}")
        
        data = result.get("data", result)
        status = data.get("status", "")
        
        if status == "completed":
            # Fetch the actual parse result
            result_url = data.get("result_url", "")
            if result_url:
                req2 = urllib.request.Request(result_url, headers=headers, method="GET")
                with urllib.request.urlopen(req2, timeout=30) as resp2:
                    return json.loads(resp2.read().decode())
            return result
        elif status == "failed":
            raise RuntimeError(f"任务失败: {json.dumps(result, ensure_ascii=False)}")
        
        if attempt % 10 == 0 and attempt > 0:
            print(f"  [轮询 {attempt}/{config['max_poll_attempts']}] 状态: {status}", file=sys.stderr)
        
        time.sleep(config["poll_interval_seconds"])
    
    raise TimeoutError(f"任务超时，已轮询 {config['max_poll_attempts']} 次")


def get_task_result(task_id, config, headers):
    """Get result of an async task."""
    poll_url = f"{config['api_base']}{config['async_endpoint']}/{task_id}"
    req = urllib.request.Request(poll_url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        status_resp = json.loads(resp.read().decode())
    
    data = status_resp.get("data", status_resp)
    status = data.get("status", "")
    
    if status == "completed":
        result_url = data.get("result_url", "")
        if result_url:
            req2 = urllib.request.Request(result_url, headers=headers, method="GET")
            with urllib.request.urlopen(req2, timeout=30) as resp2:
                return json.loads(resp2.read().decode())
    
    return status_resp


def extract_document(file_path, schema, parse_options=None, extract_options=None):
    """Extract fields from a document using JSON Schema."""
    payload = {
        "schema": schema,
    }
    
    # Build file object
    file_obj = {"file_name": Path(file_path).name if not is_url(file_path) else file_path.split("/")[-1].split("?")[0]}
    if is_url(file_path):
        file_obj["file_url"] = file_path
    else:
        file_obj["file_base64"] = file_to_base64(file_path)
    payload["file"] = file_obj
    
    if parse_options:
        payload["parse_options"] = parse_options
    if extract_options:
        payload["extract_options"] = extract_options
    
    return json_request(config["extract_endpoint"], payload, headers)


def recognize_bill(file_path, **query_params):
    """Recognize bill/invoice types and extract fields. Zero-config for 20+ bill types."""
    if is_url(file_path):
        # URL mode: text/plain body
        body = file_path.encode("utf-8")
        content_type = "text/plain"
    else:
        # Local file: raw binary
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        with open(file_path, "rb") as f:
            body = f.read()
        content_type = "application/octet-stream"
    
    # Build URL with query params
    url = f"{config['api_base']}{config['bill_endpoint']}"
    if query_params:
        from urllib.parse import urlencode
        url += "?" + urlencode(query_params)
    
    req_headers = {
        **headers,
        "Content-Type": content_type,
    }
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        raise RuntimeError(f"API 错误 [{e.code}]: {error_body}")


def download_image(image_url, output_dir="/tmp"):
    """Download an image from the API."""
    headers = {
        "User-Agent": "textin-xparse-skill/1.0"
    }
    req = urllib.request.Request(image_url, headers=headers)
    
    filename = image_url.split("/")[-1].split("?")[0] or "image.png"
    output_path = Path(output_dir) / filename
    
    with urllib.request.urlopen(req, timeout=60) as resp:
        with open(output_path, "wb") as f:
            f.write(resp.read())
    
    return str(output_path)


def print_result(result):
    """Pretty-print the parse result."""
    print(json.dumps(result, ensure_ascii=False, indent=2))


def print_summary(result):
    """Print a human-readable summary of the result."""
    import shutil
    term_width = shutil.get_terminal_size((120, 40)).columns
    
    # Handle API error
    code = result.get("code", 0)
    if code != 200 and code != 0:
        msg = result.get("message", "未知错误")
        print(f"{'='*term_width}")
        print(f"  API 错误 [{code}]: {msg}")
        print(f"{'='*term_width}")
        return
    
    # Get data from response (may be nested under 'data', 'result', or at top level)
    data = result.get("data", result.get("result", result))
    
    markdown = data.get("markdown", "")
    elements = data.get("elements", [])
    pages = data.get("pages", []) or data.get("page_count", 0)
    
    print(f"{'='*term_width}")
    print(f"  解析成功")
    
    # Markdown
    if markdown:
        print(f"{'='*term_width}")
        print(f"  Markdown ({len(markdown)} 字符):")
        print(f"{'-'*term_width}")
        preview = markdown[:3000]
        print(preview)
        if len(markdown) > 3000:
            print(f"\n  ... (共 {len(markdown)} 字符，已截断)")
    
    # Elements summary
    if elements:
        print(f"\n{'='*term_width}")
        print(f"  Elements: {len(elements)} 个")
        type_counts = {}
        for el in elements:
            t = el.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        for t, count in sorted(type_counts.items()):
            print(f"    - {t}: {count}")
    
    # Pages
    if isinstance(pages, list):
        print(f"\n  页数: {len(pages)}")
    elif pages:
        print(f"\n  页数: {pages}")
    
    print(f"{'='*term_width}")


def print_extract_result(result):
    """Pretty-print the extraction result."""
    import shutil
    term_width = shutil.get_terminal_size((120, 40)).columns
    
    code = result.get("code", 0)
    if code != 200 and code != 0:
        msg = result.get("message", "未知错误")
        print(f"{'='*term_width}")
        print(f"  API 错误 [{code}]: {msg}")
        print(f"{'='*term_width}")
        return
    
    data = result.get("data", result)
    extract_data = data.get("result", {})
    
    # The actual extracted values are in extracted_schema
    extracted_schema = extract_data.get("extracted_schema", {})
    citations = extract_data.get("citations", {})
    
    print(f"{'='*term_width}")
    print(f"  抽取成功")
    print(f"{'='*term_width}")
    
    if extracted_schema:
        print(f"  抽取字段 ({len(extracted_schema)} 个):")
        print(f"{'-'*term_width}")
        for key, value in extracted_schema.items():
            confidence = ""
            if key in citations:
                cc = citations[key]
                if isinstance(cc, dict):
                    level = cc.get("llm_confidence_level", "")
                    if level:
                        confidence = f"  [置信度: {level}]"
            if isinstance(value, list):
                preview = f"列表 ({len(value)} 项): {json.dumps(value[:3], ensure_ascii=False)}"
                if len(value) > 3:
                    preview += f" ... 共 {len(value)} 项"
            elif isinstance(value, dict):
                preview = f"对象: {json.dumps(value, ensure_ascii=False)}"
            elif value is None:
                preview = "(未提取到)"
            else:
                preview = str(value)
            print(f"    {key}: {preview}{confidence}")
    
    # Show stamps if any
    stamps = extract_data.get("stamps", [])
    if stamps:
        print(f"\n  印章: {len(stamps)} 个")
    
    # Show token usage
    usage = extract_data.get("usage", {})
    if usage:
        total = usage.get("acgpt_total_tokens", 0)
        if total:
            print(f"\n  Token 消耗: {total}")
    
    print(f"{'='*term_width}")


def print_bill_result(result):
    """Pretty-print the bill recognition result."""
    import shutil
    term_width = shutil.get_terminal_size((120, 40)).columns
    
    code = result.get("code", 0)
    if code != 200 and code != 0:
        msg = result.get("message", "未知错误")
        print(f"{'='*term_width}")
        print(f"  API 错误 [{code}]: {msg}")
        print(f"{'='*term_width}")
        return
    
    pages = result.get("pages", [])
    
    for pi, page in enumerate(pages):
        page_num = page.get("page_number", pi)
        page_result = page.get("result", {})
        
        if isinstance(page_result, list):
            bills = page_result
        elif isinstance(page_result, dict):
            bills = [page_result]
        else:
            bills = []
        
        print(f"{'='*term_width}")
        if page.get("pageNum", 1) > 1:
            print(f"  第 {page_num + 1} 页 — {len(bills)} 张票据")
        else:
            print(f"  识别到 {len(bills)} 张票据")
        print(f"{'='*term_width}")
        
        for bi, bill in enumerate(bills):
            if isinstance(bill, str):
                print(f"\n  [{bi+1}] {bill}")
                continue
            
            bill_type = bill.get("type_description", bill.get("type", "未知"))
            kind = bill.get("kind_description", "")
            kind_str = f" ({kind})" if kind else ""
            print(f"\n  [{bi+1}] {bill_type}{kind_str}")
            print(f"  {'-'*min(term_width-4, 60)}")
            
            item_list = bill.get("item_list", [])
            has_values = any(item.get("value", "") for item in item_list)
            for item in item_list:
                key = item.get("key", "")
                value = item.get("value", "")
                desc = item.get("description", "")
                if has_values and not value:
                    continue  # skip empty when others have values
                label = desc if desc else key
                print(f"    {label}: {value if value else '(无)'}")
            
            # Product list
            product_list = bill.get("product_list", [])
            if product_list:
                print(f"\n    明细 ({len(product_list)} 项):")
                # Show first 5 items
                for prod in product_list[:5]:
                    if isinstance(prod, dict):
                        items = prod.get("item_list", prod.get("items", []))
                        parts = []
                        for it in items:
                            v = it.get("value", "")
                            if v:
                                parts.append(v)
                        print(f"      - {' | '.join(parts)}")
                if len(product_list) > 5:
                    print(f"      ... 共 {len(product_list)} 项")
    
    print(f"{'='*term_width}")


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    config = load_config()
    headers = build_headers(config)
    command = sys.argv[1]
    
    try:
        if command == "sync":
            if len(sys.argv) < 3:
                print("用法: python3 parse.py sync <file_path|url>")
                sys.exit(1)
            file_path = sys.argv[2]
            print(f"→ 同步解析: {file_path}", file=sys.stderr)
            result = submit_job(file_path, config["sync_endpoint"], headers)
            print_summary(result)
            # Also output full JSON for piping
            if "--json" in sys.argv:
                print_result(result)
        
        elif command == "async":
            if len(sys.argv) < 3:
                print("用法: python3 parse.py async <file_path|url> [--no-wait]")
                sys.exit(1)
            file_path = sys.argv[2]
            no_wait = "--no-wait" in sys.argv
            
            print(f"→ 异步提交: {file_path}", file=sys.stderr)
            result = submit_job(file_path, config["async_endpoint"], headers)
            
            task_id = result.get("task_id", "") or result.get("data", {}).get("job_id", "") or result.get("job_id", "")
            
            if task_id:
                print(f"  task_id: {task_id}", file=sys.stderr)
                
                if no_wait:
                    print(json.dumps({"task_id": task_id}, ensure_ascii=False))
                else:
                    print(f"  → 轮询等待完成...", file=sys.stderr)
                    final = poll_task(task_id, config, headers)
                    print_summary(final)
                    if "--json" in sys.argv:
                        print_result(final)
            else:
                print("⚠️ 未获取到 task_id，原始响应:", file=sys.stderr)
                print_result(result)
        
        elif command == "result":
            if len(sys.argv) < 3:
                print("用法: python3 parse.py result <task_id>")
                sys.exit(1)
            task_id = sys.argv[2]
            result = get_task_result(task_id, config, headers)
            print_summary(result)
            if "--json" in sys.argv:
                print_result(result)
        
        elif command == "extract":
            if len(sys.argv) < 3:
                print("用法: python3 parse.py extract <file> --schema '...' | --schema-file schema.json")
                print("      可选: --page-start N --page-count N --json")
                sys.exit(1)
            file_path = sys.argv[2]
            
            # Parse schema
            schema = None
            if "--schema" in sys.argv:
                idx = sys.argv.index("--schema")
                if idx + 1 < len(sys.argv):
                    schema = json.loads(sys.argv[idx + 1])
            elif "--schema-file" in sys.argv:
                idx = sys.argv.index("--schema-file")
                if idx + 1 < len(sys.argv):
                    with open(sys.argv[idx + 1]) as f:
                        schema = json.load(f)
            
            if schema is None:
                print("错误: 必须指定 --schema 或 --schema-file", file=sys.stderr)
                sys.exit(1)
            
            # Parse options
            parse_opts = {}
            if "--page-start" in sys.argv:
                idx = sys.argv.index("--page-start")
                parse_opts["page_start"] = int(sys.argv[idx + 1])
            if "--page-count" in sys.argv:
                idx = sys.argv.index("--page-count")
                parse_opts["page_count"] = int(sys.argv[idx + 1])
            
            print(f"→ 字段抽取: {file_path}", file=sys.stderr)
            result = extract_document(file_path, schema, 
                                     parse_options=parse_opts if parse_opts else None)
            print_extract_result(result)
            if "--json" in sys.argv:
                print_result(result)
        
        elif command == "bill":
            if len(sys.argv) < 3:
                print("用法: python3 parse.py bill <file|url> [选项]")
                print("      选项: --crop-images    返回票据裁切图片")
                print("            --crop-fields    返回字段切图")
                print("            --merge-digital  合并多页数电票")
                print("            --pages 1,3-5    指定页码")
                print("            --json           输出完整 JSON")
                sys.exit(1)
            file_path = sys.argv[2]
            
            # Parse options
            query_params = {}
            if "--crop-images" in sys.argv:
                query_params["crop_complete_image"] = 1
            if "--crop-fields" in sys.argv:
                query_params["crop_value_image"] = 1
            if "--merge-digital" in sys.argv:
                query_params["merge_digital_elec_invoice"] = 1
            if "--pages" in sys.argv:
                idx = sys.argv.index("--pages")
                if idx + 1 < len(sys.argv):
                    query_params["specific_pages"] = sys.argv[idx + 1]
            
            print(f"→ 票据识别: {file_path}", file=sys.stderr)
            result = recognize_bill(file_path, **query_params)
            print_bill_result(result)
            if "--json" in sys.argv:
                print_result(result)
        
        elif command == "download":
            if len(sys.argv) < 3:
                print("用法: python3 parse.py download <image_url> [output_dir]")
                sys.exit(1)
            image_url = sys.argv[2]
            output_dir = sys.argv[3] if len(sys.argv) > 3 else "/tmp"
            path = download_image(image_url, output_dir)
            print(f"已下载: {path}")
        
        else:
            print(f"未知命令: {command}")
            print(__doc__)
            sys.exit(1)
    
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
