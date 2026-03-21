#!/usr/bin/env python3
"""
TransVar API Service
提供 HGVS 变异注释的 RESTful API 服务

版本 1.4.0 - 使用 transvar 官方数据库
"""

import os
import subprocess
import json
import re
import logging
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import uvicorn

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TransVar API",
    description="HGVS 变异注释工具 TransVar 的 RESTful API 服务",
    version="1.4.0"
)

# 启用 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnnotationRequest(BaseModel):
    """变异注释请求模型"""
    variant: str = Field(..., description="变异描述，如 PIK3CA:p.E545K 或 NM_006218.4:c.1633G>A")
    refversion: str = Field(default="hg38", description="参考基因组版本: hg38 或 hg19")
    mode: str = Field(default="panno", description="注释模式: panno(蛋白), canno(cDNA), ganno(DNA), codonsearch(密码子)")


class AnnotationResponse(BaseModel):
    """变异注释响应模型"""
    success: bool
    input: str
    refversion: str
    mode: str
    result: Optional[str] = None
    error: Optional[str] = None
    warning: Optional[str] = None
    raw_output: Optional[str] = None


class BatchAnnotationRequest(BaseModel):
    """批量注释请求模型"""
    variants: List[str] = Field(..., description="变异列表")
    refversion: str = Field(default="hg38", description="参考基因组版本")
    mode: str = Field(default="panno", description="注释模式")


def run_transvar(variant: str, mode: str, refversion: str) -> Dict[str, Any]:
    """
    执行 TransVar 命令

    Args:
        variant: 变异描述
        mode: 注释模式 (panno/canno/ganno/codonsearch)
        refversion: 参考基因组版本 (hg38 或 hg19)

    Returns:
        包含执行结果的字典
    """
    logger.info(f"开始处理: variant={variant}, mode={mode}, refversion={refversion}")

    # 验证模式
    valid_modes = ["panno", "canno", "ganno", "codonsearch"]
    if mode not in valid_modes:
        logger.error(f"无效的模式: {mode}")
        return {
            "success": False,
            "error": f"无效的模式: {mode}，支持的模式: {', '.join(valid_modes)}"
        }

    # 验证版本
    valid_versions = ["hg38", "hg19"]
    if refversion not in valid_versions:
        logger.error(f"无效的版本: {refversion}")
        return {
            "success": False,
            "error": f"无效的版本: {refversion}，支持的版本: {', '.join(valid_versions)}"
        }

    # 构建 TransVar 命令
    cmd = [
        "transvar", mode,
        "-i", variant,
        "--refversion", refversion,
        "-o", "/dev/stdout"
    ]

    logger.info(f"执行命令: {' '.join(cmd)}")

    try:
        env = {
            **os.environ,
            "HOME": os.path.expanduser("~")
        }
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            cwd="/app"
        )

        output = result.stdout
        error = result.stderr
        logger.info(f"命令返回码: {result.returncode}")
        logger.info(f"标准输出长度: {len(output)} 字符")
        if error:
            logger.warning(f"标准错误: {error[:500]}")

        # 检查输出行数，判断是否只有表头
        output_lines = output.strip().split('\n') if output.strip() else []
        has_data = len(output_lines) > 1

        if result.returncode == 0 and output.strip():
            if not has_data:
                logger.warning(f"输出只有表头，没有数据行")
                return {
                    "success": True,
                    "result": output.strip(),
                    "raw_output": output,
                    "warning": "输出只有表头，未找到匹配的数据。"
                }
            logger.info(f"执行成功，输出 {len(output_lines)} 行")
            return {
                "success": True,
                "result": output.strip(),
                "raw_output": output
            }
        else:
            if output.strip():
                logger.warning(f"返回码非零但有输出: returncode={result.returncode}")
                return {
                    "success": True,
                    "result": output.strip(),
                    "raw_output": output,
                    "warning": f"返回码: {result.returncode}"
                }

            logger.error(f"执行失败: returncode={result.returncode}")
            return {
                "success": False,
                "error": error.strip() if error else "未找到注释结果",
                "raw_output": output
            }

    except subprocess.TimeoutExpired:
        logger.error(f"执行超时: variant={variant}")
        return {
            "success": False,
            "error": "执行超时（120秒），请稍后重试"
        }
    except Exception as e:
        logger.exception(f"执行异常: {str(e)}")
        return {
            "success": False,
            "error": f"执行错误: {str(e)}"
        }


