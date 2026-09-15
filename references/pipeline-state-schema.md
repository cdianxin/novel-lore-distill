# PIPELINE_STATE.md 规范

在开始处理、分块、合并、终审和交付时持续更新 `PIPELINE_STATE.md`。每个固定标题都必须保留，即使某个值为“未执行”“不适用”或“待人工确认”。这样中断后可以判断已完成范围，而不会把候选结果误认为定稿。

```markdown
# 蒸馏流水线状态

## 当前阶段
- 状态：盘点 / 分块 / 分块提取 / 一级合并 / 终审 / 审计 / 已交付
- 最后成功步骤：

## 处理范围
- source_file：
- scope：全书 / 指定卷 / 指定章节 / 场景范围
- first_chapter：
- last_chapter：
- expected_chunks：

## 产物统计
- chunk_text：
- chunk_extracted：
- merge_files：
- terminal_inputs：
- final_cards：

## 来源与证据
- manifest：manifest.json
- source_sha256：
- provenance_policy：每条事实保留来源文件、分块、章节或场景定位
- audit_report：

## 并发与重试
- peak_concurrency：
- retry_count：
- failed_chunks：

## 备份与恢复
- backup_path：
- baseline_report：
- restore_note：

## 待复核
- unresolved_conflicts：
- suspected_omissions：
- unverified_ranges：

## 最后更新
- timestamp_utc：
- operator：
```

审计器会检查固定标题是否存在；不会根据空白字段擅自判定处理完成。
