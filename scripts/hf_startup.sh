#!/bin/bash
# HF Space 启动脚本 - 初始化 transvar 数据库并启动服务

echo "=========================================="
echo "TransVar API - HF Space Startup"
echo "=========================================="

# 设置数据库路径
export TRANSVAR_DB_PATH=/data/transvar_db

# hg38 setup
echo "[1/4] Setting up hg38..."
cd /data/transvar_db/refseq_hg38

echo "  - Building transvar index with --ucsc..."
transvar index --ucsc /data/transvar_db/refseq_hg38/ncbiRefSeq.txt.gz

# 修复索引文件名 bug：创建符号链接
if [ -f ncbiRefSeq.txt.gz.transvardb.gene_idx ] && [ ! -f ncbiRefSeq.txt.gz.gene_idx ]; then
    ln -s ncbiRefSeq.txt.gz.transvardb.gene_idx ncbiRefSeq.txt.gz.gene_idx
fi
if [ -f ncbiRefSeq.txt.gz.transvardb.trxn_idx ] && [ ! -f ncbiRefSeq.txt.gz.trxn_idx ]; then
    ln -s ncbiRefSeq.txt.gz.transvardb.trxn_idx ncbiRefSeq.txt.gz.trxn_idx
fi

echo "  - Configuring hg38..."
transvar config -k reference -v /data/transvar_db/refseq_hg38/hg38.fa --refversion hg38_refseq
transvar config -k ucsc -v /data/transvar_db/refseq_hg38/ncbiRefSeq.txt.gz --refversion hg38_refseq

# hg19 setup
echo "[2/4] Setting up hg19..."
cd /data/transvar_db/refseq_hg19
echo "  - Building transvar index with --ucsc..."
transvar index --ucsc /data/transvar_db/refseq_hg19/ncbiRefSeq.txt.gz

# 修复索引文件名 bug：创建符号链接
if [ -f ncbiRefSeq.txt.gz.transvardb.gene_idx ] && [ ! -f ncbiRefSeq.txt.gz.gene_idx ]; then
    ln -s ncbiRefSeq.txt.gz.transvardb.gene_idx ncbiRefSeq.txt.gz.gene_idx
fi
if [ -f ncbiRefSeq.txt.gz.transvardb.trxn_idx ] && [ ! -f ncbiRefSeq.txt.gz.trxn_idx ]; then
    ln -s ncbiRefSeq.txt.gz.transvardb.trxn_idx ncbiRefSeq.txt.gz.trxn_idx
fi

echo "  - Configuring hg19..."
transvar config -k reference -v /data/transvar_db/refseq_hg19/hg19.fa --refversion hg19_refseq
transvar config -k ucsc -v /data/transvar_db/refseq_hg19/ncbiRefSeq.txt.gz --refversion hg19_refseq

# Verify setup
echo "[3/4] Checking index files..."
ls -la /data/transvar_db/refseq_hg38/*.idx* 2>/dev/null || echo "No index files in hg38"
ls -la /data/transvar_db/refseq_hg19/*.idx* 2>/dev/null || echo "No index files in hg19"

# Start server
echo "[4/4] Starting server on port $PORT..."
echo "=========================================="

cd /app
exec python3 -c "import os; import uvicorn; from server import app; uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 7860)))"