@app.get("/", response_class=HTMLResponse)
async def home():
    """返回 Web 界面"""
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TransVar HGVS 注释工具</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 900px; margin: 0 auto; }
        .header { text-align: center; color: white; margin-bottom: 30px; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { font-size: 1.1em; opacity: 0.9; }
        .card {
            background: white;
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            margin-bottom: 20px;
        }
        .form-group { margin-bottom: 20px; }
        label { display: block; font-weight: 600; margin-bottom: 8px; color: #333; }
        input[type="text"], select, textarea {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input:focus, select:focus, textarea:focus { outline: none; border-color: #667eea; }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 14px 32px;
            font-size: 16px;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4); }
        .result { margin-top: 20px; padding: 20px; border-radius: 8px; display: none; }
        .result.success { background: #d4edda; border: 1px solid #c3e6cb; display: block; }
        .result.error { background: #f8d7da; border: 1px solid #f5c6cb; display: block; }
        .result.warning { background: #fff3cd; border: 1px solid #ffeeba; display: block; }
        .result-title { font-weight: 600; margin-bottom: 10px; font-size: 1.1em; }
        .result-content {
            font-family: 'Courier New', monospace;
            white-space: pre-wrap;
            word-break: break-all;
            background: white;
            padding: 15px;
            border-radius: 6px;
            max-height: 500px;
            overflow-y: auto;
        }
        .examples { margin-top: 20px; }
        .examples h3 { color: #333; margin-bottom: 15px; }
        .example-item {
            display: inline-block;
            background: #f0f0f0;
            padding: 8px 16px;
            border-radius: 20px;
            margin: 5px;
            cursor: pointer;
            transition: background 0.2s;
            font-size: 14px;
        }
        .example-item:hover { background: #e0e0e0; }
        .tabs { display: flex; border-bottom: 2px solid #e0e0e0; margin-bottom: 20px; }
        .tab {
            padding: 12px 24px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            margin-bottom: -2px;
            transition: all 0.2s;
        }
        .tab.active { border-bottom-color: #667eea; color: #667eea; font-weight: 600; }
        .batch-input { width: 100%; min-height: 150px; font-family: 'Courier New', monospace; }
        .loading { text-align: center; padding: 20px; }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .info-box { background: #e7f3ff; border-left: 4px solid #2196F3; padding: 15px; margin-bottom: 20px; border-radius: 4px; }
        .info-box h4 { color: #1976D2; margin-bottom: 8px; }
        .info-box p { color: #555; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>TransVar HGVS 注释工具</h1>
            <p>使用 TransVar 官方数据库进行变异注释</p>
        </div>
        <div class="card">
            <div class="info-box">
                <h4>简介</h4>
                <p>TransVar 是一个强大的 HGVS 变异注释工具，支持蛋白 (p.)、cDNA (c.) 和基因组 (g.) 水平的变异注释。</p>
            </div>
            <div class="tabs">
                <div class="tab active" onclick="switchTab('single')">单个注释</div>
                <div class="tab" onclick="switchTab('batch')">批量注释</div>
                <div class="tab" onclick="switchTab('debug')">调试</div>
            </div>
            <div id="single-form">
                <div class="form-group">
                    <label for="variant">变异描述 (HGVS)</label>
                    <input type="text" id="variant" placeholder="例如: PIK3CA:p.E545K">
                </div>
                <div class="form-group">
                    <label for="refversion">参考基因组版本</label>
                    <select id="refversion">
                        <option value="hg38">hg38 (GRCh38) - 推荐</option>
                        <option value="hg19">hg19 (GRCh37)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="mode">注释模式</label>
                    <select id="mode">
                        <option value="panno">蛋白注释 (p.)</option>
                        <option value="canno">cDNA注释 (c.)</option>
                        <option value="ganno">基因组注释 (g.)</option>
                    </select>
                </div>
                <button class="btn" onclick="annotate()">提交注释</button>
                <div class="examples">
                    <h3>示例:</h3>
                    <span class="example-item" onclick="setVariant('PIK3CA:p.E545K')">PIK3CA:p.E545K</span>
                    <span class="example-item" onclick="setVariant('EGFR:p.L858R')">EGFR:p.L858R</span>
                    <span class="example-item" onclick="setVariant('BRCA1:p.C61G')">BRCA1:p.C61G</span>
                    <span class="example-item" onclick="setVariant('TP53:p.R273H')">TP53:p.R273H</span>
                    <span class="example-item" onclick="setVariant('NM_006218.4:c.1633G>A')">NM_006218.4:c.1633G>A</span>
                </div>
            </div>
            <div id="batch-form" style="display:none;">
                <div class="form-group">
                    <label for="batch-variants">批量变异 (每行一个)</label>
                    <textarea id="batch-variants" class="batch-input" placeholder="PIK3CA:p.E545K&#10;EGFR:p.L858R"></textarea>
                </div>
                <div class="form-group">
                    <label for="batch-refversion">参考基因组版本</label>
                    <select id="batch-refversion">
                        <option value="hg38">hg38 (GRCh38)</option>
                        <option value="hg19">hg19 (GRCh37)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="batch-mode">注释模式</label>
                    <select id="batch-mode">
                        <option value="panno">蛋白注释 (p.)</option>
                        <option value="canno">cDNA注释 (c.)</option>
                        <option value="ganno">基因组注释 (g.)</option>
                    </select>
                </div>
                <button class="btn" onclick="batchAnnotate()">批量提交</button>
            </div>
            <div id="debug-form" style="display:none;">
                <button class="btn" onclick="getDebugInfo()">获取调试信息</button>
                <div id="debug-info" style="margin-top:20px;"></div>
            </div>
            <div id="result" class="result"></div>
            <div id="loading" class="loading" style="display:none;">
                <div class="spinner"></div>
                <p>正在处理...</p>
            </div>
        </div>
    </div>
    <script>
        let currentTab = 'single';
        function switchTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab')[['single', 'batch', 'debug'].indexOf(tab)].classList.add('active');
            document.getElementById('single-form').style.display = tab === 'single' ? 'block' : 'none';
            document.getElementById('batch-form').style.display = tab === 'batch' ? 'block' : 'none';
            document.getElementById('debug-form').style.display = tab === 'debug' ? 'block' : 'none';
            document.getElementById('result').style.display = 'none';
        }
        function setVariant(v) { document.getElementById('variant').value = v; }
        function showResult(success, message, isWarning = false) {
            const resultDiv = document.getElementById('result');
            resultDiv.className = 'result ' + (isWarning ? 'warning' : (success ? 'success' : 'error'));
            resultDiv.innerHTML = '<div class="result-title">' + (success ? '注释结果' : '错误') + '</div><div class="result-content">' + message + '</div>';
            resultDiv.style.display = 'block';
        }
        async function annotate() {
            const variant = document.getElementById('variant').value.trim();
            if (!variant) { showResult(false, '请输入变异描述'); return; }
            const refversion = document.getElementById('refversion').value;
            const mode = document.getElementById('mode').value;
            document.getElementById('loading').style.display = 'block';
            document.getElementById('result').style.display = 'none';
            try {
                const response = await fetch('/api/annotate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({variant, refversion, mode})
                });
                const data = await response.json();
                if (data.success) {
                    showResult(true, data.result || '(无输出)', !!data.warning);
                } else {
                    showResult(false, data.error || '注释失败');
                }
            } catch (e) {
                showResult(false, '请求失败: ' + e.message);
            } finally {
                document.getElementById('loading').style.display = 'none';
            }
        }
        async function batchAnnotate() {
            const variants = document.getElementById('batch-variants').value.trim().split('\\n').filter(v => v.trim());
            if (!variants.length) { showResult(false, '请输入变异列表'); return; }
            const refversion = document.getElementById('batch-refversion').value;
            const mode = document.getElementById('batch-mode').value;
            document.getElementById('loading').style.display = 'block';
            document.getElementById('result').style.display = 'none';
            try {
                const response = await fetch('/api/batch_annotate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({variants, refversion, mode})
                });
                const data = await response.json();
                let output = '';
                data.results.forEach(r => {
                    output += '输入: ' + r.input + '\\n';
                    if (r.success) {
                        output += r.result || '(无输出)';
                        if (r.warning) output += '\\n⚠️ ' + r.warning;
                    } else {
                        output += '❌ 错误: ' + (r.error || '失败');
                    }
                    output += '\\n---\\n';
                });
                showResult(true, output);
            } catch (e) {
                showResult(false, '请求失败: ' + e.message);
            } finally {
                document.getElementById('loading').style.display = 'none';
            }
        }
        async function getDebugInfo() {
            try {
                const response = await fetch('/api/debug');
                const data = await response.json();
                let html = '<h4>调试信息</h4>';
                html += '<p><strong>TransVar 版本:</strong> ' + data.transvar_version + '</p>';
                if (data.config_hg38) {
                    html += '<h5 style="margin-top:10px;">hg38 配置:</h5>';
                    html += '<pre style="background:#f5f5f5;padding:10px;font-size:12px;">' + data.config_hg38 + '</pre>';
                }
                if (data.test_results) {
                    html += '<h5 style="margin-top:10px;">测试结果:</h5>';
                    data.test_results.forEach(t => {
                        html += '<div style="margin:10px 0;padding:10px;background:#f9f9f9;border-radius:4px;">';
                        html += '<strong>' + t.test + '</strong><br>';
                        if (t.stdout) html += '<pre style="margin:5px 0;font-size:11px;">' + t.stdout + '</pre>';
                        if (t.error) html += '<span style="color:red;">Error: ' + t.error + '</span>';
                        html += '</div>';
                    });
                }
                document.getElementById('debug-info').innerHTML = html;
            } catch (e) {
                document.getElementById('debug-info').innerHTML = '<p style="color:red">获取失败: ' + e.message + '</p>';
            }
        }
    </script>
</body>
</html>
    """


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "service": "TransVar API"}


@app.get("/api/debug")
async def debug_info():
    """调试接口"""
    logger.info("调试接口被调用")

    # 检测 transvar 版本
    transvar_version = ""
    try:
        result = subprocess.run(["transvar", "--version"], capture_output=True, text=True, timeout=10)
        transvar_version = result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        transvar_version = f"Error: {str(e)}"

    # 获取配置信息
    config_hg38 = ""
    config_hg19 = ""
    try:
        result = subprocess.run(["transvar", "config", "--refversion", "hg38"], capture_output=True, text=True, timeout=10)
        config_hg38 = result.stdout
    except Exception as e:
        config_hg38 = f"Error: {str(e)}"

    try:
        result = subprocess.run(["transvar", "config", "--refversion", "hg19"], capture_output=True, text=True, timeout=10)
        config_hg19 = result.stdout
    except Exception as e:
        config_hg19 = f"Error: {str(e)}"

    # 测试
    test_results = []

    # Test 1: PIK3CA
    try:
        result = subprocess.run(
            ["transvar", "panno", "-i", "PIK3CA:p.E545K", "--refversion", "hg38", "-o", "/dev/stdout"],
            capture_output=True, text=True, timeout=60
        )
        test_results.append({
            "test": "PIK3CA:p.E545K (hg38)",
            "returncode": result.returncode,
            "stdout": result.stdout.strip()[:500] if result.stdout else "",
            "stderr": result.stderr.strip()[:200] if result.stderr else ""
        })
    except Exception as e:
        test_results.append({"test": "PIK3CA:p.E545K", "error": str(e)})

    # Test 2: NM_006218.4
    try:
        result = subprocess.run(
            ["transvar", "canno", "-i", "NM_006218.4:c.1633G>A", "--refversion", "hg38", "-o", "/dev/stdout"],
            capture_output=True, text=True, timeout=60
        )
        test_results.append({
            "test": "NM_006218.4:c.1633G>A (hg38)",
            "returncode": result.returncode,
            "stdout": result.stdout.strip()[:500] if result.stdout else "",
            "stderr": result.stderr.strip()[:200] if result.stderr else ""
        })
    except Exception as e:
        test_results.append({"test": "NM_006218.4:c.1633G>A", "error": str(e)})

    return {
        "service": "TransVar API",
        "transvar_version": transvar_version,
        "config_hg38": config_hg38,
        "config_hg19": config_hg19,
        "test_results": test_results
    }


@app.post("/api/annotate", response_model=AnnotationResponse)
async def annotate(request: AnnotationRequest):
    """单个变异注释接口"""
    logger.info(f"收到注释请求: variant={request.variant}, refversion={request.refversion}, mode={request.mode}")

    result = run_transvar(request.variant, request.mode, request.refversion)

    return AnnotationResponse(
        success=result.get("success", False),
        input=request.variant,
        refversion=request.refversion,
        mode=request.mode,
        result=result.get("result"),
        error=result.get("error"),
        warning=result.get("warning"),
        raw_output=result.get("raw_output")
    )


@app.post("/api/batch_annotate")
async def batch_annotate(request: BatchAnnotationRequest):
    """批量变异注释接口"""
    results = []

    for variant in request.variants:
        result = run_transvar(variant.strip(), request.mode, request.refversion)
        results.append({
            "input": variant,
            "success": result.get("success", False),
            "result": result.get("result"),
            "error": result.get("error"),
            "warning": result.get("warning")
        })

    return {
        "success": True,
        "total": len(results),
        "results": results
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)