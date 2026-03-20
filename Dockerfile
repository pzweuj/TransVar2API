# TransVar API Docker Image
# 仓库: https://github.com/pzweuj/TransVar2API

FROM python:3.9-slim

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive \
    TRANSVAR_DB_PATH=/data/transvar_db \
    PYTHONUNBUFFERED=1

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    git \
    samtools \
    tabix \
    build-essential \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-gnutls-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
WORKDIR /app
COPY requirements.txt /app/
COPY server.py /app/
COPY scripts/ /app/scripts/

# 安装 Python 依赖和 transvar
RUN pip3 install --no-cache-dir -r requirements.txt
RUN pip3 install --no-cache-dir transvar

# 修补 transvar 的 localdb.py 以修复 KeyError: 'product' 错误
RUN python3 /app/scripts/patch_transvar.py

# 创建数据目录
RUN mkdir -p /data/transvar_db/ucsc_hg38 /data/transvar_db/ucsc_hg19 \
             /data/transvar_db/ncbi_refseq_hg38 /data/transvar_db/ncbi_refseq_hg19

# ========== UCSC 数据库 ==========
WORKDIR /data/transvar_db/ucsc_hg38
RUN wget -q -O hg38.fa.gz https://hgdownload.soe.ucsc.edu/goldenPath/hg38/bigZips/hg38.fa.gz && \
    gunzip -f hg38.fa.gz && \
    samtools faidx hg38.fa
RUN wget -q -O ncbiRefSeq.txt.gz https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/ncbiRefSeq.txt.gz

WORKDIR /data/transvar_db/ucsc_hg19
RUN wget -q -O hg19.fa.gz https://hgdownload.soe.ucsc.edu/goldenPath/hg19/bigZips/hg19.fa.gz && \
    gunzip -f hg19.fa.gz && \
    samtools faidx hg19.fa
RUN wget -q -O ncbiRefSeq.txt.gz https://hgdownload.soe.ucsc.edu/goldenPath/hg19/database/ncbiRefSeq.txt.gz

# ========== NCBI RefSeq 数据库 (软链接 UCSC 的参考基因组) ==========
WORKDIR /data/transvar_db/ncbi_refseq_hg38
RUN ln -sf ../ucsc_hg38/hg38.fa ./hg38.fa && \
    samtools faidx hg38.fa
RUN wget -q -O hg38_refseq.gff.gz https://ftp.ncbi.nlm.nih.gov/refseq/H_sapiens/annotation/GRCh38_latest/refseq_identifiers/GRCh38_latest_genomic.gff.gz

WORKDIR /data/transvar_db/ncbi_refseq_hg19
RUN ln -sf ../ucsc_hg19/hg19.fa ./hg19.fa && \
    samtools faidx hg19.fa
RUN wget -q -O hg19_refseq.gff.gz https://ftp.ncbi.nlm.nih.gov/refseq/H_sapiens/annotation/GRCh37_latest/refseq_identifiers/GRCh37_latest_genomic.gff.gz

# 返回工作目录
WORKDIR /app

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 默认命令
CMD ["python3", "server.py"]