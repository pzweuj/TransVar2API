#!/bin/bash
# HF Space 启动脚本 - 初始化 transvar 数据库并启动服务

echo "=========================================="
echo "TransVar API - HF Space Startup"
echo "=========================================="

# hg38 setup
echo "[1/4] Setting up hg38..."
echo "  - Building transvar index from GTF..."
transvar index --refseq /data/transvar_db/refseq_hg38/hg38.ncbiRefSeq.gtf.gz

echo "  - Configuring hg38..."
transvar config -k reference -v /data/transvar_db/refseq_hg38/hg38.fa --refversion hg38_refseq
transvar config -k refseq -v /data/transvar_db/refseq_hg38/hg38.ncbiRefSeq.gtf.gz --refversion hg38_refseq

# hg19 setup
echo "[2/4] Setting up hg19..."
echo "  - Building transvar index from GTF..."
transvar index --refseq /data/transvar_db/refseq_hg19/hg19.ncbiRefSeq.gtf.gz

echo "  - Configuring hg19..."
transvar config -k reference -v /data/transvar_db/refseq_hg19/hg19.fa --refversion hg19_refseq
transvar config -k refseq -v /data/transvar_db/refseq_hg19/hg19.ncbiRefSeq.gtf.gz --refversion hg19_refseq

# Verify setup
echo "[3/4] Verifying databases..."
transvar version

# Start server
echo "[4/4] Starting server on port $PORT..."
echo "=========================================="

exec python3 -c "import os; import uvicorn; from server import app; uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 7860)))"