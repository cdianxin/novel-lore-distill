# 审计配置

复制根目录的 `config.example.json`，按实际资料库修改后，用 `--config` 传给审计脚本。未指定配置时使用脚本内置的中文默认值。

## 主要字段

| 字段 | 作用 |
| --- | --- |
| `expected_chunks` | 预期分块数；`null` 时只根据实际最高编号报告，不能证明末尾范围完整 |
| `chunks.text` / `chunks.extracted` | 分块目录、文件名前缀和后缀 |
| `merge` | 合并目录、编号格式和每份合并文件需要的一级栏目数 |
| `categories` | 启用的分类；`card_folder` 为 `null` 时只审计终审输入，不要求卡片目录 |
| `required_fields` | 每类卡片必须出现的标题或字段标签 |
| `chapters.patterns` | 带命名捕获组的正则；默认使用 `number` 或 `number_cn` 作为章节号 |
| `chapters.candidates` | 需要扫描的时间线或大事记文件 |
| `manifest_file` / `output.manifest_file` | 相对资料库根目录的 manifest 路径 |
| `state_file` / `output.state_file` | 相对资料库根目录的流水线状态文件路径 |
| `output.report_file` | 默认审计报告路径；命令行 `--report` 优先 |

分类可以替换为科幻、推理、历史或其他题材需要的名称，例如“线索”“科技”“制度”。不要为了匹配默认模板保留原文没有的类别。

章节正则的 `flags` 支持 Python `re` 标志名，例如 `IGNORECASE`。中文数字规则使用 `number_type: "chinese"`；自定义规则可以直接输出阿拉伯数字。

## 使用

```powershell
python scripts/audit_lore_distill.py `
  "D:\资料\某书-蒸馏" `
  --config "D:\资料\某书-蒸馏\audit-config.json" `
  --strict
```

命令行的 `--expected-chunks`、`--first-chapter` 和 `--last-chapter` 会覆盖配置文件中的同名值。
