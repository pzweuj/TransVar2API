FROM ubuntu:22.04

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive \
    TRANSVAR_DB_PATH=/data/transvar_db

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    curl \
    samtools \
    build-essential \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-gnutls-dev \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /usr/bin/python

# 安装 Python 依赖
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# 安装 transvar
RUN pip3 install --no-cache-dir transvar

# 创建工作目录
WORKDIR /app

# 复制脚本和配置文件
COPY server.py /app/
COPY scripts/ /app/scripts/

# 创建数据目录
RUN mkdir -p /data/transvar_db/refseq_hg38 /data/transvar_db/refseq_hg19

# ========== 构建 hg38 数据库 ==========
WORKDIR /data/transvar_db/refseq_hg38

# 下载 hg38 参考基因组
RUN echo "Downloading hg38 reference genome..." && \
    wget -q -O hg38.fa.gz https://hgdownload.soe.ucsc.edu/goldenPath/hg38/bigZips/hg38.fa.gz && \
    gunzip -f hg38.fa.gz && \
    samtools faidx hg38.fa

# 下载 hg38 RefSeq 注释并构建索引
RUN echo "Building hg38 transvar index..." && \
    wget -q -O ncbiRefSeq.txt.gz https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/ncbiRefSeq.txt.gz && \
    transvar index --refseq ncbiRefSeq.txt.gz && \
    transvar config -k reference -v /data/transvar_db/refseq_hg38/hg38.fa --refversion hg38_refseq && \
    transvar config -k refseq -v /data/transvar_db/refseq_hg38/ncbiRefSeq.txt.gz --refversion hg38_refseq

# ========== 构建 hg19 数据库 ==========
WORKDIR /data/transvar_db/refseq_hg19

# 下载 hg19 参考基因组
RUN echo "Downloading hg19 reference genome..." && \
    wget -q -O hg19.fa.gz https://hgdownload.soe.ucsc.edu/goldenPath/hg19/bigZips/hg19.fa.gz && \
    gunzip -f hg19.fa.gz && \
    samtools faidx hg19.fa

# 下载 hg19 RefSeq 注释并构建索引
RUN echo "Building hg19 transvar index..." && \
    wget -q -O ncbiRefSeq.txt.gz https://hgdownload.soe.ucsc.edu/goldenPath/hg19/database/ncbiRefSeq.txt.gz && \
    transvar index --refseq ncbiRefSeq.txt.gz && \
    transvar config -k reference -v /data/transvar_db/refseq_hg19/hg19.fa --refversion hg19_refseq && \
    transvar config -k refseq -v /data/transvar_db/refseq_hg19/ncbiRefSeq.txt.gz --refversion hg19_refseq

# 返回工作目录
WORKDIR /app

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 默认命令
CMD ["python3", "server.py"]