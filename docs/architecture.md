# System Architecture

The AI Kubernetes Troubleshooting Agent is designed as a modular on-demand incident investigation platform.

## Architecture Pipeline

```text
Frontend (Next.js)
    ↓  (API request)
FastAPI Backend (Orchestration Layer)
    ↓
Kubernetes Investigation Layer (Subprocess kubectl logs / events / configurations)
    ↓
AI Kubernetes Agent (Correlations & prompt synthesis)
    ↓
LLM Reasoning Engine (OpenRouter API via InsForge Key)
    ↓
Root Cause + Suggested Action Plan
    ↓
Frontend Dashboard Presentation
```

## Folder Structure

- `/backend` - FastAPI Python orchestrator.
- `/frontend` - Next.js TypeScript web application.
- `/docs` - System documentation.
- `/prompts` - Engineering instructions and development milestones.
