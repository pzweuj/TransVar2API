#!/usr/bin/env python3
"""
TransVar API Service
提供 HGVS 变异注释的 RESTful API 服务
"""

import os
import subprocess
import json
import re
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(
    title="TransVar API",
    description="HGVS 变异注释工具 TransVar 的 RESTful API 服务",
    version="1.0.0"
)

# 启用 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据库路径配置
DB_PATH = os.getenv("TRANSVAR_DB_PATH", "/data/transvar_db")
# UCSC 数据库
UCSC_HG38 = f"{DB_PATH}/ucsc_hg38"
UCSC_HG19 = f"{DB_PATH}/ucsc_hg19"
# NCBI RefSeq 数据库
REFSEQ_HG38 = f"{DB_PATH}/ncbi_refseq_hg38"
REFSEQ_HG19 = f"{DB_PATH}/ncbi_refseq_hg19"


class AnnotationRequest(BaseModel):
    """变异注释请求模型"""
    variant: str = Field(..., description="变异描述，如 PIK3CA:p.E545K 或 NM_006218.4:c.1633G>A")
    refversion: str = Field(default="hg38_refseq", description="参考基因组版本: hg38_refseq 或 hg19_refseq")
    mode: str = Field(default="panno", description="注释模式: panno(蛋白), canno(cDNA), ganno(DNA), codonsearch(密码子)")


class AnnotationResponse(BaseModel):
    """变异注释响应模型"""
    success: bool
    input: str
    refversion: str
    mode: str
    result: Optional[str] = None
    error: Optional[str] = None
    raw_output: Optional[str] = None


class BatchAnnotationRequest(BaseModel):
    """批量注释请求模型"""
    variants: List[str] = Field(..., description="变异列表")
    refversion: str = Field(default="hg38_refseq", description="参考基因组版本")
    mode: str = Field(default="panno", description="注释模式")


class DatabaseInfo(BaseModel):
    """数据库信息模型"""
    hg38: Dict[str, Any]
    hg19: Dict[str, Any]


def run_transvar(variant: str, mode: str, refversion: str) -> Dict[str, Any]:
    """
    执行 TransVar 命令

    Args:
        variant: 变异描述
        mode: 注释模式 (panno/canno/ganno/codonsearch)
        refversion: 参考基因组版本

    Returns:
        包含执行结果的字典
    """
    # 验证模式
    valid_modes = ["panno", "canno", "ganno", "codonsearch"]
    if mode not in valid_modes:
        return {
            "success": False,
            "error": f"无效的模式: {mode}，支持的模式: {', '.join(valid_modes)}"
        }

    # 选择数据库路径和类型
    # UCSC: hg38_refseq, hg19_refseq
    # NCBI RefSeq: hg38_ncbi_refseq, hg19_ncbi_refseq
    if "ncbi_refseq" in refversion:
        db_type = "--refseq"
        if "hg38" in refversion:
            db_path = REFSEQ_HG38
            refseq_file = f"{db_path}/hg38_refseq.gff.gz"
        elif "hg19" in refversion:
            db_path = REFSEQ_HG19
            refseq_file = f"{db_path}/hg19_refseq.gff.gz"
        else:
            return {"success": False, "error": f"无效的版本: {refversion}"}
    elif "hg38" in refversion:
        db_type = "--ucsc"
        db_path = UCSC_HG38
        refseq_file = f"{db_path}/ncbiRefSeq.txt.gz"
    elif "hg19" in refversion:
        db_type = "--ucsc"
        db_path = UCSC_HG19
        refseq_file = f"{db_path}/ncbiRefSeq.txt.gz"
    else:
        return {
            "success": False,
            "error": f"无效的参考基因组版本: {refversion}，支持的版本: hg38_refseq, hg19_refseq, hg38_ncbi_refseq, hg19_ncbi_refseq"
        }

    # 检查数据库是否存在
    reference_file = f"{db_path}/hg38.fa" if "hg38" in refversion else f"{db_path}/hg19.fa"

    if not os.path.exists(refseq_file):
        return {
            "success": False,
            "error": f"数据库文件不存在: {refseq_file}，请先运行构建脚本"
        }

    if not os.path.exists(reference_file):
        return {
            "success": False,
            "error": f"参考基因组文件不存在: {reference_file}"
        }

    # 构建 TransVar 命令
    cmd = [
        "transvar", mode,
        "-i", variant,
        db_type,
        "--refversion", refversion,
        "-o", "/dev/stdout"
    ]

    try:
        # 设置环境变量，确保 transvar 能找到配置文件和数据库
        env = {
            **os.environ,
            "TRANSVAR_DB_PATH": db_path,
            "HOME": os.path.expanduser("~")
        }
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            cwd="/app"  # 在工作目录下运行
        )

        output = result.stdout
        error = result.stderr

        if result.returncode == 0 and output:
            return {
                "success": True,
                "result": output.strip(),
                "raw_output": output
            }
        else:
            return {
                "success": False,
                "error": error.strip() if error else "未找到注释结果",
                "raw_output": output
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "执行超时，请检查变异格式是否正确"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"执行错误: {str(e)}"
        }


