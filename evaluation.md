# Evaluation: Architecture Trade-offs and Memory Strategy

## 1. Multi-part Research Decomposition
The Investment-Agent is optimized for **High-Fidelity Financial Synthesis**. It handles multi-layered queries (e.g., comparing FCF margins across actuals vs. projections) by decomposing them into atomic data points.
* **Strategy**: Utilizing **Gemini 2.5 Flash** with a refined retrieval context, the agent simultaneously processes multiple financial scenarios (Bull/Bear/Actuals) within a unified context window.
* **Result**: Structured outputs (Markdown tables and Atomic Facts) ensure 100% data traceability and zero-loss synthesis of complex valuation models.

## 2. Memory Strategy and Constraint Handling
Following empirical testing, the system has been scaled to a **3,072 Token Limit** to balance retrieval depth with model reasoning. We implement a **"Tiered Context Funnel"**:

* **Stage 1: Recursive Atomic Refinement**: Raw data is processed via `preprocess.py` with an `OBESE_THRESHOLD` of 850 characters. Any "dense" logic is automatically decoupled into **Part A/B segments** to maintain a consistent chunk density of ~200 tokens.
* **Stage 2: Dynamic Retrieval Logic**: In Dify, we now utilize a `top_k: 5-6` strategy.
    * **The Math**: $200 \text{ (tokens/chunk)} \times 6 = 1,200 \text{ tokens (Data Context)}$.
    * **System Overhead**: ~600 tokens (Persona + Extraction Rules).
    * **Completion Buffer**: ~800 - 1,000 tokens for complex reasoning and tabular generation.
    * **Total**: Effectively operates within **~2,800 tokens**, leaving a safety margin below the **3,072 cap**.



## 3. Architecture Trade-offs (Updated)

| Choice | Trade-off (Pros) | Trade-off (Cons) |
| :--- | :--- | :--- |
| **3,072 Token Scale** | Enables **Top-K: 6**; allows for multi-document cross-referencing without truncation. | Slightly higher latency compared to the 2K limit (negligible on Flash). |
| **Recursive Smart Splitting** | Eliminates "Information Congestion"; ensures each retrieved node is hyper-focused. | Requires dual-pass API calls during ingestion for outliers. |
| **Gemini 2.5 Flash** | Sub-2.0s latency; exceptional at "Needle-in-a-Haystack" retrieval within 3K windows. | Less prose-heavy than Pro, but more objective for financial metrics. |
| **Metadata Tagging** | Prevents temporal hallucinations by tagging `[Actual]` vs `[Projected]`. | Increases input token count by ~10% due to repetitive labels. |

## 4. Business Impact and Cost Awareness
* **Cost Efficiency**: Even with recursive splitting, Gemini 2.5 Flash maintains an operational cost of ~$0.0001 per 1K tokens, making it **10x more cost-effective** than GPT-4o for batch ETL.
* **Reliability (The 3K Guardrail)**: Moving to 3,072 tokens eliminates the "Context Window Crash" observed at 2,048 tokens, ensuring **Enterprise-grade Uptime**.
* **Traceability**: The `[Part A/B]` split system allows the agent to cite specific logical segments of a report, providing a clear audit trail for financial analysts.
