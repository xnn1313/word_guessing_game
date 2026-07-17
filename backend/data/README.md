# 冻结外部题库

这里的 JSON 是离线构建产物，服务启动时不会解析或写入它们。只有运维人员显式运行
`scripts/import_external_puzzle_banks.py` 才会将内容一次性导入 SQLite。

## 当前规模

- `external_sudoku_bank.json`：简单、中等、困难各 1000 题，共 3000 题；每题已验证唯一解。
- `external_idiom_bank.json`：3000 条候选四字成语。导入时会先排除内置题目已有答案，
  再无复用地组成 1000 个双词交叉关卡（10 个分类，每类 100 关）。

生成文件的稳定 ID 来自上游题面或成语本身的哈希。发布后的 `puzzle_id` 只允许插入，
禁止用后续构建结果覆盖。

## 来源与固定版本

| 内容 | 上游版本 | 许可证 | 本次输入 SHA-256 |
| --- | --- | --- | --- |
| Sudoku Exchange Puzzle Bank | `d8c8ebaee0c08c412cfba96af1923dfa61c83317` | CC0 / public domain | easy `095961e6…49f7`；medium `3fdd27da…82eb`；hard `f9a42587…1e88` |
| JioNLP `chinese_idiom.zip` 词频 | 文件对象 `783abc5237e05f25aea2a11dcc2ae2e0e9f4cd23` | Apache-2.0 | `29716f31…fb7` |
| `crazywhalecc/idiom-database` 释义与拼音 | `084306ce288bb319ddb9d9f55e0252a2eb158040` | MIT；再分发前仍应阅读其数据来源说明 | `27efc332…b10c` |

完整输入哈希也写在两个 JSON 的 `metadata` 中。来源地址和许可证地址同样保存在
`metadata`，构建脚本不会联网，也不会补写或猜测缺失释义。

## 可复现构建

准备三个数独文本文件、JioNLP 压缩包和成语 JSON 后，在仓库根目录运行：

```bash
./.venv/bin/python backend/scripts/build_external_puzzle_banks.py \
  --sudoku-dir /path/to/sudoku-files \
  --idiom-zip /path/to/chinese_idiom.zip \
  --idiom-json /path/to/idiom-database.json
```

脚本会校验来源哈希格式、数独唯一解、四字常用汉字、真实释义、重复项和有限数值，
然后原子替换输出文件。相同输入会产生字节一致的输出。

## 导入

数据库必须先由应用完成初始化。备份数据库后，在 `backend` 目录运行：

```bash
../.venv/bin/python scripts/import_external_puzzle_banks.py
```

导入器会先完整验证两个文件，再用单个 `BEGIN IMMEDIATE` 事务写入。重复运行是幂等的；
如果同一 schema 版本的载荷、筛选结果或已发布题目发生变化，会整批拒绝且不会部分写入。
