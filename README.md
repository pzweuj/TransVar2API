# TransVar2API

基于 Docker 的 TransVar HGVS 注释工具，提供 FastAPI 服务和 Web 界面。

**特点**: 数据库已内置于 Docker 镜像中，部署即用，无需额外配置。

## 功能特性

- 支持 hg38 (GRCh38) 和 hg19 (GRCh37) 两个参考基因组版本
- 使用 UCSC RefSeq 数据库（包含 chr 前缀）
- 支持 panno、canno、ganno、codonsearch 四种注释模式
- 提供 RESTful API 接口
- 友好的 Web 界面，支持单个和批量注释

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/pzweuj/Transvar2API.git
cd Transvar2API
```

### 2. 构建并启动服务

```bash
# 构建镜像（首次构建约需 15-20 分钟，包含数据库下载）
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
4. 选择注释模式
5. 点击"提交注释"

### API 接口

#### 单个变异注释

```bash
curl -X POST http://localhost:8000/api/annotate \
  -H "Content-Type: application/json" \
  -d '{
    "variant": "PIK3CA:p.E545K",
    "refversion": "hg38_refseq",
    "mode": "panno"
  }'
```

#### 批量注释

```bash
curl -X POST http://localhost:8000/api/batch_annotate \
  -H "Content-Type: application/json" \
  -d '{
    "variants": ["PIK3CA:p.E545K", "EGFR:p.L858R"],
    "refversion": "hg38_refseq",
    "mode": "panno"
  }'
```

#### 获取数据库信息

```bash
curl http://localhost:8000/api/db_info
```

## 变异格式说明

| 模式 | 格式示例 |
|------|----------|
| panno (蛋白) | `PIK3CA:p.E545K`, `EGFR:p.L858R` |
| canno (cDNA) | `NM_006218.4:c.1633G>A` |
| ganno (基因组) | `PIK3CA:g.178921852G>A` |
| codonsearch | `KRAS:c.12GTT>TTC` |

## 目录结构

```
Transvar2API/
├── Dockerfile              # Docker 镜像配置（含数据库构建）
├── docker-compose.yml      # Docker Compose 配置
├── server.py               # FastAPI 服务主程序
├── requirements.txt        # Python 依赖
├── README.md               # 本文档
└── scripts/
    ├── build_database.py   # 数据库构建脚本（备用）
    ├── build_hg38.sh       # hg38 构建脚本
    └── build_hg19.sh       # hg19 构建脚本
```

## 常见问题

### Q: 镜像构建很慢怎么办？

首次构建需要下载约 6GB 的参考基因组数据。如果网络不稳定，可以：
1. 使用代理
2. 手动下载文件后放入构建目录

### Q: 如何查看日志？

```bash
docker-compose logs -f transvar-api
```

### Q: 如何重新构建数据库？

修改 `Dockerfile` 后重新构建：
```bash
docker-compose build --no-cache
```

## 技术细节

### 数据库构建

- hg38 参考基因组: ~3GB
- hg19 参考基因组: ~3GB
- RefSeq 注释文件: ~50MB
- 索引文件: ~100MB

总镜像大小约 7-8GB。

### API 响应格式

```json
{
  "success": true,
  "input": "PIK3CA:p.E545K",
  "refversion": "hg38_refseq",
  "mode": "panno",
  "result": "...",
  "error": null,
  "raw_output": "..."
}
```

## 许可证

MIT License