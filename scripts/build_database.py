#!/usr/bin/env python3
"""
TransVar 数据库构建脚本
在 Docker 容器内构建 hg38 和 hg19 RefSeq 数据库
"""

import os
import sys
import subprocess
import urllib.request
import gzip
import shutil
from pathlib import Path

# 配置
DB_PATH = os.getenv("TRANSVAR_DB_PATH", "/data/transvar_db")
HG38_PATH = os.path.join(DB_PATH, "refseq_hg38")
HG19_PATH = os.path.join(DB_PATH, "refseq_hg19")

# UCSC 下载链接
HG38_FA_URL = "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/bigZips/hg38.fa.gz"
HG19_FA_URL = "https://hgdownload.soe.ucsc.edu/goldenPath/hg19/bigZips/hg19.fa.gz"
HG38_REFSEQ_URL = "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/ncbiRefSeq.txt.gz"
HG19_REFSEQ_URL = "https://hgdownload.soe.ucsc.edu/goldenPath/hg19/database/ncbiRefSeq.txt.gz"


def download_file(url: str, output_path: str, description: str):
    """下载文件并显示进度"""
    if os.path.exists(output_path):
        print(f"  [SKIP] {description} 已存在")
        return

    print(f"  [DOWNLOAD] {description}...")
    print(f"    URL: {url}")

    # 使用 curl 下载（更稳定）
    try:
        subprocess.run(
            ["curl", "-fSL", "-o", output_path, url],
            check=True,
            timeout=600
        )
        print(f"  [OK] {description} 下载完成")
    except subprocess.CalledProcessError as e:
        print(f"  [ERROR] 下载失败: {e}")
        raise


def extract_gzip(gz_path: str):
    """解压 gz 文件"""
    output_path = gz_path[:-3]
    if os.path.exists(output_path):
        print(f"  [SKIP] 文件已解压: {output_path}")
        return output_path

    print(f"  [EXTRACT] 解压 {gz_path}...")
    with gzip.open(gz_path, 'rb') as f_in:
        with open(output_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    print(f"  [OK] 解压完成: {output_path}")
    return output_path


def build_samtools_index(fa_path: str):
    """使用 samtools 建立索引"""
    fai_path = f"{fa_path}.fai"
    if os.path.exists(fai_path):
        print(f"  [SKIP] samtools 索引已存在")
        return

    print(f"  [INDEX] 建立 samtools 索引...")
    subprocess.run(["samtools", "faidx", fa_path], check=True)
    print(f"  [OK] 索引建立完成")


def build_transvar_index(refseq_gz: str):
    """构建 TransVar 索引"""
    print(f"  [INDEX] 构建 TransVar 索引...")
    subprocess.run(
        ["transvar", "index", "--refseq", refseq_gz],
        check=True,
        capture_output=True,
        text=True
    )
    print(f"  [OK] TransVar 索引构建完成")


def register_database(fa_path: str, refseq_gz: str, refversion: str):
    """注册 TransVar 数据库"""
    print(f"  [REGISTER] 注册 {refversion} 数据库...")

    # 注册参考基因组
    subprocess.run(
        ["transvar", "config", "-k", "reference", "-v", fa_path, "--refversion", refversion],
        check=True,
        capture_output=True
    )

    # 注册 RefSeq 注释
    subprocess.run(
        ["transvar", "config", "-k", "refseq", "-v", refseq_gz, "--refversion", refversion],
        check=True,
        capture_output=True
    )

    print(f"  [OK] {refversion} 注册完成")


def build_genome(name: str, path: str, fa_url: str, refseq_url: str, refversion: str):
    """构建单个基因组的数据库"""
    print(f"\n{'='*50}")
    print(f"构建 {name} 数据库")
    print(f"{'='*50}")

    os.makedirs(path, exist_ok=True)
    os.chdir(path)

    # 1. 下载参考基因组
    fa_gz = os.path.join(path, os.path.basename(fa_url))
    download_file(fa_url, fa_gz, f"{name} 参考基因组")
    fa_path = extract_gzip(fa_gz)
    os.remove(fa_gz)  # 删除压缩包

    # 2. 建立索引
    build_samtools_index(fa_path)

    # 3. 下载 RefSeq 注释
    refseq_gz = os.path.join(path, "ncbiRefSeq.txt.gz")
    download_file(refseq_url, refseq_gz, f"{name} RefSeq 注释")

    # 4. 构建 TransVar 索引
    build_transvar_index(refseq_gz)

    # 5. 注册数据库
    register_database(fa_path, refseq_gz, refversion)

    print(f"\n[SUCCESS] {name} 数据库构建完成!")
    return True


def verify_installation(refversion: str = "hg38_refseq"):
    """验证安装"""
    print(f"\n{'='*50}")
    print("验证安装")
    print(f"{'='*50}")

    test_variants = [
        ("PIK3CA:p.E545K", "panno"),
        ("EGFR:p.L858R", "panno"),
    ]

    for variant, mode in test_variants:
        print(f"\n测试: transvar {mode} -i {variant}")
        try:
            result = subprocess.run(
                ["transvar", mode, "-i", variant, "--refseq", "--refversion", refversion],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                print(f"  [OK] 成功")
                print(f"  输出: {result.stdout[:200]}...")
            else:
                print(f"  [WARN] 返回非零: {result.returncode}")
                print(f"  错误: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            print(f"  [WARN] 超时")
        except Exception as e:
            print(f"  [ERROR] {e}")


def main():
    print("TransVar 数据库构建脚本")
    print(f"数据库路径: {DB_PATH}")
    print(f"当前目录: {os.getcwd()}")

    # 确保目录存在
    os.makedirs(DB_PATH, exist_ok=True)

    try:
        # 构建 hg38
        build_genome(
            "hg38 (GRCh38)",
            HG38_PATH,
            HG38_FA_URL,
            HG38_REFSEQ_URL,
            "hg38_refseq"
        )

        # 构建 hg19
        build_genome(
            "hg19 (GRCh37)",
            HG19_PATH,
            HG19_FA_URL,
            HG19_REFSEQ_URL,
            "hg19_refseq"
        )

        # 验证安装
        verify_installation("hg38_refseq")

        print("\n" + "="*50)
        print("所有数据库构建完成!")
        print("="*50)

    except Exception as e:
        print(f"\n[ERROR] 构建失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()