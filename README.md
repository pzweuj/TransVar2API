# TransVar2API

基于 Docker 的 TransVar HGVS 注释工具，提供 FastAPI 服务和 Web 界面。

**特点**: 使用 TransVar 官方数据库，支持多数据库同时注释，部署即用。

## 功能特性

- 支持 hg38 (GRCh38) 和 hg19 (GRCh37) 两个参考基因组版本
- **支持多数据库**: RefSeq、Ensembl、GENCODE、UCSC、CCDS
- 支持 panno、canno、ganno 三种注释模式
- 提供 RESTful API 接口
- 友好的 Web 界面，支持单个和批量注释
- 支持部署到 HuggingFace Spaces

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/pzweuj/Transvar2API.git
cd Transvar2API
```

### 2. 构建并启动服务

```bash
# 构建镜像（首次构建约需 20-30 分钟，包含数据库下载）
docker-compose build

# 启动服务
docker-compose up -d
```

### 3. 访问服务

- Web 界面: http://localhost:8000
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

## 使用方法

### Web 界面

1. 打开浏览器访问 http://localhost:8000
2. 输入变异描述（如 `PIK3CA:p.E545K`）
3. 选择参考基因组版本（hg38 或 hg19）
4. 选择注释模式（蛋白/cDNA/基因组）
5. 选择数据库（可多选：RefSeq、Ensembl、GENCODE、UCSC、CCDS）
6. 点击"提交注释"

### API 接口

#### 单个变异注释

```bash
curl -X POST http://localhost:8000/api/annotate \
  -H "Content-Type: application/json" \
  -d '{
    "variant": "PIK3CA:p.E545K",
    "refversion": "hg38",
    "mode": "panno",
    "databases": ["refseq", "ensembl"]
  }'
```

#### 批量注释

```bash
curl -X POST http://localhost:8000/api/batch_annotate \
  -H "Content-Type: application/json" \
  -d '{
    "variants": ["PIK3CA:p.E545K", "EGFR:p.L858R"],
    "refversion": "hg38",
    "mode": "panno",
    "databases": ["refseq"]
  }'
```

#### 调试信息

```bash
curl http://localhost:8000/api/debug
```

## 变异格式说明

| 模式 | 格式示例 |
|------|----------|
| panno (蛋白) | `PIK3CA:p.E545K`, `EGFR:p.L858R` |
| canno (cDNA) | `NM_006218.4:c.1633G>A` |
| ganno (基因组) | `chr3:g.178921852G>A` |

## 支持的数据库

| 数据库 | 说明 |
|--------|------|
| RefSeq | NCBI RefSeq 数据库 |
| Ensembl | Ensembl 基因注释 |
| GENCODE | GENCODE 综合注释 |
| UCSC | UCSC RefGene |
| CCDS | Consensus CDS |

## 部署到 HuggingFace Spaces

本项目支持一键部署到 HuggingFace Spaces：

1. Fork 本项目到你的 GitHub
2. 在 HuggingFace 创建新的 Space (Docker 类型)
3. 连接你的 GitHub 仓库
4. 选择 `Dockerfile` 作为构建文件

## 目录结构

```
Transvar2API/
├── Dockerfile              # Docker 镜像配置
├── docker-compose.yml      # Docker Compose 配置
├── server.py               # FastAPI 服务主程序
├── requirements.txt        # Python 依赖
├── README.md               # 本文档
└── scripts/
    └── hf_startup.sh       # HF Spaces 启动脚本
```

## 常见问题

### Q: 镜像构建很慢怎么办？

首次构建需要下载参考基因组和注释数据库。如果网络不稳定，可以：
1. 使用代理
2. 使用国内镜像源

### Q: 如何查看日志？

```bash
docker-compose logs -f transvar-api
```

### Q: 如何重新构建？

```bash
docker-compose build --no-cache
```

## API 响应格式

### 单个注释响应

```json
{
  "success": true,
  "input": "PIK3CA:p.E545K",
  "refversion": "hg38",
  "mode": "panno",
  "databases": ["refseq"],
  "results": [
    {
      "success": true,
      "database": "refseq",
      "result": "coordinates	gene	ref	alt	aa_change	transcripts	exons	...",
      "has_data": true
    }
  ],
  "error": null
}
```

### 批量注释响应

```json
{
  "success": true,
  "total": 2,
  "results": [
    {
      "input": "PIK3CA:p.E545K",
      "success": true,
      "results": [...]
    },
    {
      "input": "EGFR:p.L858R",
      "success": true,
      "results": [...]
    }
  ]
}
```

## 许可证

MIT License

## 致谢

- [TransVar](https://github.com/zwdzwd/transvar) - HGVS 变异注释工具
- UCSC Genome Browser - 参考基因组数据