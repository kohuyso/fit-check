---
name: ai-vision-pipeline
description: Best practices for integrating Gemini / OpenAI AI models, Computer Vision image tagging, color matching, and outfit recommendations in FitCheck.
---

# AI & Vision Processing Pipeline Guide

This skill governs the implementation of AI features, multimodal vision models, prompt engineering, and background AI workers in `fitcheck-backend`.

## Core AI Architecture

AI capabilities in FitCheck are organized into two primary service modules:
1. `app/services/ai_engine.py`: Direct LLM/Vision API calls (Google Gemini, OpenAI), prompt formatting, and structured output parsing.
2. `app/services/ai_workers.py`: Celery background tasks for async image processing and queue management.
3. `app/services/color_math.py`: Color analysis, Delta E calculations, and HEX/RGB transformations.

## Key Principles

### 1. Robust Multimodal Vision Analysis
- When processing clothing images, pass either public image URLs or base64 encoded data to vision endpoints.
- Instruct vision models to extract:
  - **Category**: Shirt, Pants, Shoes, Jacket, Accessories, etc.
  - **Dominant Colors**: HEX codes and human-readable names.
  - **Style Tags**: Casual, Formal, Sporty, Streetwear, Vintage, Minimalist.
  - **Season/Weather Suitability**: Summer, Winter, Rain, Hot, Cold.

### 2. Guardrails & Fallbacks
- Always implement defensive JSON parsing when extracting data from AI raw text responses.
- If the AI API call fails or times out, provide a fallback response or default heuristic object to prevent 500 errors on the frontend.
- Mask API keys in diagnostic endpoints (`ai_engine.get_ai_config()`).

### 3. Prompt Engineering Guidelines
- Set system role explicitly: `You are an expert personal fashion stylist AI`.
- Instruct LLMs to return strict JSON without markdown codeblock wrappers if raw JSON parsing is required, or strip ```json wrappers before parsing.
- Provide closet items context clearly formatted (e.g. `ID`, `Category`, `Color`, `Style`).

### 4. Background AI Worker Queues
- For high-latency AI tasks (e.g. batch catalog processing or complex outfit matrix generation), enqueue jobs using Celery tasks defined in `app/services/ai_workers.py`.
