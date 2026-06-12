# 工作资料总文档

这份文档是 `growing_agent` 的主工作文档。写代码时优先看这一份。

## 1. 我们要做什么

我们要做一个聊天式 PPT 制作 Agent。

用户通过聊天描述需求，例如：

```text
我要做一个毕业答辩 PPT，题目是《基于 Java 的多类型网络攻击检测系统设计与实现》，20 页，科技蓝风格，给答辩老师看，重点讲系统架构、检测规则和实验结果。
```

Agent 要把这段话变成结构化任务，然后调用 `ppt-master` 的能力创建 PPT 项目。

第一版只做到：

```text
聊天需求
  -> 结构化需求
  -> PPT Brief
  -> 页面大纲
  -> 创建 ppt-master 项目
```

## 2. 我们不用重新做什么

不重新实现 PPT 生成器。

`ppt-master` 已经负责这些事情：

- 创建项目目录。
- 管理 `sources/`、`images/`、`svg_output/`、`exports/`。
- 把 SVG 后处理。
- 把 SVG 导出成 PPTX。

`growing_agent` 只负责在它前面加一个聊天式控制层。

## 3. 本地关键路径

`growing_agent` 仓库：

```text
F:\GitHub_project\growing_agent
```

`ppt-master` 仓库：

```text
F:\Make_money\基于java的多类型网络攻击检测系统\ppt-master
```

`ppt-master` 已完成示例项目：

```text
F:\Make_money\基于java的多类型网络攻击检测系统\ppt-master\projects\network_attack_detection_ppt169_20260519
```

## 4. 已转存的参考资料

这些文件已经放在 `growing_agent` 里，写代码时可以直接看。

| 文件 | 为什么需要 |
| --- | --- |
| `docs/reference/ppt-master/SKILL.md` | `ppt-master` 的完整工作流。需要理解八项确认、串行生成、SVG 约束。 |
| `docs/reference/ppt-master/scripts_README.md` | 常用脚本命令。需要知道怎么创建项目、处理 SVG、导出 PPTX。 |
| `docs/reference/ppt-master/technical-design.md` | 技术设计背景。需要理解为什么用 SVG、为什么需要 `spec_lock.md`。 |
| `docs/reference/ppt-master/example_design_spec.md` | 一个真实项目的设计规格示例。后面生成 `design_spec.md` 时参考。 |
| `docs/reference/ppt-master/example_spec_lock.md` | 一个真实项目的执行锁示例。后面生成 `spec_lock.md` 时参考。 |

## 5. 第一版需要用到的命令

第一版只需要调用一个 `ppt-master` 命令。

工作目录必须是：

```text
F:\Make_money\基于java的多类型网络攻击检测系统\ppt-master
```

命令：

```powershell
python skills/ppt-master/scripts/project_manager.py init <project_name> --format ppt169
```

示例：

```powershell
python skills/ppt-master/scripts/project_manager.py init network_attack_detection --format ppt169
```

创建成功后，会出现类似目录：

```text
projects/network_attack_detection_ppt169_20260603
```

## 6. 第一版不要调用的命令

第一版先不要调用这些命令：

```powershell
python skills/ppt-master/scripts/project_manager.py import-sources <project_path> <source_files...> --move
python skills/ppt-master/scripts/finalize_svg.py <project_path>
python skills/ppt-master/scripts/svg_to_pptx.py <project_path>
```

原因：

- `import-sources --move` 会移动用户文件，第一版先避免这个风险。
- `finalize_svg.py` 需要已经有 SVG 页面。
- `svg_to_pptx.py` 需要已经完成后处理。

## 7. 第一版 State 设计

`state.py` 里先定义一个 `TypedDict`。

```python
from typing import Literal, TypedDict


class PPTAgentState(TypedDict, total=False):
    user_message: str
    assistant_reply: str

    requirement: dict
    missing_fields: list[str]
    requirement_complete: bool

    ppt_brief: dict
    deck_outline: list[dict]

    project_name: str
    project_path: str

    status: Literal[
        "collecting",
        "waiting_user",
        "brief_ready",
        "outline_ready",
        "project_created",
        "failed",
    ]
    error: str
```

后面可以再把 `requirement`、`ppt_brief`、`deck_outline` 改成 Pydantic 模型。第一版先不要复杂化。

## 8. 第一版节点清单

### collect_requirement_node

输入：

```python
state["user_message"]
```

输出：

```python
state["requirement"]
```

第一版可以用简单规则提取，不一定马上接大模型。

### check_requirement_node

检查这些字段：

```text
topic
use_case
audience
page_count
style
```

输出：

```python
state["requirement_complete"]
state["missing_fields"]
```

### ask_followup_node

当 `requirement_complete == False` 时执行。

输出：

```python
state["assistant_reply"]
state["status"] = "waiting_user"
```

### freeze_brief_node

当 `requirement_complete == True` 时执行。

输出：

```python
state["ppt_brief"]
state["status"] = "brief_ready"
```

### plan_deck_node

根据 `ppt_brief` 生成页面大纲。

输出：

```python
state["deck_outline"]
state["status"] = "outline_ready"
```

### create_project_node

调用 `ppt-master` 创建项目。

输出：

```python
state["project_name"]
state["project_path"]
state["status"] = "project_created"
```

## 9. 第一版图结构

```text
START
  -> collect_requirement_node
  -> check_requirement_node
  -> route_by_requirement
       -> ask_followup_node -> END
       -> freeze_brief_node
  -> plan_deck_node
  -> create_project_node
  -> END
```

路由函数：

```python
def route_by_requirement(state: PPTAgentState) -> str:
    if state.get("requirement_complete"):
        return "complete"
    return "missing"
```

## 10. 第一版文件清单

必须创建：

```text
ppt_agent/
  __init__.py
  app.py
  graph.py
  state.py
  nodes/
    __init__.py
    collect_requirement.py
    check_requirement.py
    ask_followup.py
    freeze_brief.py
    plan_deck.py
    create_project.py
  services/
    __init__.py
    ppt_master_runner.py
    project_naming.py
```

暂时不创建：

```text
api/
storage/
database/
frontend/
```

## 11. 第一版验收

命令：

```powershell
python -m ppt_agent.app "我要做一个毕业答辩PPT，题目是基于Java的多类型网络攻击检测系统，20页，科技蓝风格，给答辩老师看，重点讲系统架构、检测规则和实验结果"
```

输出必须包含：

```text
需求完整
Brief 已生成
Outline 已生成
Project 已创建
```

并且 `ppt-master/projects/` 下真的出现一个新项目目录。

## 12. 第二版再做什么

第二版才做多轮对话：

```text
用户信息不完整
  -> agent 追问
  -> 用户补充
  -> 合并旧 state
  -> 再检查
```

第三版再做设计确认。

第四版再写入 `design_spec.md` 和 `spec_lock.md`。

第五版再生成 SVG 和导出 PPTX。

## 13. 当前最重要的开发纪律

第一版只解决一个问题：

```text
把一句完整 PPT 需求变成一个真实的 ppt-master 项目目录。
```

不要同时做：

- FastAPI
- 数据库
- 用户登录
- 文件上传
- 自动导出 PPTX
- 多 agent
- 复杂 Prompt 管理

这些都会让第一版失焦。
