# TransVar API for HuggingFace Spaces
# 使用 transvar 官方数据库

FROM python:3.9-slim

# 环境变量
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PORT=7860

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

# 从 GitHub 克隆仓库
WORKDIR /app
RUN git clone https://github.com/pzweuj/TransVar2API.git .

# 安装 Python 依赖和 transvar
RUN pip3 install --no-cache-dir -r requirements.txt
RUN pip3 install --no-cache-dir transvar

# ========== 创建数据目录 ==========
RUN mkdir -p /data/hg38 /data/hg19

# ========== 下载参考基因组 ==========
# hg38
WORKDIR /data/hg38
RUN echo "Downloading hg38 reference genome..." && \
    wget -q -O hg38.fa.gz https://hgdownload.soe.ucsc.edu/goldenPath/hg38/bigZips/hg38.fa.gz && \
    gunzip hg38.fa.gz && \
    samtools faidx hg38.fa

# hg19
WORKDIR /data/hg19
RUN echo "Downloading hg19 reference genome..." && \
    wget -q -O hg19.fa.gz https://hgdownload.soe.ucsc.edu/goldenPath/hg19/bigZips/hg19.fa.gz && \
    gunzip hg19.fa.gz && \
    samtools faidx hg19.fa

# ========== 配置 transvar reference ==========
RUN echo "Configuring hg38 reference..." && \
    transvar config -k reference -v /data/hg38/hg38.fa --refversion hg38

RUN echo "Configuring hg19 reference..." && \
    transvar config -k reference -v /data/hg19/hg19.fa --refversion hg19

# ========== 下载注释数据库 ==========
RUN echo "Downloading hg38 annotation database..." && \
    transvar config --download_anno --refversion hg38

RUN echo "Downloading hg19 annotation database..." && \
    transvar config --download_anno --refversion hg19

# 验证数据库
RUN echo "Verifying databases..." && \
    echo "hg38 config:" && transvar config --refversion hg38 && \
    echo "hg19 config:" && transvar config --refversion hg19

# 测试 transvar
RUN echo "Testing transvar..." && \
    transvar panno -i "PIK3CA:p.E545K" --refseq --refversion hg38 -o /dev/stdout

WORKDIR /app
RUN chmod +x /app/scripts/hf_startup.sh

EXPOSE 7860

CMD ["/app/scripts/hf_startup.sh"]