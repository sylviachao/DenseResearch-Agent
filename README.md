# G3: Investment Research Agent with Memory Constraints

## Project Overview
This project implements an Autonomous Investment Research Agent designed to analyze complex financial data, such as NVIDIA earnings and market trends, while operating under strict Memory and Token Constraints. 

The system utilizes a "Pre-process & Summarize" pipeline to ensure high-density information retrieval without exceeding a 2,048 token limit per query.

## Tech Stack
* LLM: Google Gemini 2.5 Flash (Latest Industry Standard)
* Orchestration: Dify.ai (Advanced Chatflow)
* Development: Python 3.10+, Cursor (AI-Pair Programming)
* Libraries: google-generativeai, python-dotenv, requests

## System Architecture: The Buffer and Cascade Strategy

### 1. Adaptive Pre-processing (/scripts/preprocess.py)
* Boundary-Aware Chunking: Uses punctuation backtracking to ensure semantic integrity during text segmentation.
* Metadata Injection: Automatically injects context (e.g., [Nvidia | April 2026]) into every data chunk to maintain retrieval accuracy.
* Atomic Fact Summarization: Employs Gemini 2.5 Flash as a "Data Refiner" to compress raw reports into high-density facts, stripping redundant prose while preserving numerical precision.

### 2. Dify Orchestration (Chatflow)
* Workflow: Located in /dify-exports/workflow_export.yml.
* Retrieval Strategy: Implements N-to-1 Retrieval with top_k: 4, capping the retrieved context to ensure a stable token budget.
* Memory Management: Configured with a 3-turn conversation window to support contextual dialogue without overwhelming the 2,048 token limit.
* Model Tuning: Set with Temperature 0.2 and Top P 0.8 to prioritize factual consistency over creative variance.

## Folder Structure
```text
/binox-g3-agent
├── /dify-exports/
│   └── workflow_export.yml   # Exported Dify DSL (Import this to reproduce)
├── /data/
│   ├── /raw/                 # Raw financial .txt reports
│   └── /processed/           # AI-summarized & chunked .md files
├── /scripts/
│   ├── preprocess.py         # Data Factory: Chunking & Summarizing
│   └── eval_tool.py          # Quality Controller: Latency & Token testing
├── .env.example              # Template for API Keys
├── README.md                 # Setup & Architecture
└── evaluation.md             # Architecture trade-offs & Memory Strategy
```

## Getting Started

### 1. Data Pre-processing
Place your raw .txt files in /data/raw/, then run the ingestion script:
```bash
python scripts/preprocess.py
```
Processed files will be generated in /data/processed/.

### 2. Dify Implementation
1. Import Workflow: Open Dify, go to Studio, click Import DSL, and select dify-exports/workflow_export.yml.
2. Setup Knowledge: Upload files from /data/processed/ to a new Dify Knowledge Base.
3. Configure API: Ensure Google Gemini 2.5 Flash is configured in the Model Provider settings.

### 3. System Evaluation
Update your .env with the DIFY_API_KEY and run:
```bash
python scripts/eval_tool.py
```
The evaluation tool fetches real-time telemetry directly from the Dify/Gemini API metadata, providing exact input/output token counts and verifying that the Knowledge Base chunks are being correctly retrieved.

## Performance Metrics (Actual Results)
| Metric | Result | Status |
| :--- | :--- | :--- |
| **Token Tracking** | API-Native (Metadata) | Precise |
| **Input (Prompt) Tokens** | ~1,200 - 1,600 | Controlled (Top-K: 4 x 400) |
| **Output (Completion) Tokens** | < 512 | Optimized |
| **Total Session Tokens** | < 2,048 | PASSED |
| **Avg. Latency** | ~2.0s | Optimized |

## Evaluation Logic
The `eval_tool.py` validates the G3 constraints by implementing the following:
* **Metadata Extraction**: Pulls actual usage data from the Gemini 2.5 Flash response to ensure 100% accuracy in token reporting.
* **RAG Verification**: Monitors retriever_resources to ensure the agent is strictly grounded in the provided financial data chunks.
* **Cost Calculation**: Provides real-time session cost estimates based on Gemini 2.5 Flash pricing models.


## Future Roadmap
* Local SLM Distillation: Transition from cloud-based preprocessing to local Small Language Models (e.g., Llama 4 or Phi-4) to reduce API costs and enhance data privacy.
* Edge-AI Fact Extraction: Fine-tune local models specifically for financial data scrubbing before cloud synchronization.
* Real-time Scraping: Integrate specialized nodes for automated financial news fetching.
* Multi-Agent Critique: Add a secondary agent to verify retrieved context against the original source.
