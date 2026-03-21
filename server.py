#!/usr/bin/env python3
"""
TransVar API Service
提供 HGVS 变异注释的 RESTful API 服务

版本 1.6.1 - 修复结果输出显示
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
    version="1.6.1"
)

# 启用 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 支持的数据库
SUPPORTED_DATABASES = {
    "refseq": {"flag": "--refseq", "name": "RefSeq"},
    "ensembl": {"flag": "--ensembl", "name": "Ensembl"},
    "gencode": {"flag": "--gencode", "name": "GENCODE"},
    "ucsc": {"flag": "--ucsc", "name": "UCSC"},
    "ccds": {"flag": "--ccds", "name": "CCDS"},
}


class AnnotationRequest(BaseModel):
    """变异注释请求模型"""
    variant: str = Field(..., description="变异描述")
    refversion: str = Field(default="hg38", description="参考基因组版本")
    mode: str = Field(default="panno", description="注释模式")
    databases: List[str] = Field(default=["refseq"], description="数据库")


class AnnotationResponse(BaseModel):
    """变异注释响应模型"""
    success: bool
    input: str
    refversion: str
    mode: str
    databases: List[str] = []
    results: List[Dict[str, Any]] = []
    error: Optional[str] = None


class BatchAnnotationRequest(BaseModel):
    """批量注释请求模型"""
    variants: List[str] = Field(..., description="变异列表")
    refversion: str = Field(default="hg38", description="参考基因组版本")
    mode: str = Field(default="panno", description="注释模式")
    databases: List[str] = Field(default=["refseq"], description="数据库")


def run_transvar(variant: str, mode: str, refversion: str, database: str) -> Dict[str, Any]:
    """执行 TransVar 命令"""
    logger.info(f"处理: {variant}, {mode}, {refversion}, {database}")

    valid_modes = ["panno", "canno", "ganno", "codonsearch"]
    if mode not in valid_modes:
        return {"success": False, "error": f"无效的模式: {mode}"}

    if refversion not in ["hg38", "hg19"]:
        return {"success": False, "error": f"无效的版本: {refversion}"}

    if database not in SUPPORTED_DATABASES:
        return {"success": False, "error": f"无效的数据库: {database}"}

    db_flag = SUPPORTED_DATABASES[database]["flag"]
    cmd = ["transvar", mode, "-i", variant, db_flag, "--refversion", refversion, "-o", "/dev/stdout"]

    try:
        env = {**os.environ, "HOME": os.path.expanduser("~")}
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env, cwd="/app")
        output = result.stdout
        output_lines = output.strip().split('\n') if output.strip() else []
        has_data = len(output_lines) > 1

        if result.returncode == 0 and output.strip():
            return {"success": True, "database": database, "result": output.strip(), "has_data": has_data}
        elif output.strip():
            return {"success": True, "database": database, "result": output.strip(), "has_data": has_data}
        else:
            return {"success": False, "database": database, "error": "未找到结果"}

    except subprocess.TimeoutExpired:
        return {"success": False, "database": database, "error": "执行超时"}
    except Exception as e:
        return {"success": False, "database": database, "error": str(e)}


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
        :root {
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --bg: #f8fafc;
            --card: #ffffff;
            --text: #1e293b;
            --text-light: #64748b;
            --border: #e2e8f0;
            --success: #10b981;
            --error: #ef4444;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); min-height: 100vh; padding: 20px; color: var(--text); }
        .container { max-width: 800px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 32px; padding: 40px 20px; background: linear-gradient(135deg, var(--primary) 0%, #8b5cf6 100%); border-radius: 20px; color: white; }
        .header h1 { font-size: 2rem; font-weight: 700; margin-bottom: 8px; }
        .header p { opacity: 0.9; font-size: 1rem; }
        .card { background: var(--card); border-radius: 16px; padding: 28px; box-shadow: 0 4px 24px rgba(0,0,0,0.06); margin-bottom: 20px; }
        .form-section { margin-bottom: 24px; }
        .form-label { font-size: 0.875rem; font-weight: 600; color: var(--text); margin-bottom: 10px; display: block; }
        .form-input { width: 100%; padding: 14px 16px; border: 2px solid var(--border); border-radius: 12px; font-size: 16px; transition: all 0.2s; background: var(--bg); }
        .form-input:focus { outline: none; border-color: var(--primary); background: white; }
        .radio-group { display: flex; gap: 10px; flex-wrap: wrap; }
        .radio-item { flex: 1; min-width: 80px; }
        .radio-item input { display: none; }
        .radio-item label { display: flex; align-items: center; justify-content: center; padding: 12px 16px; border: 2px solid var(--border); border-radius: 10px; cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.2s; background: var(--bg); text-align: center; }
        .radio-item input:checked + label { border-color: var(--primary); background: linear-gradient(135deg, var(--primary) 0%, #8b5cf6 100%); color: white; }
        .radio-item label:hover { border-color: var(--primary); }
        .checkbox-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 10px; }
        .checkbox-item { position: relative; }
        .checkbox-item input { display: none; }
        .checkbox-item label { display: flex; align-items: center; justify-content: center; padding: 10px 12px; border: 2px solid var(--border); border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.2s; background: var(--bg); }
        .checkbox-item input:checked + label { border-color: var(--primary); background: #eef2ff; color: var(--primary); }
        .checkbox-item label:hover { border-color: var(--primary); }
        .btn { width: 100%; padding: 16px; background: linear-gradient(135deg, var(--primary) 0%, #8b5cf6 100%); color: white; border: none; border-radius: 12px; font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.2s; margin-top: 8px; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(99, 102, 241, 0.3); }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .examples { margin-top: 20px; padding-top: 20px; border-top: 1px solid var(--border); }
        .examples-title { font-size: 0.875rem; color: var(--text-light); margin-bottom: 12px; }
        .example-tags { display: flex; flex-wrap: wrap; gap: 8px; }
        .example-tag { padding: 6px 14px; background: var(--bg); border: 1px solid var(--border); border-radius: 20px; font-size: 13px; cursor: pointer; transition: all 0.2s; }
        .example-tag:hover { border-color: var(--primary); color: var(--primary); }
        .result { margin-top: 20px; border-radius: 12px; overflow: hidden; display: none; }
        .result.show { display: block; }
        .result.success { border: 1px solid #bbf7d0; }
        .result.error { border: 1px solid #fecaca; }
        .result-header { padding: 12px 16px; font-weight: 600; font-size: 14px; }
        .result.success .result-header { background: #d1fae5; color: #065f46; }
        .result.error .result-header { background: #fee2e2; color: #991b1b; }
        .result-body { background: #f8fafc; padding: 16px; font-family: 'SF Mono', 'Monaco', 'Consolas', monospace; font-size: 13px; white-space: pre-wrap; word-break: break-all; max-height: 500px; overflow-y: auto; }
        .db-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; margin-right: 6px; }
        .db-refseq { background: #dbeafe; color: #1d4ed8; }
        .db-ensembl { background: #dcfce7; color: #15803d; }
        .db-gencode { background: #fce7f3; color: #be185d; }
        .db-ucsc { background: #f3e8ff; color: #7e22ce; }
        .db-ccds { background: #fef3c7; color: #b45309; }
        .divider { height: 1px; background: var(--border); margin: 20px 0; }
        .tabs { display: flex; gap: 4px; margin-bottom: 24px; background: var(--bg); padding: 4px; border-radius: 12px; }
        .tab { flex: 1; padding: 12px; text-align: center; cursor: pointer; border-radius: 8px; font-size: 14px; font-weight: 500; color: var(--text-light); transition: all 0.2s; }
        .tab.active { background: white; color: var(--primary); box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        .tab:hover:not(.active) { color: var(--text); }
        .loading-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(255,255,255,0.9); z-index: 1000; align-items: center; justify-content: center; flex-direction: column; }
        .loading-overlay.show { display: flex; }
        .spinner { width: 48px; height: 48px; border: 4px solid var(--border); border-top-color: var(--primary); border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading-text { margin-top: 16px; color: var(--text-light); }
        textarea.batch-input { min-height: 180px; resize: vertical; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>TransVar HGVS 注释工具</h1>
            <p>支持 RefSeq、Ensembl、GENCODE、UCSC、CCDS 多数据库注释</p>
        </div>
        <div class="card">
            <div class="tabs">
                <div class="tab active" onclick="switchTab('single')">单个注释</div>
                <div class="tab" onclick="switchTab('batch')">批量注释</div>
            </div>

            <div id="single-form">
                <div class="form-section">
                    <label class="form-label">变异描述 (HGVS)</label>
                    <input type="text" class="form-input" id="variant" placeholder="PIK3CA:p.E545K 或 NM_006218.4:c.1633G>A">
                </div>

                <div class="form-section">
                    <label class="form-label">参考基因组版本</label>
                    <div class="radio-group">
                        <div class="radio-item"><input type="radio" name="refversion" id="rv-hg38" value="hg38" checked><label for="rv-hg38">hg38 (GRCh38)</label></div>
                        <div class="radio-item"><input type="radio" name="refversion" id="rv-hg19" value="hg19"><label for="rv-hg19">hg19 (GRCh37)</label></div>
                    </div>
                </div>

                <div class="form-section">
                    <label class="form-label">注释模式</label>
                    <div class="radio-group">
                        <div class="radio-item"><input type="radio" name="mode" id="mode-panno" value="panno" checked><label for="mode-panno">蛋白 (p.)</label></div>
                        <div class="radio-item"><input type="radio" name="mode" id="mode-canno" value="canno"><label for="mode-canno">cDNA (c.)</label></div>
                        <div class="radio-item"><input type="radio" name="mode" id="mode-ganno" value="ganno"><label for="mode-ganno">基因组 (g.)</label></div>
                    </div>
                </div>

                <div class="form-section">
                    <label class="form-label">数据库 (可多选)</label>
                    <div class="checkbox-grid">
                        <div class="checkbox-item"><input type="checkbox" id="db-refseq" checked><label for="db-refseq">RefSeq</label></div>
                        <div class="checkbox-item"><input type="checkbox" id="db-ensembl"><label for="db-ensembl">Ensembl</label></div>
                        <div class="checkbox-item"><input type="checkbox" id="db-gencode"><label for="db-gencode">GENCODE</label></div>
                        <div class="checkbox-item"><input type="checkbox" id="db-ucsc"><label for="db-ucsc">UCSC</label></div>
                        <div class="checkbox-item"><input type="checkbox" id="db-ccds"><label for="db-ccds">CCDS</label></div>
                    </div>
                </div>

                <button class="btn" onclick="annotate()">提交注释</button>

                <div class="examples">
                    <div class="examples-title">点击示例快速填充：</div>
                    <div class="example-tags">
                        <span class="example-tag" onclick="setVariant('PIK3CA:p.E545K')">PIK3CA:p.E545K</span>
                        <span class="example-tag" onclick="setVariant('EGFR:p.L858R')">EGFR:p.L858R</span>
                        <span class="example-tag" onclick="setVariant('TP53:p.R273H')">TP53:p.R273H</span>
                        <span class="example-tag" onclick="setVariant('NM_006218.4:c.1633G>A')">NM_006218.4:c.1633G>A</span>
                    </div>
                </div>
            </div>

            <div id="batch-form" style="display:none;">
                <div class="form-section">
                    <label class="form-label">批量变异 (每行一个)</label>
                    <textarea class="form-input batch-input" id="batch-variants" placeholder="PIK3CA:p.E545K&#10;EGFR:p.L858R&#10;TP53:p.R273H"></textarea>
                </div>

                <div class="form-section">
                    <label class="form-label">参考基因组版本</label>
                    <div class="radio-group">
                        <div class="radio-item"><input type="radio" name="batch-refversion" id="batch-rv-hg38" value="hg38" checked><label for="batch-rv-hg38">hg38</label></div>
                        <div class="radio-item"><input type="radio" name="batch-refversion" id="batch-rv-hg19" value="hg19"><label for="batch-rv-hg19">hg19</label></div>
                    </div>
                </div>

                <div class="form-section">
                    <label class="form-label">注释模式</label>
                    <div class="radio-group">
                        <div class="radio-item"><input type="radio" name="batch-mode" id="batch-mode-panno" value="panno" checked><label for="batch-mode-panno">蛋白 (p.)</label></div>
                        <div class="radio-item"><input type="radio" name="batch-mode" id="batch-mode-canno" value="canno"><label for="batch-mode-canno">cDNA (c.)</label></div>
                        <div class="radio-item"><input type="radio" name="batch-mode" id="batch-mode-ganno" value="ganno"><label for="batch-mode-ganno">基因组 (g.)</label></div>
                    </div>
                </div>

                <div class="form-section">
                    <label class="form-label">数据库</label>
                    <div class="checkbox-grid">
                        <div class="checkbox-item"><input type="checkbox" id="batch-db-refseq" checked><label for="batch-db-refseq">RefSeq</label></div>
                        <div class="checkbox-item"><input type="checkbox" id="batch-db-ensembl"><label for="batch-db-ensembl">Ensembl</label></div>
                        <div class="checkbox-item"><input type="checkbox" id="batch-db-gencode"><label for="batch-db-gencode">GENCODE</label></div>
                        <div class="checkbox-item"><input type="checkbox" id="batch-db-ucsc"><label for="batch-db-ucsc">UCSC</label></div>
                        <div class="checkbox-item"><input type="checkbox" id="batch-db-ccds"><label for="batch-db-ccds">CCDS</label></div>
                    </div>
                </div>

                <button class="btn" onclick="batchAnnotate()">批量提交</button>
            </div>

            <div id="result" class="result"></div>
        </div>
    </div>

    <div id="loading" class="loading-overlay">
        <div class="spinner"></div>
        <div class="loading-text">正在注释...</div>
    </div>

    <script>
        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab')[tab === 'single' ? 0 : 1].classList.add('active');
            document.getElementById('single-form').style.display = tab === 'single' ? 'block' : 'none';
            document.getElementById('batch-form').style.display = tab === 'batch' ? 'block' : 'none';
            document.getElementById('result').style.display = 'none';
        }

        function setVariant(v) { document.getElementById('variant').value = v; }

        function getRadioValue(name) {
            const el = document.querySelector('input[name="' + name + '"]:checked');
            return el ? el.value : 'hg38';
        }

        function getDatabases(prefix) {
            const p = prefix ? prefix + '-' : '';
            const dbs = [];
            ['refseq', 'ensembl', 'gencode', 'ucsc', 'ccds'].forEach(db => {
                if (document.getElementById(p + 'db-' + db)?.checked) dbs.push(db);
            });
            return dbs.length > 0 ? dbs : ['refseq'];
        }

        function showResult(success, content) {
            const r = document.getElementById('result');
            r.className = 'result show ' + (success ? 'success' : 'error');
            r.innerHTML = '<div class="result-header">' + (success ? '注释结果' : '错误') + '</div><div class="result-body">' + content + '</div>';
        }

        function getDbBadge(db) {
            const names = {refseq: 'RefSeq', ensembl: 'Ensembl', gencode: 'GENCODE', ucsc: 'UCSC', ccds: 'CCDS'};
            return '<span class="db-badge db-' + db + '">' + names[db] + '</span>';
        }

        async function annotate() {
            const variant = document.getElementById('variant').value.trim();
            if (!variant) { showResult(false, '请输入变异描述'); return; }

            document.getElementById('loading').classList.add('show');
            document.getElementById('result').style.display = 'none';

            try {
                const res = await fetch('/api/annotate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        variant,
                        refversion: getRadioValue('refversion'),
                        mode: getRadioValue('mode'),
                        databases: getDatabases()
                    })
                });
                const data = await res.json();

                if (data.results && data.results.length > 0) {
                    let out = '';
                    for (let i = 0; i < data.results.length; i++) {
                        const r = data.results[i];
                        out += getDbBadge(r.database) + '\\n';
                        if (r.success) {
                            out += r.result || '无输出';
                        } else {
                            out += '错误: ' + (r.error || '注释失败');
                        }
                        out += '\\n\\n';
                    }
                    showResult(true, out);
                } else {
                    showResult(false, data.error || '注释失败');
                }
            } catch (e) {
                showResult(false, '请求失败: ' + e.message);
            } finally {
                document.getElementById('loading').classList.remove('show');
            }
        }

        async function batchAnnotate() {
            const variants = document.getElementById('batch-variants').value.trim().split('\\n').filter(v => v.trim());
            if (!variants.length) { showResult(false, '请输入变异列表'); return; }

            document.getElementById('loading').classList.add('show');
            document.getElementById('result').style.display = 'none';

            try {
                const res = await fetch('/api/batch_annotate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        variants,
                        refversion: getRadioValue('batch-refversion'),
                        mode: getRadioValue('batch-mode'),
                        databases: getDatabases('batch')
                    })
                });
                const data = await res.json();

                let out = '';
                for (let i = 0; i < data.results.length; i++) {
                    const r = data.results[i];
                    out += '【' + r.input + '】\\n';
                    if (r.results && r.results.length > 0) {
                        for (let j = 0; j < r.results.length; j++) {
                            const sr = r.results[j];
                            out += getDbBadge(sr.database) + ' ';
                            if (sr.success) {
                                out += sr.result || '无输出';
                            } else {
                                out += '错误: ' + (sr.error || '失败');
                            }
                            out += '\\n';
                        }
                    }
                    out += '───\\n';
                }
                showResult(true, out);
            } catch (e) {
                showResult(false, '请求失败: ' + e.message);
            } finally {
                document.getElementById('loading').classList.remove('show');
            }
        }
    </script>
</body>
</html>
    """


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/annotate", response_model=AnnotationResponse)
async def annotate(request: AnnotationRequest):
    databases = request.databases if request.databases else ["refseq"]
    results = [run_transvar(request.variant, request.mode, request.refversion, db) for db in databases]
    success = any(r.get("success") and r.get("has_data") for r in results)
    return AnnotationResponse(
        success=success,
        input=request.variant,
        refversion=request.refversion,
        mode=request.mode,
        databases=databases,
        results=results,
        error=None if success else "未找到匹配数据"
    )


@app.post("/api/batch_annotate")
async def batch_annotate(request: BatchAnnotationRequest):
    databases = request.databases if request.databases else ["refseq"]
    results = []
    for variant in request.variants:
        variant_results = [run_transvar(variant.strip(), request.mode, request.refversion, db) for db in databases]
        results.append({
            "input": variant,
            "success": any(r.get("success") and r.get("has_data") for r in variant_results),
            "results": variant_results
        })
    return {"success": True, "total": len(results), "results": results}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)