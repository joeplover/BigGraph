# Agent 颗粒度设计

这份文档只回答一个问题：PPT 制作 Agent 应该拆到什么颗粒度。

结论：第一版不要拆成多个独立 agent，要拆成一个 LangGraph 里的多个节点。

## 为什么先用节点，不先用多 agent

`ppt-master` 的流程是严格串行的：

```text
需求
  -> 设计确认
  -> design_spec.md
  -> spec_lock.md
  -> 逐页 SVG
  -> 检查
  -> 导出
```

如果一开始拆成多个并行 agent，很容易出现：

- 页面风格不一致。
- 不同 agent 对用户需求理解不同。
- SVG 页面之间视觉节奏漂移。
- 还没确认设计规格就提前生成页面。
- 调试时不知道错误来自哪个 agent。

所以第一版采用：

```text
一个 LangGraph
多个清晰节点
每个节点只做一件事
```

## 第一版节点

```text
START
  -> collect_requirement_node
  -> check_requirement_node
  -> route_by_requirement
       -> ask_followup_node
       -> freeze_brief_node
  -> plan_deck_node
  -> create_project_node
  -> END
```

## 节点定义

### 1. collect_requirement_node

职责：从用户消息中提取 PPT 需求。

输入：

```python
state["user_message"]
```

输出：

```python
state["requirement"]
```

字段：

```python
{
    "topic": "PPT 题目",
    "use_case": "使用场景",
    "audience": "目标受众",
    "page_count": 20,
    "style": "视觉风格",
    "language": "zh-CN",
    "key_points": ["重点1", "重点2"],
    "source_files": []
}
```

### 2. check_requirement_node

职责：检查需求是否足够创建 PPT Brief。

最小必填字段：

```text
topic
use_case
audience
page_count
style
```

输出：

```python
state["requirement_complete"] = True 或 False
state["missing_fields"] = ["audience", "page_count"]
```

### 3. ask_followup_node

职责：需求不完整时，向用户追问。

输入：

```python
state["missing_fields"]
```

输出：

```python
state["assistant_reply"]
state["status"] = "waiting_user"
```

示例：

```text
我还需要确认两点：
1. 这份 PPT 是给谁看的？例如答辩老师、领导、客户。
2. 你希望大概多少页？
```

### 4. freeze_brief_node

职责：把聊天需求冻结成稳定的 PPT Brief。

输入：

```python
state["requirement"]
```

输出：

```python
state["ppt_brief"]
```

Brief 是后续页面规划、项目创建、设计规格生成的统一输入。

### 5. plan_deck_node

职责：根据 PPT Brief 生成页面大纲。

输入：

```python
state["ppt_brief"]
```

输出：

```python
state["deck_outline"]
```

每一页包含：

```python
{
    "page": 1,
    "title": "封面",
    "purpose": "展示题目、学生、导师",
    "rhythm": "anchor"
}
```

### 6. create_project_node

职责：调用 `ppt-master` 创建项目目录。

输入：

```python
state["ppt_brief"]
state["deck_outline"]
```

调用：

```powershell
python skills/ppt-master/scripts/project_manager.py init <project_name> --format ppt169
```

输出：

```python
state["project_path"]
state["status"] = "project_created"
```

## 后续阶段节点

第一版跑通后，再增加：

```text
write_requirement_source_node
generate_design_spec_node
generate_spec_lock_node
confirm_design_node
generate_svg_page_node
check_svg_quality_node
finalize_svg_node
export_pptx_node
deliver_result_node
```

## 什么时候升级成多 agent

只有当某个节点内部逻辑复杂到需要独立上下文时，才升级成子 agent。

候选子 agent：

| Agent | 从哪个节点升级 | 负责什么 |
| --- | --- | --- |
| Requirement Agent | collect_requirement_node | 多轮需求收集 |
| Strategist Agent | plan_deck_node / generate_design_spec_node | 页面规划和设计规格 |
| Executor Agent | generate_svg_page_node | 逐页生成 SVG |
| Quality Agent | check_svg_quality_node | 检查和定位 SVG 问题 |
| Delivery Agent | export_pptx_node | 导出和交付 |
