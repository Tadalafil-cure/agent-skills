#!/usr/bin/env python3
"""
merge_fields.py — 合并多份文档的 extract JSON 为 materials_fields.json

输入: doc1_fields.json doc2_fields.json ... (来自 textin-xparse extract 的输出)
输出: stdout — 合并后的 JSON（含 source 清单 + predictions 数组）

用法:
  python3 merge_fields.py doc1_fields.json doc2_fields.json > materials_fields.json
  或
  cat doc*_fields.json | python3 merge_fields.py --stdin

输出格式:
{
  "source": "用户提供材料",
  "generated_at": "2025-06-22T18:00:00",
  "documents": [
    {"file": "研报A.pdf", "parsed_at": "...", "fields_count": 5},
    ...
  ],
  "predictions": [
    {"研报来源": "招商证券", "预测年度": "2025E", "净利预测": 850, ...},
    ...
  ]
}
"""

import json
import sys
from datetime import datetime, timezone


def extract_predictions_from_doc(data, source_name):
    """从单份 extract 结果中提取有效字段。支持新旧两种 schema 格式。"""
    # extract API 返回格式: {code, data: {result: {extracted_schema: {...}, citations: {...}}}}
    result = data.get("data", data).get("result", {})
    extracted = result.get("extracted_schema", {})
    
    if isinstance(extracted, dict) and extracted:
        # 新 schema: predictions 在 预测 数组里
        predictions_array = extracted.get("预测")
        if isinstance(predictions_array, list) and len(predictions_array) > 0:
            # 为每个预测条目附加研报元数据
            report_meta = {
                "研报来源": extracted.get("研报来源", source_name),
                "覆盖日期": extracted.get("覆盖日期"),
                "评级": extracted.get("评级"),
                "目标价": extracted.get("目标价"),
                "核心假设": extracted.get("核心假设"),
                "风险提示": extracted.get("风险提示"),
            }
            result_preds = []
            for pred in predictions_array:
                if isinstance(pred, dict):
                    merged = {**report_meta, **pred}
                    has_value = any(
                        v is not None and k != "研报来源"
                        for k, v in merged.items()
                    )
                    if has_value:
                        result_preds.append(merged)
            if result_preds:
                return result_preds
        
        # 旧 schema（兼容）: 字段是扁平的
        has_value = any(v is not None for v in extracted.values())
        if has_value:
            extracted["研报来源"] = extracted.get("研报来源", source_name)
            return extracted
    
    # 如果顶层直接就是 predictions 数组
    if isinstance(data, dict) and "predictions" in data:
        return data["predictions"]
    
    # 如果是旧格式直接返回值
    if isinstance(extracted, list):
        return extracted
    
    return None


def main():
    files = sys.argv[1:]
    stdin_mode = "--stdin" in files
    if stdin_mode:
        files.remove("--stdin")
    
    predictions = []
    documents = []
    
    # 读取文件
    if stdin_mode:
        # 从 stdin 读取 JSON 数组 [{...}, {...}]
        raw = sys.stdin.read()
        try:
            docs = json.loads(raw)
            if not isinstance(docs, list):
                docs = [docs]
        except json.JSONDecodeError:
            print("错误: stdin 不是有效 JSON", file=sys.stderr)
            sys.exit(1)
        
        for i, doc in enumerate(docs):
            source_name = f"文档{i+1}"
            preds = extract_predictions_from_doc(doc, source_name)
            if isinstance(preds, list):
                predictions.extend(preds)
            elif isinstance(preds, dict):
                predictions.append(preds)
            documents.append({
                "index": i + 1,
                "fields_count": len(preds) if isinstance(preds, list) else (1 if preds else 0)
            })
    else:
        if not files:
            print("用法: python3 merge_fields.py doc1_fields.json ... > materials_fields.json", file=sys.stderr)
            sys.exit(1)
        
        for i, fp in enumerate(files):
            try:
                with open(fp) as f:
                    doc = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"警告: 跳过 {fp}: {e}", file=sys.stderr)
                documents.append({"file": fp, "error": str(e), "fields_count": 0})
                continue
            
            preds = extract_predictions_from_doc(doc, fp)
            if isinstance(preds, list):
                predictions.extend(preds)
            elif isinstance(preds, dict):
                predictions.append(preds)
            
            documents.append({
                "file": fp,
                "fields_count": len(preds) if isinstance(preds, list) else (1 if preds else 0)
            })
    
    output = {
        "source": "用户提供材料",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "documents": documents,
        "predictions": predictions,
        "total_predictions": sum(
            len(p) if isinstance(p, list) else 1
            for p in [predictions]
            if p
        ) if predictions else 0
    }
    
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
