# 开发路线图

这份路线图按“能运行、能验证、能扩展”的顺序推进。

## Phase 1: 命令行 LangGraph 最小闭环

目标：用户输入一句 PPT 需求，程序创建一个 `ppt-master` 项目目录。

必须实现：

- `ppt_agent/state.py`
- `ppt_agent/graph.py`
- `ppt_agent/app.py`
- `ppt_agent/nodes/collect_requirement.py`
- `ppt_agent/nodes/check_requirement.py`
- `ppt_agent/nodes/ask_followup.py`
- `ppt_agent/nodes/freeze_brief.py`
- `ppt_agent/nodes/plan_deck.py`
- `ppt_agent/nodes/create_project.py`
- `ppt_agent/services/ppt_master_runner.py`

验收命令：

```powershell
python -m ppt_agent.app "我要做一个毕业答辩PPT，题目是基于Java的多类型网络攻击检测系统，20页，科技蓝风格，给答辩老师看，重点讲系统架构、检测规则和实验结果"
```

验收结果：

```text
需求完整
Brief 已生成
Outline 已生成
Project 已创建
```

## Phase 2: 多轮追问

目标：用户信息不全时，agent 能追问，而不是乱生成。

示例输入：

```text
帮我做一个网络安全系统的PPT
```

应该输出：

```text
我还需要确认：
1. PPT 的具体题目是什么？
2. 使用场景是什么？
3. 目标受众是谁？
4. 大概多少页？
5. 想要什么风格？
```

## Phase 3: 设计确认

目标：引入 `ppt-master` 的八项确认思想。

确认项：

- 画布格式
- 页数范围
- 目标受众
- 风格目标
- 配色方案
- 图标使用
- 字体方案
- 图片使用

这一阶段要让 graph 停下来等用户确认。

## Phase 4: 写入项目资料

目标：把 Brief 和 Outline 写入 `ppt-master` 项目。

产物：

```text
sources/user_requirement.md
agent_brief.json
agent_outline.json
```

注意：这一阶段仍然不移动用户外部文件。

## Phase 5: 生成 design_spec.md 和 spec_lock.md

目标：让 agent 按 `ppt-master` 示例生成设计规格。

参考：

```text
docs/reference/ppt-master/example_design_spec.md
docs/reference/ppt-master/example_spec_lock.md
```

产物：

```text
<project_path>/design_spec.md
<project_path>/spec_lock.md
```

## Phase 6: 逐页 SVG 生成

目标：根据 outline 逐页生成 SVG。

规则：

- 必须串行。
- 每页生成前读取 `spec_lock.md`。
- 每页写入 `svg_output/`。
- 不并行生成页面。

## Phase 7: 质量检查和导出

目标：输出最终 PPTX。

调用：

```powershell
python skills/ppt-master/scripts/finalize_svg.py <project_path>
python skills/ppt-master/scripts/svg_to_pptx.py <project_path>
```

产物：

```text
<project_path>/exports/*.pptx
```
