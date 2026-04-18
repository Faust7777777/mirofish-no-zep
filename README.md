<div align="center">

<img src="./static/image/MiroFish_logo_compressed.jpeg" alt="MiroFish Logo" width="72%"/>

# MiroFish No-Zep

一个基于原版 MiroFish 改出来的轻量分支。  
现在这版主要服务于哲学文本驱动的社会模拟，尤其是《理想国》相关实验。

[中文](./README.md) | [English](./README-EN.md)

</div>

## 这是什么

这个仓库不是原版 MiroFish 的完整替代品，而是一个为了具体使用场景做出来的重构版。

事情的起点很简单：

- kunkun 是哲学专业学生，想拿 MiroFish 去做苏格拉底《理想国》中的社会模拟。
- 但原版流程里有一部分依赖 Zep Cloud。对于哲学系老师来说，这一步额外配置 API 和云端服务，门槛偏高。
- 所以这次重构的目标就是把这部分拿掉，尽量把项目收敛成“只配一个 LLM API Key 就能跑”的形态。

我本人是大连理工大学电子商务专业大一学生，目标方向是产品经理。这次主要负责：

- 需求整理
- 交互流程收敛
- 产品重构
- 让项目更适合非前沿技术背景的老师和同学使用

最后形成的就是现在这个版本：

> 一个不依赖 Zep、只需要配置 LLM API Key、适合做轻量哲学实验模拟的 MiroFish。

## 这版改了什么

和原版相比，这个分支最重要的变化有几条：

- 去掉了对 Zep Cloud 的主流程依赖
- `USE_ZEP=false` 时，图谱和报告检索走本地文件图谱
- 报告阶段尽量提供本地可退化路径，而不是直接卡死在云端依赖上
- Step 2 的流程更偏“课堂可用”和“实验可调”
- 可以直接在界面里改 Agent 的 `sentiment_bias`

如果你只是想做：

- 哲学课堂演示
- 小规模社会实验
- 本地轻量运行

这个版本会比原版更顺手。

如果你要的是：

- 原版完整能力
- 云端记忆增强
- 更大规模的通用预测场景

那还是应该回到原始仓库。

## 适合什么场景

- 《理想国》相关课程讨论
- 哲学文本驱动的社会模拟
- 思想实验
- 课堂演示
- 不想折腾额外云服务的研究和作业场景

## 现在的基本流程

1. 上传文本材料
2. 生成本体和项目文本
3. 构建本地图谱
4. 生成人设和模拟配置
5. 启动模拟
6. 生成报告
7. 继续和报告或 Agent 交互

## 快速开始

### 环境要求

| 工具 | 版本要求 |
|------|----------|
| Node.js | 18+ |
| Python | 3.11 - 3.12 |
| uv | 最新版 |

> 不建议用 Python 3.13，部分依赖安装会出问题。

### 1. 配置 `.env`

在项目根目录创建 `.env`，最小配置如下：

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o-mini

USE_ZEP=false
PORT=5001
```

说明：

- 这版的推荐运行方式就是 `USE_ZEP=false`
- 只要你的模型接口兼容 OpenAI SDK 格式即可
- 主流程不再要求必须配置 `ZEP_API_KEY`

### 2. 安装依赖

```bash
npm run setup:all
```

如果想分步执行：

```bash
npm run setup
npm run setup:backend
```

### 3. 启动

```bash
npm run dev
```

启动后访问：

- 前端：`http://localhost:3000`
- 后端：`http://localhost:5001`

## 目前保留的核心能力

### 本地图谱

当 `USE_ZEP=false` 时，项目会把文本处理成局部图谱 JSON，用于：

- 图谱查看
- report 检索
- quick search
- panorama search
- 报告阶段的本地退化逻辑

### 场景热配置

Step 2 支持改场景配置，包括：

- 场景名称
- 场景描述
- 触发事件
- 角色列表
- 初始帖子

这让项目不再只适合固定 demo，而可以拿去做别的哲学或社会场景实验。

### Agent 情感倾向可调

Step 2 现在可以直接改并保存：

- `sentiment_bias`

适合做简单对照实验，比如观察不同角色情绪基线变化后，舆论演化会不会发生偏移。

## 项目截图

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

## 和原项目的关系

- 原项目：`666ghj/MiroFish`
- 这个仓库：面向哲学模拟的 No-Zep 轻量重构版

也就是说，这里更像是一个“按教学和实验需求裁剪过的分支”，不是对原项目的一比一介绍页。

## 致谢

- 原开源项目 **MiroFish**
- 多智能体仿真引擎 **[OASIS](https://github.com/camel-ai/oasis)**
- 提出使用场景并推动重构的人：kunkun

## License

沿用原项目许可证，见 [LICENSE](./LICENSE)。
