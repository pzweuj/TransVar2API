---
name: transvar-annotate
description: 通过 TransVar API 注释基因变异。将自然语言变异查询转换为 API 调用并返回注释结果。触发场景：(1) 用户询问变异注释、突变注释、基因变异, (2) 用户提到 TransVar、transvar 注释, (3) 用户给出 chr:g.、:c.、:p. 等 HGVS 格式变异, (4) 用户说"注释"、"查一下"、"这个位点"配合变异描述。
---

# TransVar 变异注释

API 地址: `https://pzweuj-transvarweb.hf.space`

## 第1步: 解析用户输入

从用户的自然语言中提取以下参数：

### 变异 variant / variants

| 用户输入示例 | 提取 variant | 对应 mode |
|---|---|---|
| `chr7:g.55259515T>G` | `chr7:g.55259515T>G` | `ganno` |
| `chr7 g.55259515 T>G` | `chr7:g.55259515T>G` | `ganno` |
| `chr7 55259515 T>G` | `chr7:g.55259515T>G` | `ganno` |
| `chr12:g.25398284C>T` | `chr12:g.25398284C>T` | `ganno` |
| `NM_004333.6:c.1799T>A` | `NM_004333.6:c.1799T>A` | `canno` |
| `BRAF V600E` | `BRAF:V600E` | `panno` |
| `TP53 R273H` | `TP53:R273H` | `panno` |
| `KRAS c.35G>A` | `KRAS:c.35G>A` | `canno` |

**格式推断规则（优先级从高到低）：**
1. 输入包含 `chr` + `:g.` → mode=`ganno`，直接使用
2. 输入包含 `:c.` → mode=`canno`，直接使用
3. 输入包含 `:p.` 或 `GENE MUTATION`（空格分隔的基因名+突变） → 拼接为 `GENE:MUTATION`，mode=`panno`
4. 无法推断时默认 mode=`ganno`

**标准化清理：**
- 将半角 `>` 和全角 `＞` 统一为 `>`
- 将 `->` / `→` / `-->` 统一为 `>`
- 移除变异字符串中不必要的空格

### 参考基因组版本 refversion

- 默认: `hg19`
- `hg19` / `GRCh37` / `hg19参考基因组` → `hg19`
- `hg38` / `GRCh38` / `hg38参考基因组` → `hg38`

### 单条 vs 批量

- 单个变异 → `POST /api/annotate`，请求体使用 `variant` 字段
- 多个变异（逗号、顿号、分号、空格、换行分隔）→ `POST /api/batch_annotate`，请求体使用 `variants` 数组
- 用户提到"批量"、"多个" → 使用批量接口

## 第2步: 构造并发送请求

在 Windows PowerShell 5.1 中执行：

### 单条注释

```powershell
$json = '{"variant":"chr7:g.55259515T>G","refversion":"hg19","mode":"ganno","databases":["refseq"]}'
$r = Invoke-RestMethod -Uri "https://pzweuj-transvarweb.hf.space/api/annotate" -Method Post -Body $json -ContentType "application/json"
$r | ConvertTo-Json -Depth 6
```

请求体字段：
| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `variant` | string | 是 | — | 变异描述 |
| `refversion` | string | 否 | `hg19` | 参考基因组版本 |
| `mode` | string | 否 | `ganno` | `ganno`/`canno`/`panno` |
| `databases` | string[] | 否 | `["refseq"]` | 数据库列表 |

### 批量注释

```powershell
$json = '{"variants":["chr7:g.55259515T>G","chr12:g.25398284C>T"],"refversion":"hg19","mode":"ganno","databases":["refseq"]}'
$r = Invoke-RestMethod -Uri "https://pzweuj-transvarweb.hf.space/api/batch_annotate" -Method Post -Body $json -ContentType "application/json"
$r | ConvertTo-Json -Depth 6
```

请求体字段：
| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `variants` | string[] | 是 | — | 变异列表 |
| `refversion` | string | 否 | `hg19` | 参考基因组版本 |
| `mode` | string | 否 | `ganno` | `ganno`/`canno`/`panno` |
| `databases` | string[] | 否 | `["refseq"]` | 数据库列表 |

## 第3步: 解析响应

响应 JSON 结构：
```json
{
  "success": true,
  "input": "chr7:g.55259515T>G",
  "refversion": "hg19",
  "mode": "ganno",
  "databases": ["refseq"],
  "results": [
    {
      "success": true,
      "database": "refseq",
      "result": "input\ttranscript\tgene\tstrand\tcoordinates(gDNA/cDNA/protein)\tregion\tinfo\n...",
      "has_data": true
    }
  ],
  "error": null
}
```

### 结果解读

`results[].result` 是 TSV 格式文本，包含以下列：

| 列名 | 说明 |
|------|------|
| `input` | 输入变异 |
| `transcript` | 转录本 (如 `NM_001354609.1`) |
| `gene` | 基因名 (如 `BRAF`) |
| `strand` | 链方向 (`+` / `-`) |
| `coordinates(gDNA/cDNA/protein)` | 基因组/cDNA/蛋白质坐标 |
| `region` | 位置区域 (如 `inside_[cds_in_exon_15]`) |
| `info` | 附加信息 (CSQN、dbxref 等) |

### 格式化输出

将 TSV 结果解析为可读表格展示给用户：

```
变异: chr7:g.55259515T>G
基因组版本: hg19 | 模式: ganno | 数据库: refseq
─────────────────────────────────────────────
转录本        基因    链    坐标(gDNA/cDNA/protein)              区域
NM_001354609.1 BRAF   -     chr7:g.140753336A>T/c.1799T>A/p.V600E  inside_[cds_in_exon_15]
NM_004333.5    BRAF   -     chr7:g.140753336A>T/c.1799T>A/p.V600E  inside_[cds_in_exon_15]
```

- 如果 `success` 为 `false` 或 `error` 非空，直接向用户展示错误信息
- 如果 `has_data` 为 `false` 或 `result` 仅含表头无数据行，告诉用户"未找到注释结果"

## 第4步: 错误处理

| 情况 | 处理 |
|------|------|
| API 返回 422 | 提示用户检查变异格式是否正确 |
| `results[].result` 包含 `Error=` | 提取错误原因告知用户（如 `invalid_reference_base_T;expect_G`） |
| 网络超时/不可达 | 告知用户 API 服务暂时不可用，稍后重试 |
| 用户未提供变异 | 询问用户要注释的变异位点 |

## 调用示例

**用户说**: "帮我注释一下 chr7:g.55259515T>G"

→ mode=`ganno`, 单条, 直接构造请求调用 API，解析 TSV 结果展示表格

**用户说**: "用 hg38 查 BRAF V600E 和 TP53 R273H"

→ mode=`panno`, refversion=`hg38`, 批量, 两个变异 `["BRAF:V600E","TP53:R273H"]`

**用户说**: "注释这些位点: chr7:g.55259515T>G, chr12:g.25398284C>T, chr17:g.43092962G>A"

→ mode=`ganno`, 批量, 3个变异数组
