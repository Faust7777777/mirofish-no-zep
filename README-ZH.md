<div align="center">

<img src="./static/image/MiroFish_logo_compressed.jpeg" alt="MiroFish Logo" width="75%"/>

# MiroFish No-Zep

基于原开源项目 **MiroFish** 的轻量重构版。  
面向哲学场景，尤其适合做《理想国》式社会实验模拟。

[English](./README.md) | [中文文档](./README-ZH.md)

</div>

## 项目定位

这个仓库不是原版 MiroFish 的镜像，而是一个面向具体教学与实验场景的重构分支。

重构背景：

- 泰勒斯是哲学专业学生，希望借助 MiroFish 对苏格拉底《理想国》中的社会结构、教育机制与舆论传播进行模拟。
- 为了方便哲学系老师使用，项目移除了原流程中对 Zep Cloud 的依赖，避免额外的 API 配置和云端图谱门槛。
- 我是大连理工大学电子商务专业大一学生，目标方向是产品经理，主要负责这次产品重构、需求整理与交互梳理。

这次重构后的目标很明确：

> 只需要配置 `LLM_API_KEY`，就可以运行一个轻量、可落地的哲学实验模拟版 MiroFish。

## 这版和原版的区别

- 去掉了对 Zep Cloud 的强依赖。
- 在 `USE_ZEP=false` 时，报告检索与图谱搜索走本地文件图谱。
- 环境准备与报告生成更偏向“单机可跑通”的轻量路线。
- 保留了多智能体模拟、报告生成、交互式分析这些核心体验。
- UI 和流程重点服务于《理想国》式哲学实验，而不是广义“预测万物”叙事。

## 适合什么场景

- 《理想国》相关课程讨论
- 哲学文本驱动的社会结构实验
- 小规模思想实验与叙事推演
- 教师课堂演示
- 不想配置复杂图数据库和记忆服务的轻量研究环境

## 当前工作流

1. 上传文本材料，生成本体和项目文本
2. 构建本地图谱
3. 生成人设与模拟配置
4. 启动双平台社会模拟
5. 基于模拟结果生成报告
6. 在报告与 Agent 之间继续交互追问

## 快速开始

### 环境要求

| 工具 | 版本要求 |
|------|----------|
| Node.js | 18+ |
| Python | 3.11 - 3.12 |
| uv | 最新版 |

> 不建议使用 Python 3.13，部分依赖会在安装时失败。

### 1. 配置环境变量

根目录创建 `.env`，最小可用配置如下：

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o-mini

USE_ZEP=false
PORT=5001
```

说明：

- 这版的核心是 `USE_ZEP=false`
- 只要 LLM 兼容 OpenAI SDK 格式即可
- 不再要求必须配置 `ZEP_API_KEY`

### 2. 安装依赖

```bash
npm run setup:all
```

如果你只想分步安装：

```bash
npm run setup
npm run setup:backend
```

### 3. 启动项目

```bash
npm run dev
```

启动后访问：

- 前端：`http://localhost:3000`
- 后端：`http://localhost:5001`

### 4. 使用方式

1. 上传材料并生成项目
2. 进入 Step 2 环境搭建
3. 选择或编辑场景热配置
4. 准备模拟并启动运行
5. 在 Step 4 生成报告

## 功能说明

### 1. 本地图谱替代 Zep

项目会把文本切块后生成本地图谱 JSON，在 `USE_ZEP=false` 时用于：

- 图谱搜索
- 报告检索
- 本地 quick search / panorama search
- 报告阶段的离线采访降级

### 2. 场景热配置

支持在 Step 2 中编辑场景：

- 场景名称
- 场景描述
- 触发事件
- 角色列表
- 初始帖子

这使得项目可以不局限于固定示例，而是转向“任意哲学场景”的轻量实验。

### 3. 可编辑 Agent 情感倾向

在 Step 2 的 Agent 配置卡片中，可以直接修改并保存：

- `sentiment_bias`

用于快速调节不同角色面对事件时的正负倾向。

## 截图

<div align="center">
<table>
<tr>
<td><img src="./static/image/Screenshot/运行截图1.png" alt="截图1" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图2.png" alt="截图2" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/运行截图3.png" alt="截图3" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图4.png" alt="截图4" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/运行截图5.png" alt="截图5" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图6.png" alt="截图6" width="100%"/></td>
</tr>
</table>
</div>

## 仓库说明

- 原项目：`666ghj/MiroFish`
- 本仓库：面向哲学模拟的 No-Zep 重构版

如果你想做的是：

- 云端记忆增强
- 原版大规模预测场景
- 完整保留原项目生态

请直接参考原始仓库。

如果你想做的是：

- 本地轻量运行
- 哲学课堂演示
- 《理想国》式社会实验

这个仓库就是更合适的入口。

## 致谢

- 原开源项目 **MiroFish**
- 多智能体仿真引擎 **[OASIS](https://github.com/camel-ai/oasis)**
- 重构背景提出者：哲学学生“泰勒斯”
- 产品重构与需求整理：大连理工大学电子商务专业学生

## License

本仓库沿用原项目许可证，详见 [LICENSE](./LICENSE)。
