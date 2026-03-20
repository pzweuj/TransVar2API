#!/usr/bin/env python3
"""
TransVar API Service
提供 HGVS 变异注释的 RESTful API 服务
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
    version="1.1.0"
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
    refversion: str = Field(default="hg38", description="参考基因组版本: hg38 或 hg19")
    mode: str = Field(default="panno", description="注释模式: panno(蛋白), canno(cDNA), ganno(DNA), codonsearch(密码子)")
    sources: List[str] = Field(default=["ucsc"], description="数据库来源: ucsc 和/或 ncbi_refseq")


class AnnotationResponse(BaseModel):
    """变异注释响应模型"""
    success: bool
    input: str
    refversion: str
    mode: str
    sources: List[str] = []
    results: Optional[List[Dict[str, Any]]] = None
    result: Optional[str] = None  # 兼容旧版，合并后的结果
    error: Optional[str] = None
    raw_output: Optional[str] = None


class BatchAnnotationRequest(BaseModel):
    """批量注释请求模型"""
    variants: List[str] = Field(..., description="变异列表")
    refversion: str = Field(default="hg38", description="参考基因组版本")
    mode: str = Field(default="panno", description="注释模式")
    sources: List[str] = Field(default=["ucsc"], description="数据库来源: ucsc 和/或 ncbi_refseq")


class DatabaseInfo(BaseModel):
    """数据库信息模型"""
    hg38: Dict[str, Any]
    hg19: Dict[str, Any]


def run_transvar(variant: str, mode: str, refversion: str, source: str = "ucsc") -> Dict[str, Any]:
    """
    执行 TransVar 命令

    Args:
        variant: 变异描述
        mode: 注释模式 (panno/canno/ganno/codonsearch)
        refversion: 参考基因组版本 (hg38 或 hg19)
        source: 数据库来源 (ucsc 或 ncbi_refseq)

    Returns:
        包含执行结果的字典
    """
    logger.info(f"开始处理: variant={variant}, mode={mode}, refversion={refversion}, source={source}")

    # 验证模式
    valid_modes = ["panno", "canno", "ganno", "codonsearch"]
    if mode not in valid_modes:
        logger.error(f"无效的模式: {mode}")
        return {
            "success": False,
            "error": f"无效的模式: {mode}，支持的模式: {', '.join(valid_modes)}"
        }

    # 验证数据库来源
    valid_sources = ["ucsc", "ncbi_refseq"]
    if source not in valid_sources:
        logger.error(f"无效的数据库来源: {source}")
        return {
            "success": False,
            "error": f"无效的数据库来源: {source}，支持的来源: {', '.join(valid_sources)}"
        }

    # 根据 source 和 refversion 确定 transvar 使用的 refversion 名称
    # 统一命名风格: hg38_ucsc, hg19_ucsc, hg38_ncbi, hg19_ncbi
    if source == "ncbi_refseq":
        db_type = "--refseq"
        if refversion == "hg38":
            transvar_refversion = "hg38_ncbi"
            db_path = REFSEQ_HG38
        elif refversion == "hg19":
            transvar_refversion = "hg19_ncbi"
            db_path = REFSEQ_HG19
        else:
            logger.error(f"无效的版本: {refversion}")
            return {"success": False, "error": f"无效的版本: {refversion}"}
    else:  # ucsc
        db_type = "--ucsc"
        if refversion == "hg38":
            transvar_refversion = "hg38_ucsc"
            db_path = UCSC_HG38
        elif refversion == "hg19":
            transvar_refversion = "hg19_ucsc"
            db_path = UCSC_HG19
        else:
            logger.error(f"无效的版本: {refversion}")
            return {"success": False, "error": f"无效的版本: {refversion}"}

    logger.info(f"使用 transvar refversion: {transvar_refversion}")

    # 构建 TransVar 命令 - 使用旧版本格式，依赖 transvar config 配置
    # 不指定文件路径，让 transvar 从配置文件读取
    cmd = [
        "transvar", mode,
        "-i", variant,
        db_type,
        "--refversion", transvar_refversion,
        "-o", "/dev/stdout"
    ]
    logger.info(f"执行命令: {' '.join(cmd)}")

    try:
        env = {
            **os.environ,
            "TRANSVAR_DB_PATH": DB_PATH,
            "HOME": os.path.expanduser("~")
        }
        logger.info(f"开始执行 transvar 命令，超时设置为 120 秒")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 增加超时时间到 120 秒
            env=env,
            cwd="/app"
        )

        output = result.stdout
        error = result.stderr
        logger.info(f"命令返回码: {result.returncode}")
        logger.info(f"标准输出长度: {len(output)} 字符")
        if error:
            logger.warning(f"标准错误: {error[:500]}")  # 只记录前500字符

        if result.returncode == 0 and output:
            logger.info(f"执行成功")
            return {
                "success": True,
                "source": source,
                "result": output.strip(),
                "raw_output": output
            }
        else:
            logger.error(f"执行失败: returncode={result.returncode}")
            return {
                "success": False,
                "source": source,
                "error": error.strip() if error else "未找到注释结果",
                "raw_output": output
            }

    except subprocess.TimeoutExpired:
        logger.error(f"执行超时: variant={variant}")
        return {
            "success": False,
            "source": source,
            "error": "执行超时（120秒），请检查变异格式是否正确或稍后重试"
        }
    except Exception as e:
        logger.exception(f"执行异常: {str(e)}")
        return {
            "success": False,
            "source": source,
            "error": f"执行错误: {str(e)}"
        }


def parse_transvar_output(output: str) -> Dict[str, Any]:
    """
    解析 TransVar 输出
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
        input[type="text"], select, textarea {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        .checkbox-group {
            display: flex;
            gap: 20px;
            margin-top: 8px;
        }
        .checkbox-item {
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
        }
        .checkbox-item input[type="checkbox"] {
            width: 18px;
            height: 18px;
            cursor: pointer;
        }
        .checkbox-item label {
            margin: 0;
            cursor: pointer;
            font-weight: normal;
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
            max-height: 500px;
            overflow-y: auto;
        }
        .source-label {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            margin-right: 8px;
        }
        .source-ucsc {
            background: #e3f2fd;
            color: #1565c0;
        }
        .source-ncbi {
            background: #f3e5f5;
            color: #7b1fa2;
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
        .db-status {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            margin-left: 8px;
        }
        .db-available {
            background: #c8e6c9;
            color: #2e7d32;
        }
        .db-unavailable {
            background: #ffcdd2;
            color: #c62828;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>TransVar HGVS 注释工具</h1>
            <p>支持 UCSC RefSeq 和 NCBI RefSeq 数据库进行变异注释</p>
        </div>

        <div class="card">
            <div class="info-box">
                <h4>简介</h4>
                <p>TransVar 是一个强大的 HGVS 变异注释工具，支持蛋白 (p.)、cDNA (c.) 和基因组 (g.) 水平的变异注释。您可以选择使用 UCSC RefSeq 或 NCBI RefSeq 转录本数据库，或同时使用两者进行注释。</p>
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
                        <option value="hg38">hg38 (GRCh38) - 推荐</option>
                        <option value="hg19">hg19 (GRCh37)</option>
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

                <div class="form-group">
                    <label>数据库来源 (可多选)</label>
                    <div class="checkbox-group">
                        <div class="checkbox-item">
                            <input type="checkbox" id="source-ucsc" value="ucsc" checked>
                            <label for="source-ucsc">UCSC RefSeq</label>
                        </div>
                        <div class="checkbox-item">
                            <input type="checkbox" id="source-ncbi" value="ncbi_refseq">
                            <label for="source-ncbi">NCBI RefSeq</label>
                        </div>
                    </div>
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
                        <option value="codonsearch">密码子搜索</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>数据库来源 (可多选)</label>
                    <div class="checkbox-group">
                        <div class="checkbox-item">
                            <input type="checkbox" id="batch-source-ucsc" value="ucsc" checked>
                            <label for="batch-source-ucsc">UCSC RefSeq</label>
                        </div>
                        <div class="checkbox-item">
                            <input type="checkbox" id="batch-source-ncbi" value="ncbi_refseq">
                            <label for="batch-source-ncbi">NCBI RefSeq</label>
                        </div>
                    </div>
                </div>

                <button class="btn" onclick="batchAnnotate()">批量提交</button>
            </div>

            <div id="info-form" style="display:none;">
                <div id="db-info">
                    <p>点击"查看数据库信息"按钮获取详细信息</p>
                </div>
                <button class="btn" onclick="getDbInfo()">查看数据库信息</button>
                <button class="btn" style="margin-left:10px;background:linear-gradient(135deg, #f44336 0%, #c62828 100%);" onclick="getDebugInfo()">调试信息</button>
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

        function getSources(prefix) {
            const sources = [];
            if (document.getElementById(prefix + '-source-ucsc').checked) {
                sources.push('ucsc');
            }
            if (document.getElementById(prefix + '-source-ncbi').checked) {
                sources.push('ncbi_refseq');
            }
            return sources.length > 0 ? sources : ['ucsc'];
        }

        function showResult(success, message) {
            const resultDiv = document.getElementById('result');
            resultDiv.className = 'result ' + (success ? 'success' : 'error');
            resultDiv.innerHTML = '<div class="result-title">' + (success ? '注释结果' : '错误') + '</div><div class="result-content">' + message + '</div>';
            resultDiv.style.display = 'block';
        }

        function formatSourceLabel(source) {
            const labelClass = source === 'ucsc' ? 'source-ucsc' : 'source-ncbi';
            const labelName = source === 'ucsc' ? 'UCSC' : 'NCBI';
            return '<span class="source-label ' + labelClass + '">' + labelName + '</span>';
        }

        async function annotate() {
            const variant = document.getElementById('variant').value.trim();
            const refversion = document.getElementById('refversion').value;
            const mode = document.getElementById('mode').value;
            const sources = getSources('');

            if (!variant) {
                showResult(false, '请输入变异描述');
                return;
            }

            document.getElementById('loading').style.display = 'block';
            document.getElementById('result').style.display = 'none';

            // 添加请求超时控制
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 150000); // 150秒超时

            try {
                const response = await fetch('/api/annotate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({variant, refversion, mode, sources}),
                    signal: controller.signal
                });
                clearTimeout(timeoutId);

                if (!response.ok) {
                    throw new Error('HTTP ' + response.status + ': ' + response.statusText);
                }

                const data = await response.json();

                if (data.success && data.results) {
                    let output = '';
                    data.results.forEach(r => {
                        output += formatSourceLabel(r.source) + '\\n';
                        if (r.success) {
                            output += r.result || '无输出';
                        } else {
                            output += '错误: ' + (r.error || '注释失败');
                        }
                        output += '\\n\\n' + '─'.repeat(60) + '\\n\\n';
                    });
                    showResult(true, output);
                } else {
                    showResult(false, data.error || '注释失败');
                }
            } catch (e) {
                clearTimeout(timeoutId);
                if (e.name === 'AbortError') {
                    showResult(false, '请求超时（150秒），服务器可能正在处理复杂请求，请稍后重试');
                } else {
                    showResult(false, '请求失败: ' + e.message);
                }
            } finally {
                document.getElementById('loading').style.display = 'none';
            }
        }

        async function batchAnnotate() {
            const variants = document.getElementById('batch-variants').value.trim().split('\\n').filter(v => v.trim());
            const refversion = document.getElementById('batch-refversion').value;
            const mode = document.getElementById('batch-mode').value;
            const sources = getSources('batch-');

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
                    body: JSON.stringify({variants, refversion, mode, sources})
                });
                const data = await response.json();

                if (data.success) {
                    let output = '';
                    data.results.forEach(r => {
                        output += '输入: ' + r.input + '\\n';
                        if (r.results) {
                            r.results.forEach(sr => {
                                output += formatSourceLabel(sr.source) + ' ';
                                output += (sr.success ? (sr.result || '无输出') : '错误: ' + (sr.error || '失败'));
                                output += '\\n';
                            });
                        } else {
                            output += '结果: ' + (r.result || r.error || '无输出');
                        }
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

                let html = '<h3>数据库状态</h3>';

                html += '<h4 style="margin-top:15px;color:#333;">hg38 (GRCh38)</h4><ul>';
                html += '<li><strong>UCSC RefSeq:</strong> ' + (data.hg38.ucsc_available ? '<span class="db-status db-available">可用</span>' : '<span class="db-status db-unavailable">不可用</span>') + '</li>';
                html += '<li><strong>NCBI RefSeq:</strong> ' + (data.hg38.ncbi_available ? '<span class="db-status db-available">可用</span>' : '<span class="db-status db-unavailable">不可用</span>') + '</li>';
                html += '</ul>';

                html += '<h4 style="margin-top:15px;color:#333;">hg19 (GRCh37)</h4><ul>';
                html += '<li><strong>UCSC RefSeq:</strong> ' + (data.hg19.ucsc_available ? '<span class="db-status db-available">可用</span>' : '<span class="db-status db-unavailable">不可用</span>') + '</li>';
                html += '<li><strong>NCBI RefSeq:</strong> ' + (data.hg19.ncbi_available ? '<span class="db-status db-available">可用</span>' : '<span class="db-status db-unavailable">不可用</span>') + '</li>';
                html += '</ul>';

                document.getElementById('db-info').innerHTML = html;
            } catch (e) {
                document.getElementById('db-info').innerHTML = '<p style="color:red">获取失败: ' + e.message + '</p>';
            }
        }

        async function getDebugInfo() {
            try {
                const response = await fetch('/api/debug');
                const data = await response.json();

                let html = '<h3>调试信息</h3>';
                html += '<p><strong>服务:</strong> ' + data.service + '</p>';
                html += '<p><strong>数据库路径:</strong> ' + data.db_path + '</p>';
                html += '<p><strong>TransVar 可用:</strong> ' + (data.transvar_available ? '是' : '否') + '</p>';
                html += '<p><strong>TransVar 版本:</strong> ' + data.transvar_version + '</p>';

                html += '<h4 style="margin-top:15px;">hg38 文件状态</h4>';
                html += '<pre style="background:#f5f5f5;padding:10px;overflow-x:auto;font-size:12px;">' + JSON.stringify(data.hg38, null, 2) + '</pre>';

                html += '<h4 style="margin-top:15px;">hg19 文件状态</h4>';
                html += '<pre style="background:#f5f5f5;padding:10px;overflow-x:auto;font-size:12px;">' + JSON.stringify(data.hg19, null, 2) + '</pre>';

                document.getElementById('db-info').innerHTML = html;
            } catch (e) {
                document.getElementById('db-info').innerHTML = '<p style="color:red">获取调试信息失败: ' + e.message + '</p>';
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
    """调试接口 - 检查服务状态和数据库"""
    logger.info("调试接口被调用")

    def check_db_files(refversion):
        if refversion == "hg38":
            ucsc_path = UCSC_HG38
            ncbi_path = REFSEQ_HG38
        else:
            ucsc_path = UCSC_HG19
            ncbi_path = REFSEQ_HG19

        files_status = {}

        # UCSC 文件
        ucsc_refseq = f"{ucsc_path}/ncbiRefSeq.txt.gz"
        ucsc_ref = f"{ucsc_path}/{refversion}.fa"
        ucsc_db = f"{ucsc_path}/ncbiRefSeq.txt.gz.transvardb"
        ucsc_gene_idx = f"{ucsc_path}/ncbiRefSeq.txt.gz.gene_idx"
        ucsc_trxn_idx = f"{ucsc_path}/ncbiRefSeq.txt.gz.trxn_idx"

        files_status["ucsc"] = {
            "refseq_file": {"path": ucsc_refseq, "exists": os.path.exists(ucsc_refseq)},
            "reference_file": {"path": ucsc_ref, "exists": os.path.exists(ucsc_ref)},
            "transvardb": {"path": ucsc_db, "exists": os.path.exists(ucsc_db)},
            "gene_idx": {"path": ucsc_gene_idx, "exists": os.path.exists(ucsc_gene_idx)},
            "trxn_idx": {"path": ucsc_trxn_idx, "exists": os.path.exists(ucsc_trxn_idx)}
        }

        # NCBI 文件
        ncbi_refseq = f"{ncbi_path}/{refversion}_refseq.gff.gz"
        ncbi_ref = f"{ncbi_path}/{refversion}.fa"
        ncbi_db = f"{ncbi_path}/{refversion}_refseq.gff.gz.transvardb"
        ncbi_gene_idx = f"{ncbi_path}/{refversion}_refseq.gff.gz.gene_idx"
        ncbi_trxn_idx = f"{ncbi_path}/{refversion}_refseq.gff.gz.trxn_idx"

        files_status["ncbi_refseq"] = {
            "refseq_file": {"path": ncbi_refseq, "exists": os.path.exists(ncbi_refseq)},
            "reference_file": {"path": ncbi_ref, "exists": os.path.exists(ncbi_ref)},
            "transvardb": {"path": ncbi_db, "exists": os.path.exists(ncbi_db)},
            "gene_idx": {"path": ncbi_gene_idx, "exists": os.path.exists(ncbi_gene_idx)},
            "trxn_idx": {"path": ncbi_trxn_idx, "exists": os.path.exists(ncbi_trxn_idx)}
        }

        return files_status

    # 测试 transvar 命令是否可用
    transvar_available = False
    transvar_version = ""
    try:
        result = subprocess.run(["transvar", "--version"], capture_output=True, text=True, timeout=10)
        transvar_available = result.returncode == 0
        transvar_version = result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        transvar_version = f"Error: {str(e)}"

    return {
        "service": "TransVar API",
        "db_path": DB_PATH,
        "transvar_available": transvar_available,
        "transvar_version": transvar_version,
        "hg38": check_db_files("hg38"),
        "hg19": check_db_files("hg19")
    }


@app.post("/api/annotate", response_model=AnnotationResponse)
async def annotate(request: AnnotationRequest):
    """
    单个变异注释接口

    - **variant**: 变异描述 (如 PIK3CA:p.E545K)
    - **refversion**: 参考基因组版本 (hg38 或 hg19)
    - **mode**: 注释模式 (panno/canno/ganno/codonsearch)
    - **sources**: 数据库来源列表 (ucsc, ncbi_refseq)
    """
    logger.info(f"收到注释请求: variant={request.variant}, refversion={request.refversion}, mode={request.mode}, sources={request.sources}")

    sources = request.sources if request.sources else ["ucsc"]
    results = []
    all_success = True
    merged_result = ""

    for source in sources:
        logger.info(f"处理数据源: {source}")
        result = run_transvar(request.variant, request.mode, request.refversion, source)
        logger.info(f"数据源 {source} 处理完成: success={result.get('success', False)}")
        results.append({
            "source": source,
            "success": result.get("success", False),
            "result": result.get("result"),
            "error": result.get("error"),
            "raw_output": result.get("raw_output")
        })
        if not result.get("success", False):
            all_success = False
        if result.get("result"):
            merged_result += f"[{source}]\n{result['result']}\n\n"

    logger.info(f"注释请求完成: all_success={all_success}")
    return AnnotationResponse(
        success=all_success or len([r for r in results if r["success"]]) > 0,
        input=request.variant,
        refversion=request.refversion,
        mode=request.mode,
        sources=sources,
        results=results,
        result=merged_result.strip() if merged_result else None,
        error=None if all_success else "部分数据库注释失败"
    )


@app.post("/api/batch_annotate")
async def batch_annotate(request: BatchAnnotationRequest):
    """
    批量变异注释接口

    - **variants**: 变异列表
    - **refversion**: 参考基因组版本
    - **mode**: 注释模式
    - **sources**: 数据库来源列表
    """
    sources = request.sources if request.sources else ["ucsc"]
    results = []

    for variant in request.variants:
        variant_results = []
        for source in sources:
            result = run_transvar(variant.strip(), request.mode, request.refversion, source)
            variant_results.append({
                "source": source,
                "success": result.get("success", False),
                "result": result.get("result"),
                "error": result.get("error")
            })
        results.append({
            "input": variant,
            "success": any(r["success"] for r in variant_results),
            "results": variant_results
        })

    return {
        "success": True,
        "total": len(results),
        "sources": sources,
        "results": results
    }


@app.get("/api/db_info")
async def get_db_info():
    """获取数据库信息"""
    def check_db(refversion):
        if refversion == "hg38":
            ucsc_path = UCSC_HG38
            ncbi_path = REFSEQ_HG38
        else:
            ucsc_path = UCSC_HG19
            ncbi_path = REFSEQ_HG19

        ucsc_transvardb = f"{ucsc_path}/ncbiRefSeq.txt.gz.transvardb"
        ncbi_transvardb = f"{ncbi_path}/{refversion}_refseq.gff.gz.transvardb"
        reference_file = f"{ucsc_path}/{refversion}.fa"

        return {
            "ucsc_available": os.path.exists(ucsc_transvardb) and os.path.exists(reference_file),
            "ncbi_available": os.path.exists(ncbi_transvardb) and os.path.exists(reference_file),
            "ucsc_file": ucsc_transvardb,
            "ncbi_file": ncbi_transvardb,
            "reference_file": reference_file
        }

    return {
        "hg38": check_db("hg38"),
        "hg19": check_db("hg19")
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)