#!/bin/bash
# TransVar 数据库构建脚本 - hg38 (GRCh38)
# 使用 UCSC RefSeq 数据构建

set -e

# 配置
DB_PATH="${TRANSVAR_DB_PATH:-/data/transvar_db}"
HG38_PATH="$DB_PATH/refseq_hg38"
LOG_FILE="$DB_PATH/build_hg38.log"

echo "========================================"
echo "TransVar hg38 数据库构建"
echo "========================================"

# 创建目录
mkdir -p "$HG38_PATH"
cd "$HG38_PATH"

echo "[$(date)] 开始下载 hg38 参考基因组..." | tee -a "$LOG_FILE"

# 下载 hg38 参考基因组
if [ ! -f "hg38.fa" ]; then
    wget -q --show-progress -O hg38.fa.gz https://hgdownload.soe.ucsc.edu/goldenPath/hg38/bigZips/hg38.fa.gz
    gunzip -f hg38.fa.gz
    echo "[$(date)] hg38 参考基因组下载完成" | tee -a "$LOG_FILE"
else
    echo "[$(date)] hg38 参考基因组已存在，跳过下载" | tee -a "$LOG_FILE"
fi

# 建立索引
if [ ! -f "hg38.fa.fai" ]; then
    echo "[$(date)] 建立 samtools 索引..." | tee -a "$LOG_FILE"
    samtools faidx hg38.fa
    echo "[$(date)] 索引建立完成" | tee -a "$LOG_FILE"
fi

echo "[$(date)] 下载 RefSeq 注释文件..." | tee -a "$LOG_FILE"

# 下载 UCSC RefSeq 注释
if [ ! -f "ncbiRefSeq.txt.gz" ]; then
    wget -q --show-progress -O ncbiRefSeq.txt.gz https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/ncbiRefSeq.txt.gz
    echo "[$(date)] RefSeq 注释下载完成" | tee -a "$LOG_FILE"
else
    echo "[$(date)] RefSeq 注释已存在，跳过下载" | tee -a "$LOG_FILE"
fi

# 构建 TransVar 索引
echo "[$(date)] 构建 TransVar 索引..." | tee -a "$LOG_FILE"
transvar index --refseq ncbiRefSeq.txt.gz 2>&1 | tee -a "$LOG_FILE"

# 注册数据库
echo "[$(date)] 注册 hg38_refseq 数据库..." | tee -a "$LOG_FILE"
transvar config -k reference -v "$HG38_PATH/hg38.fa" --refversion hg38_refseq 2>&1 | tee -a "$LOG_FILE"
transvar config -k refseq -v "$HG38_PATH/ncbiRefSeq.txt.gz" --refversion hg38_refseq 2>&1 | tee -a "$LOG_FILE"

echo "[$(date)] hg38 数据库构建完成!" | tee -a "$LOG_FILE"

# 验证安装
echo "[$(date)] 验证安装..." | tee -a "$LOG_FILE"
transvar panno -i 'PIK3CA:p.E545K' --refseq --refversion hg38_refseq 2>&1 | tee -a "$LOG_FILE" || true

echo "========================================"
echo "hg38 数据库构建完成!"
echo "数据库路径: $HG38_PATH"
echo "========================================"