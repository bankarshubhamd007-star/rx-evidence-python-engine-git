"""
pipeline/synthesizer.py — LLM Synthesis Module
================================================
This module uses the OpenRouter API (Gemini 2.5 Flash) to synthesize the retrieved
evidence and evaluate the user's claim.

It enforces a structured JSON output that matches our `AnalysisResult` schema.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
import json_repair

import httpx
from app.http_client import get_client

from app.shared.core.config import settings
from app.shared.models.schemas import AnalysisResult, EvidenceSource, Verdict
from app.shared.core.vector_store import SearchResult
from app.shared.repositories.feedback_repository import feedback_repo

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMSynthesizer:
    """Uses Gemini 2.5 Flash via OpenRouter to evaluate medical claims against evidence."""

    def __init__(self) -> None:
        self.api_key = settings.openrouter_api_key

    async def synthesize(self, claim: str, search_results: list[SearchResult], accuracy_level: str = "medium") -> AnalysisResult:
        """
        Evaluate the claim against the provided search results using the LLM.
        """
        if not self.api_key:
            raise ValueError("OpenRouter API key is missing. Check your .env file.")

        if not search_results:
            # If no evidence was found, we can't verify the claim.
            return AnalysisResult(
                id=uuid.uuid4().hex,
                claim=claim,
                confidence=0.0,
                summary="No relevant medical evidence was found for this claim.",
                key_points=["Insufficient data across all queried providers."],
                evidence=[],
                created_at=time.time(),
            )

        # 1. Format the evidence context for the LLM
        context_parts = []
        for i, res in enumerate(search_results, 1):
            context_parts.append(
                f"--- EVIDENCE {i} ---\n"
                f"Publisher: {res.publisher}\n"
                f"URL: {res.url}\n"
                f"Relevance Score: {res.score}\n"
                f"Text: {res.text}\n"
            )
        evidence_context = "\n".join(context_parts)

        # 2. Build the strict JSON schema instruction
        system_prompt = (
            "You are an expert fact-checker and evidence synthesizer. "
            "Your task is to evaluate a claim strictly based on the provided EVIDENCE. "
            "Do NOT use outside knowledge.\n\n"
            "CRITICAL: The `summary` field MUST strictly begin with either 'Yes.', 'No.', or 'Maybe.' based on whether the claim is accurate, followed by the main reason.\n\n"
            "CONFIDENCE SCORING RUBRIC:\n"
            "Calculate the `confidence` score (0.0 to 1.0) strictly using these rules:\n"
            "- 0.0 to 0.3: Very weak or no direct evidence.\n"
            "- 0.4 to 0.6: Conflicting evidence (some sources support, some contradict).\n"
            "- 0.7 to 0.8: Strong evidence from at least one reputable source.\n"
            "- 0.9 to 1.0: Unanimous medical consensus across multiple high-quality sources.\n\n"
            "You must output valid JSON matching this schema exactly:\n"
            "OUTPUT FORMAT (Strict JSON):\n"
            "{\n"
            '  "confidence": <float between 0.0 and 1.0 based on the rubric>,\n'
            '  "isAccurate": <boolean>,\n'
            '  "summary": "<MUST start with \'Yes.\', \'No.\', or \'Maybe.\' followed by a 2-3 sentence summary in simple English>",\n'
            '  "keyPoints": [\n'
            '    "<summarized bullet point 1 (10-15 words)>",\n'
            '    "<summarized bullet point 2>"\n'
            "  ],\n"
            '  "evidence": [\n'
            "    {\n"
            '      "title": "<title>",\n'
            '      "publisher": "<publisher>",\n'
            '      "url": "<url>",\n'
            '      "stance": "supports" | "contradicts" | "neutral",\n'
            '      "relevance": <float between 0.0 and 1.0>\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "EXAMPLE JSON OUTPUT:\n"
            "{\n"
            '  "confidence": 0.85,\n'
            '  "isAccurate": false,\n'
            '  "summary": "No. While tryptophan is found in turkey and does play a role in sleep, the amount in a typical Thanksgiving meal is not enough to cause drowsiness on its own.",\n'
            '  "keyPoints": [\n'
            '    "Turkey contains tryptophan, an amino acid linked to sleep regulation.",\n'
            '    "Tryptophan is converted into serotonin and melatonin in the brain.",\n'
            '    "Heavy meals can also contribute to post-meal drowsiness."\n'
            "  ],\n"
            '  "evidence": [\n'
            "    {\n"
            '      "title": "Dietary Tryptophan and Sleep",\n'
            '      "publisher": "National Institutes of Health",\n'
            '      "url": "https://pubmed.ncbi.nlm.nih.gov/...",\n'
            '      "stance": "supports",\n'
            '      "relevance": 0.95\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        # 2b. Check feedback_repo for similar claims and inject Dynamic Few-Shot Prompting
        past_examples = ""
        try:
            feedback_items = feedback_repo.get_similar_feedback(claim, top_k=2)
            if feedback_items:
                examples_text = "\n\n--- DYNAMIC ALIGNMENT (USER PREFERENCES) ---\n"
                for item in feedback_items:
                    past_claim = item["claim"]
                    past_response = item["response"]
                    vote = item["vote"]
                    reason = item["reason"]
                    
                    if vote == "helpful":
                        examples_text += (
                            f"\nHere is an example of a past response the user found HIGHLY HELPFUL for a similar claim:\n"
                            f"Claim: {past_claim}\n"
                            f"Ideal Response: {past_response}\n"
                            f"Please match the style, brevity, and tone of this example.\n"
                        )
                    else:
                        examples_text += (
                            f"\nCRITICAL INSTRUCTION: Here is a past response that the user explicitly DISLIKED (Anti-Pattern):\n"
                            f"Claim: {past_claim}\n"
                            f"Bad Response: {past_response}\n"
                            f"Reason for rejection: {reason or 'Not specified'}\n\n"
                            f"You MUST NOT generate a response like this. Do not repeat its tone, structure, or mistakes.\n"
                        )
                past_examples = examples_text
        except Exception as e:
            logger.error(f"Failed to retrieve dynamic feedback examples: {e}")
            
        system_prompt += past_examples

        user_prompt = (
            f"CLAIM TO EVALUATE: {claim}\n\n"
            f"EVIDENCE:\n{evidence_context}\n\n"
            "Analyze the claim against the evidence and return the JSON response."
        )

        # 3. Call the LLM
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "http://localhost",  # Required by OpenRouter
            "X-Title": "RX Evidence Engine",     # Required by OpenRouter
            "Content-Type": "application/json",
        }

        # Determine model to use
        model = settings.llm_model_medium
        if accuracy_level == "low":
            model = settings.llm_model_low
        elif accuracy_level == "high":
            model = settings.llm_model_high
            
        logger.info(f"[Synthesis] Using model '{model}' for accuracy_level '{accuracy_level}'")

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "response_format": {"type": "json_object"}
        }

        # Prioritize ultra-fast hardware (LPUs / Groq / Cerebras) where supported
        payload["provider"] = {
            "order": ["Groq", "Cerebras", "Together"],
            "allow_fallbacks": True
        }

        import time
        start_time = time.time()
        client = get_client()
        try:
            resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.error(f"[Synthesis] API Error (HTTP {resp.status_code}): {resp.text[:200]}")
            resp.raise_for_status()
            data = resp.json()
            
            elapsed = time.time() - start_time
            logger.info(f"[Synthesis] LLM {model} completed in {elapsed:.2f}s")
        except Exception as e:
            logger.error(f"[Synthesis] Failed to communicate with LLM provider: {e}")
            raise

        # 4. Parse the response
        raw_content = data["choices"][0]["message"]["content"].strip()
        
        # Clean up markdown code blocks if the LLM ignored instructions
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        if raw_content.startswith("```"):
            raw_content = raw_content[3:]
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]
        
        raw_content = raw_content.strip()

        try:
            parsed = json_repair.loads(raw_content)
        except Exception as e:
            logger.error(f"Failed to parse LLM response with json_repair. Raw output:\n{raw_content}")
            raise RuntimeError(f"LLM did not return valid JSON: {e}")

        # 5. Build and validate Evidence items individually, dropping invalid ones
        valid_evidence = []
        raw_evidence = parsed.get("evidence", [])
        if isinstance(raw_evidence, list):
            for item in raw_evidence:
                try:
                    if isinstance(item, dict):
                        valid_item = EvidenceSource(**item)
                        valid_evidence.append(valid_item)
                except Exception as e:
                    logger.warning(f"Discarding invalid evidence item from LLM output: {item}. Error: {e}")

        # 6. Build and return the AnalysisResult model
        try:
            return AnalysisResult(
                id=uuid.uuid4().hex,
                claim=claim,
                confidence=float(parsed.get("confidence", 0.0) or 0.0),
                is_accurate=bool(parsed.get("isAccurate", False)),
                summary=str(parsed.get("summary", "No relevant information found.")),
                key_points=parsed.get("keyPoints", []),
                evidence=valid_evidence,
                created_at=time.time(),
                accuracy_level=accuracy_level,
            )
        except Exception as e:
            logger.error(f"Failed to validate AnalysisResult structure. JSON:\n{parsed}")
            raise RuntimeError(f"LLM JSON output failed schema validation: {e}")
