#!/usr/bin/env python3
"""
创建 TransVar 配置文件
在服务启动时运行，创建 ~/.transvar.cfg 配置文件
"""

import os
import configparser

DB_PATH = os.getenv("TRANSVAR_DB_PATH", "/data/transvar_db")
HOME = os.path.expanduser("~")

def create_config():
    """创建 transvar 配置文件"""

    config = configparser.ConfigParser()

    # 默认设置
    config['DEFAULT'] = {
        'refversion': 'hg38_ucsc'
    }

    # UCSC hg38 配置
    config['hg38_ucsc'] = {
        'reference': f'{DB_PATH}/ucsc_hg38/hg38.fa',
        'ucsc': f'{DB_PATH}/ucsc_hg38/ncbiRefSeq.txt.gz'
    }

    # UCSC hg19 配置
    config['hg19_ucsc'] = {
        'reference': f'{DB_PATH}/ucsc_hg19/hg19.fa',
        'ucsc': f'{DB_PATH}/ucsc_hg19/ncbiRefSeq.txt.gz'
    }

    # NCBI RefSeq hg38 配置
    config['hg38_ncbi'] = {
        'reference': f'{DB_PATH}/ncbi_refseq_hg38/hg38.fa',
        'refseq': f'{DB_PATH}/ncbi_refseq_hg38/hg38_refseq.gff.gz'
    }

    # NCBI RefSeq hg19 配置
    config['hg19_ncbi'] = {
        'reference': f'{DB_PATH}/ncbi_refseq_hg19/hg19.fa',
        'refseq': f'{DB_PATH}/ncbi_refseq_hg19/hg19_refseq.gff.gz'
    }

    # 写入配置文件
    config_path = os.path.join(HOME, '.transvar.cfg')

    with open(config_path, 'w') as f:
        config.write(f)

    print(f"配置文件已创建: {config_path}")
    print("\n配置内容:")
    with open(config_path, 'r') as f:
        print(f.read())

    return config_path

if __name__ == '__main__':
    create_config()