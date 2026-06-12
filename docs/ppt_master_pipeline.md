# ppt-master 使用资料

这份文档只记录 `growing_agent` 需要调用的 `ppt-master` 能力。

## 本地路径

```text
F:\Make_money\基于java的多类型网络攻击检测系统\ppt-master
```

后续代码中建议把这个路径配置成常量：

```python
PPT_MASTER_ROOT = r"F:\Make_money\基于java的多类型网络攻击检测系统\ppt-master"
```

## 第一版只调用一个脚本

第一版只调用项目创建脚本：

```powershell
python skills/ppt-master/scripts/project_manager.py init <project_name> --format ppt169
```

示例：

```powershell
cd F:\Make_money\基于java的多类型网络攻击检测系统\ppt-master
python skills/ppt-master/scripts/project_manager.py init network_attack_detection --format ppt169
```

预期输出目录：

```text
projects/network_attack_detection_ppt169_YYYYMMDD/
```

## 后续阶段会用到的命令

### 导入资料

```powershell
python skills/ppt-master/scripts/project_manager.py import-sources <project_path> <source_files...> --move
```

注意：`--move` 会移动文件。第一版先不用这个命令，避免误移动用户资料。

### 校验项目目录

```powershell
python skills/ppt-master/scripts/project_manager.py validate <project_path>
```

### 分割讲稿

```powershell
python skills/ppt-master/scripts/total_md_split.py <project_path>
```

### 处理 SVG

```powershell
python skills/ppt-master/scripts/finalize_svg.py <project_path>
```

### 导出 PPTX

```powershell
python skills/ppt-master/scripts/svg_to_pptx.py <project_path>
```

## 项目目录结构

`ppt-master` 创建的项目大概长这样：

```text
projects/<project_name>/
  README.md
  design_spec.md
  spec_lock.md
  sources/
  images/
  notes/
  svg_output/
  svg_final/
  templates/
  exports/
```

第一版只要求创建目录成功，不要求这些文件全部存在。

## 参考示例

已经完成的本地示例：

```text
F:\Make_money\基于java的多类型网络攻击检测系统\ppt-master\projects\network_attack_detection_ppt169_20260519
```

里面最有用的两个文件：

```text
design_spec.md
spec_lock.md
```

已经转存到：

```text
docs/reference/ppt-master/example_design_spec.md
docs/reference/ppt-master/example_spec_lock.md
```

## growing_agent 和 ppt-master 的边界

`growing_agent` 负责：

- 聊天式需求收集。
- 把需求变成结构化 Brief。
- 生成页面大纲。
- 决定什么时候调用 `ppt-master`。
- 保存每一步状态。

`ppt-master` 负责：

- 创建 PPT 项目目录。
- 管理项目结构。
- 处理 SVG。
- 导出 PPTX。

第一版不要修改 `ppt-master` 源码。
