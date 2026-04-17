<div align="center">

<img src="./static/image/MiroFish_logo_compressed.jpeg" alt="MiroFish Logo" width="75%"/>

# MiroFish No-Zep

A lightweight refactor of the original **MiroFish** project, focused on philosophy-driven social simulation, especially Plato's *Republic*.

[English](./README.md) | [中文文档](./README-ZH.md)

</div>

## What This Repository Is

This is not a mirror of the original MiroFish repository.  
It is a simplified, scenario-oriented fork built for a specific teaching and research use case.

Background:

- Thales, a philosophy student, wanted to use MiroFish to simulate the society described in Plato's *Republic*.
- To make the system easier for philosophy instructors to use, the Zep-dependent parts were removed, so teachers do not have to manage extra API services or cloud graph memory.
- The product refactor and requirement restructuring were led by a first-year e-commerce student at Dalian University of Technology, with a product-manager-oriented focus on usability and workflow clarity.

The result is a version of MiroFish that aims to be simple:

> configure only an LLM API key, then run lightweight philosophy experiments locally.

## Key Differences from the Original Project

- Removes hard dependency on Zep Cloud.
- Uses local file graphs when `USE_ZEP=false`.
- Keeps the multi-agent simulation and report workflow, but simplifies deployment.
- Optimizes the product flow for philosophy experiments rather than general-purpose "predict anything" branding.
- Makes classroom and small-lab usage more practical.

## Good Fit For

- Plato's *Republic* classroom experiments
- Philosophy text based social simulations
- Small-scale thought experiments
- Teaching demos
- Researchers who want a lighter local workflow without extra graph-memory services

## Workflow

1. Upload source material
2. Build a local graph from the text
3. Generate personas and simulation configuration
4. Run dual-platform social simulation
5. Generate reports from simulation outputs
6. Continue interacting with agents and the report system

## Quick Start

### Requirements

| Tool | Version |
|------|---------|
| Node.js | 18+ |
| Python | 3.11 - 3.12 |
| uv | Latest |

> Python 3.13 is not recommended because some dependencies may fail to build.

### 1. Configure Environment Variables

Create a root `.env` file with the minimum required configuration:

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o-mini

USE_ZEP=false
PORT=5001
```

Notes:

- `USE_ZEP=false` is the intended mode of this fork
- Any OpenAI-compatible LLM endpoint should work
- `ZEP_API_KEY` is no longer required for the main local workflow

### 2. Install Dependencies

```bash
npm run setup:all
```

Or step by step:

```bash
npm run setup
npm run setup:backend
```

### 3. Start the App

```bash
npm run dev
```

Services:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:5001`

## Features

### Local Graph Instead of Zep

When `USE_ZEP=false`, the project uses local graph JSON files for:

- graph retrieval
- report search
- quick search / panorama search
- local report fallback behavior

### Scene Hot Configuration

Step 2 supports editable scene configuration:

- scene name
- scene description
- triggering event
- actor list
- initial posts

This makes the system usable for custom philosophy scenarios instead of one fixed demo world.

### Editable Agent Sentiment Bias

In Step 2, you can directly edit and save:

- `sentiment_bias`

This is useful for adjusting how different characters react to the same event.

## Screenshots

<div align="center">
<table>
<tr>
<td><img src="./static/image/Screenshot/运行截图1.png" alt="Screenshot 1" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图2.png" alt="Screenshot 2" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/运行截图3.png" alt="Screenshot 3" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图4.png" alt="Screenshot 4" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/运行截图5.png" alt="Screenshot 5" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图6.png" alt="Screenshot 6" width="100%"/></td>
</tr>
</table>
</div>

## Relationship to the Original Project

- Original project: `666ghj/MiroFish`
- This repository: a philosophy-oriented, no-Zep refactor

If you want:

- cloud graph memory
- the original large-scale prediction framing
- the full upstream ecosystem

you should refer to the original repository.

If you want:

- local lightweight execution
- philosophy-friendly teaching workflow
- *Republic*-style social experiments

this repository is the better entry point.

## Credits

- Original open-source project: **MiroFish**
- Multi-agent simulation engine: **[OASIS](https://github.com/camel-ai/oasis)**
- Use-case initiator: Thales, a philosophy student
- Product refactor and requirement restructuring: a first-year e-commerce student from Dalian University of Technology

## License

This repository follows the original project license. See [LICENSE](./LICENSE).
