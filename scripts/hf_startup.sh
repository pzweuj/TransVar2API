#!/bin/bash
# HF Space 启动脚本 - 初始化 transvar 数据库并启动服务

echo "=========================================="
echo "TransVar API - HF Space Startup"
echo "=========================================="

# hg38 setup
echo "[1/4] Setting up hg38..."
echo "  - Building transvar index with --ucsc..."
transvar index --ucsc /data/transvar_db/refseq_hg38/ncbiRefSeq.txt.gz

echo "  - Configuring hg38..."
transvar config -k reference -v /data/transvar_db/refseq_hg38/hg38.fa --refversion hg38_refseq
transvar config -k ucsc -v /data/transvar_db/refseq_hg38/ncbiRefSeq.txt.gz --refversion hg38_refseq

# hg19 setup
echo "[2/4] Setting up hg19..."
echo "  - Building transvar index with --ucsc..."
transvar index --ucsc /data/transvar_db/refseq_hg19/ncbiRefSeq.txt.gz

echo "  - Configuring hg19..."
transvar config -k reference -v /data/transvar_db/refseq_hg19/hg19.fa --refversion hg19_refseq
transvar config -k ucsc -v /data/transvar_db/refseq_hg19/ncbiRefSeq.txt.gz --refversion hg19_refseq

# Verify setup - 移除不存在的 version 命令
echo "[3/4] Database setup complete"

# Start server
echo "[4/4] Starting server on port $PORT..."
echo "=========================================="

exec python3 -c "import os; import uvicorn; from server import app; uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 7860)))"