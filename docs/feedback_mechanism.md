# Goal: Implement a Scalable LLM Feedback Loop (Continuous Alignment)

This document outlines a scalable, highly efficient strategy for enabling the LLM (Gemini 2.5 Flash) to learn from user feedback (thumbs up / thumbs down) without requiring expensive, time-consuming model fine-tuning.

## Strategy: Dynamic Few-Shot Prompting (RAG for Alignment)

Fine-tuning a massive LLM on every single click is neither scalable nor efficient. Instead, we will use **Dynamic Few-Shot Prompting**. 

When a user submits a claim, we will search our historical database for similar past claims, giving **primary focus to Negative Feedback ("Thumbs Down")**. 

- **Negative Examples (Thumbs Down):** Injected as critical "Anti-Patterns". The system will explicitly instruct the LLM: *“The user hated this response. DO NOT repeat this tone, structure, or content.”*
- **Positive Examples (Thumbs Up):** Used as secondary context for good formatting, but avoiding past mistakes is the top priority.

### The Workflow:
1. **Analysis Caching:** When an analysis is generated, we temporarily cache the `claim`, `chunks`, and `response` in memory using the `analysis_id`.
2. **Feedback Ingestion:** When the user clicks "Helpful" (thumbs up), the `routers/feedback.py` endpoint retrieves the cached data and saves it to a persistent Vector Database (e.g., ChromaDB).
3. **Pre-Synthesis Search:** During a *new* claim analysis, `synthesizer.py` will search the Feedback Vector DB for past claims similar to the current one.
4. **Prompt Injection:** If matching examples are found, they are injected into the Gemini prompt. Positive examples act as few-shot guides, and negative examples act as explicit anti-patterns (e.g., "Do not format your response like this...").

> [!TIP]
> **Why this is efficient & scalable:**
> - **Zero Training Cost:** No GPU compute is wasted on fine-tuning.
> - **Instant Adaptation:** The model learns instantly on the very next query.
> - **Infinite Context:** We only retrieve the top 1-2 most relevant past examples, so the prompt never overflows, keeping latency and token costs extremely low.

---

## Proposed Changes

### 1. Database & Caching Layer

#### [NEW] `src/rx_evidence_engine/db/feedback_store.py`
Create a persistent vector store using **ChromaDB** configured to save to a local `.chroma/` directory on disk.
- Expose methods: `save_feedback(claim, response, is_positive, reason)` and `get_similar_feedback(query_claim)`.

#### [MODIFY] `src/rx_evidence_engine/routers/feedback.py`
- Modify the endpoint to retrieve the original claim and response using `analysis_id`.
- Save both "helpful" and "not_helpful" votes to the `feedback_store`, along with any user-provided reasoning.

### 2. Analysis Caching

#### [MODIFY] `src/rx_evidence_engine/pipeline/orchestrator.py`
- Add a lightweight `TTLCache` (e.g., 24-hour expiration) to temporarily hold the generated `AnalysisResult` keyed by its `id`.
- This ensures that when the user submits feedback an hour later, we know exactly what they are giving feedback on.

### 3. LLM Integration

#### [MODIFY] `src/rx_evidence_engine/pipeline/synthesizer.py`
- Before building the payload for Gemini, query the `feedback_store` for similar past claims.
- If negative examples are found, append a CRITICAL Anti-Pattern block:
  ```text
  CRITICAL INSTRUCTION: Here is a past response that the user explicitly DISLIKED (Anti-Pattern):
  Claim: {past_claim}
  Bad Response: {past_response_json}
  Reason for rejection: {user_reason}
  
  You MUST NOT generate a response like this. Do not repeat its tone, structure, or mistakes. 
  ```
- Positive examples will be appended normally, but below the critical anti-patterns.

---

## Verification Plan

### Automated Tests
- Test `feedback_store.py` to ensure embeddings are successfully saved and retrieved from disk.
- Test `orchestrator.py` to verify the cache correctly links an `analysis_id` to its payload.
- Mock the LLM to verify that past "Thumbs Up" examples are accurately injected into the prompt.

### Manual Verification
- Run the server, analyze a claim, and manually submit a "Thumbs Up" via `curl` or the browser Extension.
- Analyze a similar claim and review the server logs to verify that the cached example was successfully retrieved and passed to the LLM.

