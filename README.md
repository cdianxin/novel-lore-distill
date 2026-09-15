# novel-lore-distill

一个用于把长篇小说或长文本整理成**可追溯、可检索、可继续编辑的设定资料库**的 ZCode Skill。

它适合将 TXT、EPUB/PDF 转出的文本、字幕和其他长篇资料，整理为人物、事件、地点、势力、物品、能力/规则、术语和大事年表；也支持对旧蒸馏库做来源覆盖审计、漏项修复和索引修复。

本 skill 不绑定奇幻、科幻、推理、历史、现实、武侠、言情或其他题材。分类会根据原文和用户需求调整，不会为不存在的概念强行生成卡片。

> 本项目主要面向 ZCode / Agents 风格的本地 Skill 使用场景。

## 主要能力

- 人物/角色卡：身份、别名、目标、关系、关键经历、结局和出场章节
- 事件/情节/任务卡：案件、战役、冒险、比赛、灾难、任务、剧情线或其他关键事件
- 地点/场景卡：位置、功能、历史变化、场景规则和关联实体
- 势力/组织/阵营卡：成员、目标、结构、资源、关系和阶段变化
- 物品/资源/技术卡：来源、属性、用途、持有者、限制和变化
- 能力/技能/制度/规则卡：作用对象、触发条件、代价、限制、演变和例证
- 术语与世界观词典：专有名词、制度、文化、历史、技术和设定解释
- 按章节或原文时间排序的大事记/时间线
- 同名对象、别名、译名和阶段性身份的冲突裁决
- 根目录索引和分类目录索引生成
- SillyTavern World Book / Lorebook / 角色卡 JSON 的后续转换基础
- 旧资料库的来源覆盖率、索引链接和卡片质量审计

## 为什么不是普通的“总结小说”

本 Skill 的目标不是写读后感，也不是只输出一篇剧情简介，而是建立一套可以继续查询、编辑和转换的结构化资料库。

它会把长文本拆成多个章节或场景分块，保留中间提取结果和来源链，再进行跨分块合并。每条重要事实尽量带有：

- 来源文件
- 来源分块
- 原文章节或场景
- 相关实体
- 信息状态（核心、次要、仅提及或待复核）

没有证据的内容不会被写成确定事实。

## 处理流程

```text
原文 TXT / EPUB / PDF 转文本
              │
              ▼
   盘点编码、章节、文件大小和范围
              │
              ▼
       按章节或场景切成分块
              │
              ▼
  并行提取人物/事件/地点/势力/物品/能力/术语/大事记
              │
              ▼
        一级合并：按章节区间归并
              │
              ▼
       终审输入覆盖率检查（全部来源）
              │
              ▼
   二级终审：按实体去重、合并别名和阶段
              │
              ▼
  冲突裁决、卡片分层、索引和别名映射
              │
              ▼
          全量审计与可选 JSON 转换
```

## 输出目录

默认在源文件旁建立一个新的 `<书名>-蒸馏/` 目录，不覆盖原文：

```text
<书名>-蒸馏/
├── 00-总览.md
├── PIPELINE_STATE.md
├── manifest.json
├── audit-config.json       # 可选：自定义分类、字段和章节规则
├── 角色索引.md
├── 事件索引.md
├── 地点索引.md
├── 势力索引.md
├── 物品索引.md
├── 能力索引.md
├── 术语表.md
├── 大事年表.md
├── 别名映射.md
├── 角色/
├── 事件/
├── 地点/
├── 势力/
├── 物品/
├── 能力/
├── 分块文本/
├── 分块提取/
├── 合并/
├── 终审输入/
└── 修复/
```

`分块文本/`、`分块提取/`、`合并/` 和`修复/`不是无用临时文件，而是审计、回滚和断点续跑所需的证据链。合并文件数量根据文本规模和处理范围决定，不绑定固定章节数。

## 安装

将整个 `novel-lore-distill` 目录复制到任一可发现的 Skill 目录：

```text
用户级：~/.agents/skills/novel-lore-distill/
用户级：~/.zcode/skills/novel-lore-distill/
项目级：<project>/.agents/skills/novel-lore-distill/
项目级：<project>/.zcode/skills/novel-lore-distill/
```

在当前 Windows 环境中，也可以直接复制到：

```text
D:\Claude\.agents\skills\novel-lore-distill\
```

目录中必须包含：

```text
SKILL.md
references/card-schemas.md
references/repair-checklist.md
references/test-prompts.md
scripts/audit_lore_distill.py
scripts/create_lore_manifest.py
```

## 触发方式

自然语言触发示例：

- “把这本小说蒸馏成角色、事件和世界观资料库。”
- “提取这本书所有人物、地点、势力、物品和能力规则。”
- “帮我做一套小说世界书和人物关系索引。”
- “把这部长篇整理成 SillyTavern Lorebook。”
- “之前的蒸馏库可能漏了几卷，帮我审查和修复。”
- “检查人物卡有没有重复、来源有没有覆盖、索引有没有坏链。”

也可以在 ZCode 中显式加载：

```text
/skill novel-lore-distill D:\小说\某部长篇.txt
```

## 使用建议

### 第一次处理一本小说

推荐先试点一卷或前 50-100 章：

