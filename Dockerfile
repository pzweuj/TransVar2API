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

# 修补 transvar 的 localdb.py 以修复 KeyError: 'product' 错误
RUN python3 /app/scripts/patch_transvar.py

# ========== 下载 transvar 官方数据库 ==========
# hg38 - 下载注释数据库和参考基因组
RUN echo "Downloading hg38 annotation database..." && \
    transvar config --download_anno --refversion hg38

RUN echo "Downloading hg38 reference genome..." && \
    transvar config --download_ref --refversion hg38

# hg19 - 下载注释数据库和参考基因组
RUN echo "Downloading hg19 annotation database..." && \
    transvar config --download_anno --refversion hg19

RUN echo "Downloading hg19 reference genome..." && \
    transvar config --download_ref --refversion hg19

# 验证数据库
RUN echo "Verifying databases..." && \
    echo "hg38 config:" && transvar config --refversion hg38 && \
    echo "hg19 config:" && transvar config --refversion hg19

# 测试 transvar
RUN echo "Testing transvar..." && \
    transvar panno -i "PIK3CA:p.E545K" --refversion hg38 -o /dev/stdout

# 设置启动脚本权限
RUN chmod +x /app/scripts/hf_startup.sh

EXPOSE 7860

CMD ["/app/scripts/hf_startup.sh"]