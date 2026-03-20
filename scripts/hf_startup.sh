#!/bin/bash
# HF Space 启动脚本 - 初始化 transvar 数据库并启动服务

echo "=========================================="
echo "TransVar API - HF Space Startup"
echo "=========================================="

# 设置数据库路径
export TRANSVAR_DB_PATH=/data/transvar_db

# ========== UCSC hg38 ==========
echo "[1/6] Setting up UCSC hg38..."
cd /data/transvar_db/ucsc_hg38
echo "  - Building transvar index with --ucsc..."
transvar index --ucsc /data/transvar_db/ucsc_hg38/ncbiRefSeq.txt.gz
if [ -f ncbiRefSeq.txt.gz.transvardb.gene_idx ] && [ ! -f ncbiRefSeq.txt.gz.gene_idx ]; then
    ln -sf ncbiRefSeq.txt.gz.transvardb.gene_idx ncbiRefSeq.txt.gz.gene_idx
    ln -sf ncbiRefSeq.txt.gz.transvardb.trxn_idx ncbiRefSeq.txt.gz.trxn_idx
fi
echo "  - Configuring hg38_refseq..."
transvar config -k reference -v /data/transvar_db/ucsc_hg38/hg38.fa --refversion hg38_refseq
transvar config -k ucsc -v /data/transvar_db/ucsc_hg38/ncbiRefSeq.txt.gz --refversion hg38_refseq

# ========== UCSC hg19 ==========
echo "[2/6] Setting up UCSC hg19..."
cd /data/transvar_db/ucsc_hg19
echo "  - Building transvar index with --ucsc..."
transvar index --ucsc /data/transvar_db/ucsc_hg19/ncbiRefSeq.txt.gz
if [ -f ncbiRefSeq.txt.gz.transvardb.gene_idx ] && [ ! -f ncbiRefSeq.txt.gz.gene_idx ]; then
    ln -sf ncbiRefSeq.txt.gz.transvardb.gene_idx ncbiRefSeq.txt.gz.gene_idx
    ln -sf ncbiRefSeq.txt.gz.transvardb.trxn_idx ncbiRefSeq.txt.gz.trxn_idx
fi
echo "  - Configuring hg19_refseq..."
transvar config -k reference -v /data/transvar_db/ucsc_hg19/hg19.fa --refversion hg19_refseq
transvar config -k ucsc -v /data/transvar_db/ucsc_hg19/ncbiRefSeq.txt.gz --refversion hg19_refseq

# ========== NCBI RefSeq hg38 ==========
echo "[3/6] Setting up NCBI RefSeq hg38..."
cd /data/transvar_db/ncbi_refseq_hg38
echo "  - Building transvar index with --refseq..."
transvar index --refseq /data/transvar_db/ncbi_refseq_hg38/hg38_refseq.gff.gz
if [ -f hg38_refseq.gff.gz.transvardb.gene_idx ] && [ ! -f hg38_refseq.gff.gz.gene_idx ]; then
    ln -sf hg38_refseq.gff.gz.transvardb.gene_idx hg38_refseq.gff.gz.gene_idx
    ln -sf hg38_refseq.gff.gz.transvardb.trxn_idx hg38_refseq.gff.gz.trxn_idx
fi
echo "  - Configuring ncbi_refseq_hg38..."
transvar config -k reference -v /data/transvar_db/ncbi_refseq_hg38/hg38.fa --refversion hg38_ncbi_refseq
transvar config -k refseq -v /data/transvar_db/ncbi_refseq_hg38/hg38_refseq.gff.gz --refversion hg38_ncbi_refseq

# ========== NCBI RefSeq hg19 ==========
echo "[4/6] Setting up NCBI RefSeq hg19..."
cd /data/transvar_db/ncbi_refseq_hg19
echo "  - Building transvar index with --refseq..."
transvar index --refseq /data/transvar_db/ncbi_refseq_hg19/hg19_refseq.gff.gz
if [ -f hg19_refseq.gff.gz.transvardb.gene_idx ] && [ ! -f hg19_refseq.gff.gz.gene_idx ]; then
    ln -sf hg19_refseq.gff.gz.transvardb.gene_idx hg19_refseq.gff.gz.gene_idx
    ln -sf hg19_refseq.gff.gz.transvardb.trxn_idx hg19_refseq.gff.gz.trxn_idx
fi
echo "  - Configuring ncbi_refseq_hg19..."
transvar config -k reference -v /data/transvar_db/ncbi_refseq_hg19/hg19.fa --refversion hg19_ncbi_refseq
transvar config -k refseq -v /data/transvar_db/ncbi_refseq_hg19/hg19_refseq.gff.gz --refversion hg19_ncbi_refseq

# Verify setup
echo "[5/6] Checking index files..."
ls -la /data/transvar_db/ucsc_hg38/*.idx* 2>/dev/null | head -5

# Start server
echo "[6/6] Starting server on port $PORT..."
echo "=========================================="

cd /app
exec python3 -c "import os; import uvicorn; from server import app; uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 7860)), log_level='info')"