1. 检查章节或场景识别是否正确；
2. 确认人物、事件、地点和其他卡片字段符合需求；
3. 确认“核心/次要/仅提及/待复核”的分层方式；
4. 确认后再运行全书批量任务。

如果用户明确要求直接处理全书，仍然要先说明文本规模、预计分块数和运行成本。

### 全书批量处理

长篇小说通常不能一次放进上下文，应按章节或稳定场景切块。建议每块约 15-25 章，实际大小根据章节长度调整。每个子代理必须读完整自己的分块，不得只读开头或默认 `Read` 一次就代表读完。

并发数不能写死。先用 3-4 个子代理试跑，根据平台返回的并发和配额错误逐步增加；如果出现限制，退回上一次成功的并发数，并只重跑失败编号。

### 需要 World Book 或 Lorebook 时

先完成 Markdown 资料库、索引和审计，再转换成 World Book、Lorebook 或角色卡 JSON。不要直接把未去重的分块提取结果塞进 JSON，否则容易出现别名重复、规则冲突和来源丢失。

## 卡片状态

每类实体都应尽量使用状态字段：

- **核心**：多章节、多来源或主线关键实体
- **次要**：有明确身份和行动，但不是主线核心
- **仅提及**：只有名称、称呼或一次转述，资料不足
- **待复核**：来源之间有身份、时间、关系、能力或结局冲突

“仅提及”对象不应被静默删除，也不应伪装成完整传记。空白字段可以写“原文未说明”，不要用“输入未提供”制造模板噪声。

## 审计脚本

`scripts/audit_lore_distill.py` 是只读审计工具。它会检查：

- 分块文本和分块提取编号是否连续；
- 合并文件编号是否连续，每份是否包含八个一级栏目；
- 每份终审输入是否包含合并目录中的全部实际来源；
- 已声明的章节或时间范围是否覆盖源文首尾；
- 卡片是否为空、缺少实体状态、实体 ID、逐条证据或来源定位；
- 根索引和目录内索引中的所有 Markdown 链接、锚点是否存在，以及是否有卡片未被索引；
- `manifest.json` 是否完整，源文件可访问时 SHA-256 和大小是否匹配；
- `PIPELINE_STATE.md` 是否包含固定状态字段；
- 仅提及、待复核、短卡、占位字段和规范化重名数量；
- 与修复前基线的数量差异。

运行：

```bash
python scripts/audit_lore_distill.py "D:\小说\某书-蒸馏"
```

交付前使用严格模式；发现缺口时命令返回状态码 `1`，输出目录不存在返回 `2`：

```powershell
python scripts/audit_lore_distill.py "D:\小说\某书-蒸馏" --strict
```

如果已知分块和章节范围，可以显式提供预期值：

```bash
python scripts/audit_lore_distill.py \
  "D:\小说\某书-蒸馏" \
  --config "D:\小说\某书-蒸馏\audit-config.json" \
  --baseline "D:\小说\某书-蒸馏\修复\repair-baseline.json" \
  --report "D:\小说\某书-蒸馏\修复\audit-report.json" \
  --strict
```

`--expected-chunks`、`--first-chapter` 和 `--last-chapter` 都是可选的，不提供时不会假设某本书的固定规模；也可以在配置文件中设置。章节规则、分类、字段、合并栏目数和输出路径见 [`config.example.json`](config.example.json) 与 [`references/config-schema.md`](references/config-schema.md)。脚本会在 `修复/audit-report.json` 写入机器可读报告；它不会修改卡片和原文。

处理原文的第一步可生成 manifest：

```powershell
python scripts/create_lore_manifest.py "D:\小说\某部长篇.txt" "D:\小说\某书-蒸馏"
```

## 安全与边界

- 不凭记忆补全小说设定；没有原文就停止并索要文本来源。
- 不覆盖原始 TXT、EPUB 或 PDF。
- 覆盖正式卡片目录前先建立备份。
- 不把同名自动当成同一实体；不确定时保留冲突并标记待复核。
- 不把某一题材的专用分类套用到其他题材。
- 不擅自纠正原文的章节编号、时间矛盾或前后冲突；保留证据并说明边界。
- 不把候选提取结果冒充已审计定稿。
- 本 Skill 不负责作者思想方法论蒸馏，也不负责人物角色扮演。

## 参考文件

- [`SKILL.md`](SKILL.md)：完整执行流程和工具行为规范
- [`references/card-schemas.md`](references/card-schemas.md)：卡片与中间文件字段规范
- [`references/config-schema.md`](references/config-schema.md)：自定义分类、字段、章节规则和输出路径
- [`references/pipeline-state-schema.md`](references/pipeline-state-schema.md)：`PIPELINE_STATE.md` 固定字段
- [`references/repair-checklist.md`](references/repair-checklist.md)：修复、覆盖率和交付检查清单
- [`references/test-prompts.md`](references/test-prompts.md)：触发和修复分支测试提示
- [`scripts/audit_lore_distill.py`](scripts/audit_lore_distill.py)：最终审计脚本
- [`scripts/create_lore_manifest.py`](scripts/create_lore_manifest.py)：生成原始文件 manifest

## 许可证

本项目当前未附带开源许可证。若要允许他人复制、修改和再发布，请在仓库中补充合适的 LICENSE 文件。