def parse_transvar_output(output: str) -> Dict[str, Any]:
    """
    解析 TransVar 输出

    Args:
        output: TransVar 原始输出

    Returns:
        解析后的结构化数据
    """
    lines = output.strip().split('\n')
    parsed = {
        "input": "",
        "gene": "",
        "transcript": "",
        "variation": "",
        "interpretation": ""
    }

    for line in lines:
        if line.startswith('input'):
            parsed["input"] = line.split(':', 1)[1].strip()
        elif line.startswith('gene'):
            parsed["gene"] = line.split(':', 1)[1].strip()
        elif line.startswith('transcript'):
            parsed["transcript"] = line.split(':', 1)[1].strip()
        elif line.startswith('variation'):
            parsed["variation"] = line.split(':', 1)[1].strip()
        elif line.startswith('interpretation'):
            parsed["interpretation"] = line.split(':', 1)[1].strip()

    return parsed


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
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        .card {
            background: white;
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            margin-bottom: 20px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            color: #333;
        }
        input, select {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input:focus, select:focus {
            outline: none;
            border-color: #667eea;
        }
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
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
        }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        .result {
            margin-top: 20px;
            padding: 20px;
            border-radius: 8px;
            display: none;
        }
        .result.success {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            display: block;
        }
        .result.error {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            display: block;
        }
        .result-title {
            font-weight: 600;
            margin-bottom: 10px;
            font-size: 1.1em;
        }
        .result-content {
            font-family: 'Courier New', monospace;
            white-space: pre-wrap;
            word-break: break-all;
            background: white;
            padding: 15px;
            border-radius: 6px;
            max-height: 400px;
            overflow-y: auto;
        }
        .examples {
            margin-top: 20px;
        }
        .examples h3 {
            color: #333;
            margin-bottom: 15px;
        }
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
        .example-item:hover {
            background: #e0e0e0;
        }
        .tabs {
            display: flex;
            border-bottom: 2px solid #e0e0e0;
            margin-bottom: 20px;
        }
        .tab {
            padding: 12px 24px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            margin-bottom: -2px;
            transition: all 0.2s;
        }
        .tab.active {
            border-bottom-color: #667eea;
            color: #667eea;
            font-weight: 600;
        }
        .batch-input {
            width: 100%;
            min-height: 150px;
            font-family: 'Courier New', monospace;
        }
        .loading {
            text-align: center;
            padding: 20px;
        }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .info-box {
            background: #e7f3ff;
            border-left: 4px solid #2196F3;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        .info-box h4 {
            color: #1976D2;
            margin-bottom: 8px;
        }
        .info-box p {
            color: #555;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>TransVar HGVS 注释工具</h1>
            <p>使用 RefSeq 数据库进行变异注释</p>
        </div>

        <div class="card">
            <div class="info-box">
                <h4>简介</h4>
                <p>TransVar 是一个强大的 HGVS 变异注释工具，支持蛋白 (p.)、cDNA (c.) 和基因组 (g.) 水平的变异注释。使用 RefSeq 转录本数据库，确保临床基因诊断的准确性。</p>
            </div>

            <div class="tabs">
                <div class="tab active" onclick="switchTab('single')">单个注释</div>
                <div class="tab" onclick="switchTab('batch')">批量注释</div>
                <div class="tab" onclick="switchTab('info')">数据库信息</div>
            </div>

            <div id="single-form">
                <div class="form-group">
                    <label for="variant">变异描述 (HGVS)</label>
                    <input type="text" id="variant" placeholder="例如: PIK3CA:p.E545K 或 NM_006218.4:c.1633G>A">
                </div>

                <div class="form-group">
                    <label for="refversion">参考基因组版本</label>
                    <select id="refversion">
                        <option value="hg38_refseq">hg38 (GRCh38) - 推荐</option>
                        <option value="hg19_refseq">hg19 (GRCh37)</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="mode">注释模式</label>
                    <select id="mode">
                        <option value="panno">蛋白注释 (p.) 例如: p.E545K</option>
                        <option value="canno">cDNA注释 (c.) 例如: c.1633G>A</option>
                        <option value="ganno">基因组注释 (g.) 例如: g.178921852G>A</option>
                        <option value="codonsearch">密码子搜索 例如: KRAS:c.12GTT></option>
                    </select>
                </div>

                <button class="btn" onclick="annotate()">提交注释</button>

                <div class="examples">
                    <h3>示例:</h3>
                    <span class="example-item" onclick="setVariant('PIK3CA:p.E545K')">PIK3CA:p.E545K</span>
                    <span class="example-item" onclick="setVariant('EGFR:p.L858R')">EGFR:p.L858R</span>
                    <span class="example-item" onclick="setVariant('BRCA1:p.C61G')">BRCA1:p.C61G</span>
                    <span class="example-item" onclick="setVariant('NM_006218.4:c.1633G>A')">NM_006218.4:c.1633G>A</span>
                    <span class="example-item" onclick="setVariant('TP53:p.R273H')">TP53:p.R273H</span>
                    <span class="example-item" onclick="setVariant('KRAS:c.12GTT>TTC')">KRAS:c.12GTT>TTC</span>
                </div>
            </div>

            <div id="batch-form" style="display:none;">
                <div class="form-group">
                    <label for="batch-variants">批量变异 (每行一个)</label>
                    <textarea id="batch-variants" class="batch-input" placeholder="PIK3CA:p.E545K&#10;EGFR:p.L858R&#10;BRCA1:p.C61G"></textarea>
                </div>

                <div class="form-group">
                    <label for="batch-refversion">参考基因组版本</label>
                    <select id="batch-refversion">
                        <option value="hg38_refseq">hg38 (GRCh38)</option>
                        <option value="hg19_refseq">hg19 (GRCh37)</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="batch-mode">注释模式</label>
                    <select id="batch-mode">
                        <option value="panno">蛋白注释 (p.)</option>
                        <option value="canno">cDNA注释 (c.)</option>
                        <option value="ganno">基因组注释 (g.)</option>
                        <option value="codonsearch">密码子搜索</option>
                    </select>
                </div>

                <button class="btn" onclick="batchAnnotate()">批量提交</button>
            </div>

            <div id="info-form" style="display:none;">
                <div id="db-info">
                    <p>点击"查看数据库信息"按钮获取详细信息</p>
                </div>
                <button class="btn" onclick="getDbInfo()">查看数据库信息</button>
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
            document.querySelectorAll('.tab')[['single', 'batch', 'info'].indexOf(tab)].classList.add('active');

            document.getElementById('single-form').style.display = tab === 'single' ? 'block' : 'none';
            document.getElementById('batch-form').style.display = tab === 'batch' ? 'block' : 'none';
            document.getElementById('info-form').style.display = tab === 'info' ? 'block' : 'none';

            document.getElementById('result').style.display = 'none';
        }

        function setVariant(variant) {
            document.getElementById('variant').value = variant;
        }

        function showResult(success, message) {
            const resultDiv = document.getElementById('result');
            resultDiv.className = 'result ' + (success ? 'success' : 'error');
            resultDiv.innerHTML = '<div class="result-title">' + (success ? '注释结果' : '错误') + '</div><div class="result-content">' + message + '</div>';
            resultDiv.style.display = 'block';
        }

        async function annotate() {
            const variant = document.getElementById('variant').value.trim();
            const refversion = document.getElementById('refversion').value;
            const mode = document.getElementById('mode').value;

            if (!variant) {
                showResult(false, '请输入变异描述');
                return;
            }

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
                    showResult(true, data.result || data.raw_output || '注释成功但无输出');
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
            const refversion = document.getElementById('batch-refversion').value;
            const mode = document.getElementById('batch-mode').value;

            if (!variants.length) {
                showResult(false, '请输入变异列表');
                return;
            }

            document.getElementById('loading').style.display = 'block';
            document.getElementById('result').style.display = 'none';

            try {
                const response = await fetch('/api/batch_annotate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({variants, refversion, mode})
                });
                const data = await response.json();

                if (data.success) {
                    let output = '';
                    data.results.forEach(r => {
                        output += '输入: ' + r.input + '\\n';
                        output += '结果: ' + (r.result || r.error || '无输出') + '\\n';
                        output += '---\\n';
                    });
                    showResult(true, output);
                } else {
                    showResult(false, data.error || '批量注释失败');
                }
            } catch (e) {
                showResult(false, '请求失败: ' + e.message);
            } finally {
                document.getElementById('loading').style.display = 'none';
            }
        }

        async function getDbInfo() {
            try {
                const response = await fetch('/api/db_info');
                const data = await response.json();

                let html = '<h3>数据库状态</h3><ul>';
                html += '<li><strong>hg38:</strong> ' + (data.hg38.available ? '已安装' : '未安装') + '</li>';
                html += '<li><strong>hg19:</strong> ' + (data.hg19.available ? '已安装' : '未安装') + '</li>';
                html += '</ul>';

                document.getElementById('db-info').innerHTML = html;
            } catch (e) {
                document.getElementById('db-info').innerHTML = '<p style="color:red">获取失败: ' + e.message + '</p>';
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


@app.post("/api/annotate", response_model=AnnotationResponse)
async def annotate(request: AnnotationRequest):
    """
    单个变异注释接口

    - **variant**: 变异描述 (如 PIK3CA:p.E545K)
    - **refversion**: 参考基因组版本 (hg38_refseq 或 hg19_refseq)
    - **mode**: 注释模式 (panno/canno/ganno/codonsearch)
    """
    result = run_transvar(request.variant, request.mode, request.refversion)

    return AnnotationResponse(
        success=result.get("success", False),
        input=request.variant,
        refversion=request.refversion,
        mode=request.mode,
        result=result.get("result"),
        error=result.get("error"),
        raw_output=result.get("raw_output")
    )


@app.post("/api/batch_annotate")
async def batch_annotate(request: BatchAnnotationRequest):
    """
    批量变异注释接口

    - **variants**: 变异列表
    - **refversion**: 参考基因组版本
    - **mode**: 注释模式
    """
    results = []

    for variant in request.variants:
        result = run_transvar(variant.strip(), request.mode, request.refversion)
        results.append({
            "input": variant,
            "success": result.get("success", False),
            "result": result.get("result"),
            "error": result.get("error")
        })

    return {
        "success": True,
        "total": len(results),
        "results": results
    }


@app.get("/api/db_info", response_model=DatabaseInfo)
async def get_db_info():
    """获取数据库信息"""
    def check_db(db_path):
        refseq_file = f"{db_path}/ncbiRefSeq.txt.gz"
        reference_file = f"{db_path}/hg38.fa"
        if "hg19" in db_path:
            reference_file = f"{db_path}/hg19.fa"

        return {
            "available": os.path.exists(refseq_file) and os.path.exists(reference_file),
            "refseq_file": refseq_file,
            "reference_file": reference_file
        }

    return DatabaseInfo(
        hg38=check_db(HG38_REFSEQ),
        hg19=check_db(HG19_REFSEQ)
    )


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)