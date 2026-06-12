# 基于Java的多类型网络攻击检测系统设计与实现 - Design Spec

> Human-readable design narrative. Machine-readable contract: `spec_lock.md`.

## I. Project Information

| Item | Value |
| ---- | ----- |
| **Project Name** | 基于Java的多类型网络攻击检测系统设计与实现 |
| **Canvas Format** | PPT 16:9 (1280×720) |
| **Page Count** | 22 |
| **Design Style** | General Consulting (B) — 数据清晰优先 |
| **Target Audience** | 毕业答辩评审专家 |
| **Use Case** | 本科毕业设计答辩 |
| **Created Date** | 2026-05-19 |

## II. Canvas Specification

| Property | Value |
| -------- | ----- |
| **Format** | PPT 16:9 |
| **Dimensions** | 1280×720 |
| **viewBox** | `0 0 1280 720` |
| **Margins** | 左右 60px，上下 50px |
| **Content Area** | 1160×620 (60,50 → 1220,670) |

## III. Visual Theme

- **Style**: General Consulting — 逻辑严谨、数据驱动、架构清晰
- **Theme**: Light theme
- **Tone**: 专业、科技、可信

### Color Scheme

| Role | HEX | Purpose |
| ---- | --- | ------- |
| **Background** | `#FFFFFF` | 主背景 |
| **Secondary bg** | `#F0F4F8` | 卡片底色、分区底色 |
| **Primary** | `#1565C0` | 主色、标题装饰、图标 |
| **Primary dark** | `#0D47A1` | 页眉页脚、强调区域 |
| **Accent** | `#FF6D00` | 风险告警强调、关键数据高亮 |
| **Body text** | `#212121` | 正文 |
| **Secondary text** | `#546E7A` | 说明、图注 |
| **Tertiary text** | `#90A4AE` | 页脚、辅助 |
| **Border** | `#CFD8DC` | 分隔线、边框 |
| **Success** | `#2E7D32` | 正向标记 |
| **Warning** | `#C62828` | 风险标记 |

## IV. Typography System

**Typography direction**: contrast — SimHei title + Microsoft YaHei body

| Role | Chinese | English | Fallback |
| ---- | ------- | ------- | -------- |
| **Title** | SimHei | Arial | Microsoft YaHei |
| **Body** | Microsoft YaHei | Arial | sans-serif |
| **Code** | — | Consolas | Courier New |

**Per-role font stacks**:
- Title: `"SimHei", "Microsoft YaHei", sans-serif`
- Body: `"Microsoft YaHei", Arial, sans-serif`
- Code: `"Consolas", "Courier New", monospace`

**Baseline**: Body = 18px (密集型，技术内容多)

## V. Layout Principles

- **Header**: 顶部导航条，包含章节标记和页标题
- **Content**: 根据页面节奏使用卡片网格、流程图、对比表
- **Footer**: 页脚含页码和项目名称

## VI. Icon Usage

Library: `tabler-outline` (stroke=2), consistent line-weight across all pages.

## VII. Content Outline (22 pages)

| # | 页面 | 内容要点 | 节奏 |
|---|------|---------|------|
| P01 | 封面 | 课题名称、答辩人、导师、日期 | anchor |
| P02 | 目录 | 报告结构导航 | breathing |
| P03 | 研究背景 | 三重困难：日志不统一、攻击跨日志、缺乏追踪链路 | dense |
| P04 | 系统目标 | 四项具体目标 + 五步闭环 | breathing |
| P05 | 技术架构总览 | 前后端技术栈 + 四层架构图 | dense |
| P06 | 后端架构详解 | Spring Boot 3, MyBatis-Plus, Redis, RabbitMQ | dense |
| P07 | 前端架构详解 | Vue 3, Vite, Element Plus, ECharts | breathing |
| P08 | 日志标准化模块 | 异构日志统一映射、批次管理、CSV解析 | dense |
| P09 | 检测规则管理 | 规则参数化、版本快照与回滚 | dense |
| P10 | 核心检测引擎(上) | 四类攻击差异化统计逻辑、代码结构 | dense |
| P11 | 核心检测引擎(下) | 事件哈希聚合、eventTime窗口计算、关键决策 | dense |
| P12 | 检测流程全景 | 完整检测流程图 | breathing |
| P13 | 事件告警管理 | 状态机流转、证据链设计、黑名单联动 | dense |
| P14 | 首页仪表盘 | 统计卡片、趋势图、分布图、排行 | dense |
| P15 | 批次报告与回放 | 报告生成、数据回放、CSV导出 | dense |
| P16 | 安全与审计 | JWT认证、角色权限、操作审计过滤器 | dense |
| P17 | 数据库设计 | 11张核心表、ER关系、关联链路 | breathing |
| P18 | 前端页面体系 | 10个页面全景展示 | breathing |
| P19 | 创新点与工作量 | 8个创新点、代码量统计、页面数 | dense |
| P20 | 实验验证 | 四类攻击测试样本与触发效果 | dense |
| P21 | 总结展望 | 完成工作、不足、未来方向 | breathing |
| P22 | 致谢 | 感谢语 | anchor |