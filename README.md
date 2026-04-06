# G3: Investment Research Agent with Memory Constraints

## Project Overview
This project implements an **Autonomous Investment Research Agent** designed to analyze complex financial data (e.g., NVIDIA earnings) while operating under a strict **2,048 Token Limit**. 

The system features a **"Pre-load & Refine"** pipeline that decouples persona-driven prompts from raw data, ensuring high-density information retrieval and factual integrity across multiple research chunks.

## Core Innovation: The Resource-Based Architecture
Unlike standard RAG pipelines, this agent treats prompts as **versioned resources**. 
* **Decoupled Logic**: Separates Persona (research_profile.md) from Domain-Specific Schemas (skills/*.yaml).
* **Budget-Aware Pre-processing**: A dedicated `PromptManager` calculates token overhead at boot-time, preventing context overflow.
* **Dynamic Safety Orchestration**: Automatically adjusts Gemini API safety thresholds (e.g., BLOCK_NONE for Finance) to prevent "False Positive" content blocking during high-density risk data extraction.

## Tech Stack
* **LLM**: Google Gemini 2.5 Flash
* **Orchestration**: Dify.ai (Advanced Chatflow & Knowledge Base)
* **Development**: Python 3.10+, Cursor (AI-Pair Programming)
* **Testing**: Dify API Metadata & Python Requests

---

## Folder Structure
```text
/binox-g3-agent
├── /dify-exports/           # Dify Workflow DSL (Import this to reproduce)
│   └── investment-Agent.yml  
├── /prompts/                # Resource-based prompt storage
│   ├── research_profile.md # Persona & Professional Standards
├── /skills/                 # Domain-specific Extraction Schemas
│   ├── finance_extraction.yaml # Template for Quantitative Financial Rules
│   └── legal_compliance.yaml   # Template for Legal Rules
│   └── tech_stack.yaml         # Template for Tech Stack Rules
├── /data/
│   ├── /raw/                # Input: Raw financial .txt reports
│   └── /processed/          # Output: AI-refined .md facts
├── /scripts/
│   ├── preprocess.py         # Data Factory: Chunking & Summarizing
│   └── eval_tool.py          # Quality Controller: Latency & Token testing
├── .env.example              # Template for API Keys
├── README.md                 # Setup & Architecture
└── evaluation.md             # Architecture trade-offs & Memory Strategy
```

---

## System Architecture

### 1. Data Factory (`/scripts/preprocess.py`)
* **PromptManager**: Loads system prompts once at startup. It performs a **Token Budget Audit**, reporting the estimated "Data Margin" available for each chunk.
* **Decimal-Aware Recursive Splitting**: Uses hierarchical separators (`\n\n` > `\n` > `. `) to protect critical financial decimals (e.g., $369.42) from being severed.
* **Advanced Tail-Merge**: Automatically detects orphaned text fragments (< 800 chars) and merges them backward.
* **Full-Atomic Summarization**: Every chunk is force-refined into a structured list of "Atomic Facts" with **Timeline Isolation** (Actuals vs. Projections).
* **Multi-Domain Skill Injection**: Supports switching between different extraction targets (Finance, Legal, Tech) via modular YAML schemas without altering core code.
* **Safety-First Failover**: Implements candidate-level response validation to handle FINISH_REASON: SAFETY errors gracefully, ensuring pipeline continuity even when processing sensitive financial instruments (Shorts/Options).

### 2. Dify Orchestration (`/dify-exports/`)
* **Workflow DSL**: Optimized `top_k: 4` retrieval strategy, ensuring the total retrieved context stays within ~1,600 tokens.
* **Grounding Metadata**: Injects `[Company | Date]` into every chunk to prevent hallucination.

### 3. Automated Evaluation (`/scripts/eval_tool.py`)
* **Telemetry Extraction**: Pulls actual usage data from the Gemini 2.5 Flash metadata via Dify's API to ensure 100% accuracy in token reporting.
* **RAG Verification**: Monitors `retriever_resources` to ensure the agent is strictly grounded in the provided financial data chunks.

---

## Performance & Evaluation
| Metric | Implementation | Result |
| :--- | :--- | :--- |
| **Input Tokens** | Top-K: 4 x 400 | ~1,200 - 1,600 (Controlled) |
| **Output Tokens** | Fact Summarization | < 512 (Optimized) |
| **Total Session** | Strict 2,048 Cap | **PASSED** |
| **Avg. Latency** | Gemini 2.5 Flash | ~2.0s |

---

## Getting Started

### 1. Configure Prompts
Customize the AI's behavior by editing `/prompts/research_profile.txt`. Keep total characters under 1,200 for optimal performance.

### 2. Ingest Data
Place raw reports in `data/raw/` and run:
```bash
python scripts/preprocess.py
```

### 3. Set Up Dify Orchestration
To reproduce the AI's reasoning and retrieval logic:
1. Import Workflow: Log in to your Dify instance and go to Create from DSL file.
2. Upload: Select /dify-exports/investment-Agent.yml.
3. Connect Knowledge: Create a new Knowledge Base in Dify and upload the .md files from your local data/processed/ folder.
4. Link API: Ensure the workflow is linked to your Gemini 2.5 Flash API key within Dify's settings.

### 3. Run Evaluation
Update your `.env` with the `DIFY_API_KEY` and run:
```bash
python scripts/eval_tool.py
```
The evaluation tool fetches real-time telemetry directly from the Dify/Gemini API metadata, providing exact input/output token counts and verifying that the Knowledge Base chunks are being correctly retrieved.

## Performance Metrics (Updated for Production)
| Metric | Specification | Status |
| :--- | :--- | :--- |
| **Atomic Chunk Size** | 700 Characters (~175 Tokens) | **OPTIMIZED** |
| **System Prompt Overhead** | ~500 Tokens | **STABLE** |
| **Effective Data Margin** | ~1,000 Tokens (Top-K: 4-6) | **HIGH DENSITY** |
| **Truth Grounding** | Mandatory [Actual/Projected] Tagging | **VERIFIED** |
| **Total Session Tokens** | < 2,048 (Avg. 1,850) | **PASSED** |

## Evaluation Logic
The `eval_tool.py` validates the G3 constraints by implementing the following:
* **Metadata Extraction**: Pulls actual usage data from the Gemini 2.5 Flash response to ensure 100% accuracy in token reporting.
* **RAG Verification**: Monitors retriever_resources to ensure the agent is strictly grounded in the provided financial data chunks.
* **Cost Calculation**: Provides real-time session cost estimates based on Gemini 2.5 Flash pricing models.

## Known Issues & Handling
* Safety Filter Triggering (Chunk Skipping):
Symptom: When processing high-volatility financial data (e.g., short positions, complex derivatives), the Gemini API may return FINISH_REASON: SAFETY and block the output.
Handling: The system has implemented an automatic skip mechanism to ensure the pipeline is not interrupted.
Workaround: If forced extraction is required, refer to the Dynamic Safety Settings adjustment suggestions in evaluation.md.

## Future Roadmap
* Local SLM Distillation: Transition from cloud-based preprocessing to local Small Language Models (e.g., Llama 4 or Phi-4) to reduce API costs and enhance data privacy.
* Edge-AI Fact Extraction: Fine-tune local models specifically for financial data scrubbing before cloud synchronization.
* Real-time Scraping: Integrate specialized nodes for automated financial news fetching.
* Multi-Agent Critique: Add a secondary agent to verify retrieved context against the original source.
