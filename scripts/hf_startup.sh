#!/bin/bash
# HF Space 启动脚本 - 初始化 transvar 数据库并启动服务

echo "=========================================="
echo "TransVar API - HF Space Startup"
echo "=========================================="

# 设置数据库路径
export TRANSVAR_DB_PATH=/data/transvar_db

# ========== Step 1: 创建配置文件 ==========
echo "[Step 1] Creating transvar config file..."
cd /app
python3 /app/scripts/create_config.py
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create config file"
    exit 1
fi

# ========== Step 2: 创建索引文件 ==========
echo ""
echo "[Step 2] Building UCSC hg38 index..."
cd /data/transvar_db/ucsc_hg38
if [ ! -f ncbiRefSeq.txt.gz.transvardb ]; then
    echo "  - Running transvar index..."
    transvar index --ucsc /data/transvar_db/ucsc_hg38/ncbiRefSeq.txt.gz
fi
# 创建符号链接（如果需要）
if [ -f ncbiRefSeq.txt.gz.transvardb.gene_idx ] && [ ! -f ncbiRefSeq.txt.gz.gene_idx ]; then
    ln -sf ncbiRefSeq.txt.gz.transvardb.gene_idx ncbiRefSeq.txt.gz.gene_idx
    ln -sf ncbiRefSeq.txt.gz.transvardb.trxn_idx ncbiRefSeq.txt.gz.trxn_idx
fi
echo "  - Done"

echo "[Step 3] Building UCSC hg19 index..."
cd /data/transvar_db/ucsc_hg19
if [ ! -f ncbiRefSeq.txt.gz.transvardb ]; then
    echo "  - Running transvar index..."
    transvar index --ucsc /data/transvar_db/ucsc_hg19/ncbiRefSeq.txt.gz
fi
if [ -f ncbiRefSeq.txt.gz.transvardb.gene_idx ] && [ ! -f ncbiRefSeq.txt.gz.gene_idx ]; then
    ln -sf ncbiRefSeq.txt.gz.transvardb.gene_idx ncbiRefSeq.txt.gz.gene_idx
    ln -sf ncbiRefSeq.txt.gz.transvardb.trxn_idx ncbiRefSeq.txt.gz.trxn_idx
fi
echo "  - Done"

echo "[Step 4] Building NCBI RefSeq hg38 index..."
cd /data/transvar_db/ncbi_refseq_hg38
if [ ! -f hg38_refseq.gff.gz.transvardb ]; then
    echo "  - Running transvar index..."
    transvar index --refseq /data/transvar_db/ncbi_refseq_hg38/hg38_refseq.gff.gz
fi
if [ -f hg38_refseq.gff.gz.transvardb.gene_idx ] && [ ! -f hg38_refseq.gff.gz.gene_idx ]; then
    ln -sf hg38_refseq.gff.gz.transvardb.gene_idx hg38_refseq.gff.gz.gene_idx
    ln -sf hg38_refseq.gff.gz.transvardb.trxn_idx hg38_refseq.gff.gz.trxn_idx
fi
echo "  - Done"

echo "[Step 5] Building NCBI RefSeq hg19 index..."
cd /data/transvar_db/ncbi_refseq_hg19
if [ ! -f hg19_refseq.gff.gz.transvardb ]; then
    echo "  - Running transvar index..."
    transvar index --refseq /data/transvar_db/ncbi_refseq_hg19/hg19_refseq.gff.gz
fi
if [ -f hg19_refseq.gff.gz.transvardb.gene_idx ] && [ ! -f hg19_refseq.gff.gz.gene_idx ]; then
    ln -sf hg19_refseq.gff.gz.transvardb.gene_idx hg19_refseq.gff.gz.gene_idx
    ln -sf hg19_refseq.gff.gz.transvardb.trxn_idx hg19_refseq.gff.gz.trxn_idx
fi
echo "  - Done"

# 验证关键文件
echo ""
echo "[Step 6] Verifying key files..."
echo "Config file:"
cat ~/.transvar.cfg 2>/dev/null || echo "  Warning: No config file found"

echo ""
echo "Index files:"
ls -la /data/transvar_db/ucsc_hg38/*.transvardb 2>/dev/null
ls -la /data/transvar_db/ucsc_hg38/*idx* 2>/dev/null | head -5

echo ""
echo "Reference files:"
ls -la /data/transvar_db/ucsc_hg38/*.fa* 2>/dev/null | head -5

# 检查 transvar config 输出
echo ""
echo "[Step 7] Checking transvar config..."
transvar config --refversion hg38_ucsc 2>&1

# 测试 transvar 命令
echo ""
echo "[Step 8] Testing transvar annotation..."
echo "Test 1: PIK3CA:p.E545K"
transvar panno -i "PIK3CA:p.E545K" --refversion hg38_ucsc -o /dev/stdout 2>&1

echo ""
echo "Test 2: NM_006218.4:c.1633G>A"
transvar canno -i "NM_006218.4:c.1633G>A" --refversion hg38_ucsc -o /dev/stdout 2>&1

echo ""
echo "Test 3: EGFR:p.L858R"
transvar panno -i "EGFR:p.L858R" --refversion hg38_ucsc -o /dev/stdout 2>&1

# Start server
echo ""
echo "[Step 9] Starting server on port $PORT..."
echo "=========================================="

cd /app
exec python3 -c "import os; import uvicorn; from server import app; uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 7860)), log_level='info')"