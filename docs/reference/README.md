# Reference Files

这里存放 `growing_agent` 的外部参考资料。

## ppt-master

来源：

```text
F:\Make_money\基于java的多类型网络攻击检测系统\ppt-master
```

已转存的关键文件：

| File | Purpose |
| --- | --- |
| `ppt-master/SKILL.md` | `ppt-master` 的完整工作流说明，包含严格串行流程、八项确认、SVG 生成纪律、导出流程 |
| `ppt-master/scripts_README.md` | 常用脚本入口说明，例如 `project_manager.py`、`finalize_svg.py`、`svg_to_pptx.py` |
| `ppt-master/technical-design.md` | 技术设计说明，解释为什么使用 SVG、为什么串行生成、为什么需要 `spec_lock.md` |
| `ppt-master/example_design_spec.md` | 已完成项目里的 `design_spec.md` 示例 |
| `ppt-master/example_spec_lock.md` | 已完成项目里的 `spec_lock.md` 示例 |

## 使用原则

这些文件只作为学习和实现参考。后续代码不要直接修改这些参考文件。

真正的 agent 实现应该放在：

```text
ppt_agent/
```

项目说明和学习笔记放在：

```text
docs/
```
