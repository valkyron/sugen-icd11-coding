"""Stage 2A LLM Candidate Reranker.

Reranks top BM25 candidates using gpt-4o-mini (or Anthropic Claude / local endpoint),
enforcing ICD-11 specificity rules (leaf nodes over parents, .Z unspecified for missing details),
with strict budget guards and automatic fallback to Stage 2B.
"""

import json
import os
import re
from coder.budget import GLOBAL_BUDGET
from coder.postprocess import clean_predictions
from coder.local_ranker import rank_local_candidates

SYSTEM_PROMPT = """You are an expert WHO ICD-11 clinical outpatient coder.
Your job is to read a clinical consultation note and select up to 3 most accurate, most specific ICD-11 MMS diagnostic codes from a provided candidate list.

STRICT CODING RULES:
1. Specificity: Always select the most specific code the note supports. A parent code does NOT count when a child code fits.
2. Unspecified (.Z): When the note confirms a disease family but lacks further anatomic or etiology details, choose the .Z (unspecified) child code, NOT the parent category.
3. Exclusions / Negations: Never code conditions that are negated, ruled out, or marked as misdiagnoses (e.g., 'mRDT NEG', 'malaria excluded', 'no fracture').
4. Candidate Constraint: Choose ONLY from the provided candidate codes.
5. Format: Return ONLY a JSON object with key "codes" containing a list of up to 3 codes, best code first. Example: {"codes": ["1F40.Z", "CA40.Z"]}"""


def format_candidate_list(candidates: list[dict]) -> str:
    lines = []
    for i, c in enumerate(candidates[:15], 1):
        status = "[LEAF - Specific]" if c.get("leaf") else "[PARENT - do not select if child fits]"
        if c.get("residual") and c["code"].endswith(".Z"):
            status = "[LEAF - Unspecified .Z]"
        lines.append(f"[{i}] Code: {c['code']} | Title: {c['title']} | Status: {status}")
    return "\n".join(lines)


def get_llm_client():
    """Resolve available LLM client: OpenAI or Anthropic SDK."""
    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_base_url = os.environ.get("OPENAI_BASE_URL")
    openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key, base_url=openai_base_url) if openai_base_url else OpenAI(api_key=openai_key)
            return ("openai", client, openai_model)
        except Exception:
            pass

    if anthropic_key:
        try:
            import anthropic
            anthropic_model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
            return ("anthropic", anthropic.Anthropic(api_key=anthropic_key), anthropic_model)
        except Exception:
            pass

    return (None, None, None)


def rerank_with_llm(
    note_id: str,
    note_text: str,
    candidates: list[dict],
    extracted_info: dict | None = None,
    timeout_secs: float = 6.0,
) -> list[str]:
    """Rerank candidates using LLM if budget and credentials allow, else fallback."""
    # Check budget ceiling first
    if not GLOBAL_BUDGET.can_call():
        return rank_local_candidates(candidates, extracted_info)

    provider, client, model_name = get_llm_client()
    if not client:
        return rank_local_candidates(candidates, extracted_info)

    # Format user prompt
    candidate_text = format_candidate_list(candidates)
    user_prompt = f"""Clinical Note:
\"\"\"{note_text.strip()[:1200]}\"\"\"

Candidate ICD-11 Codes:
{candidate_text}

Task: Output up to 3 best matching codes in ranked order (best first). Return strictly valid JSON: {{"codes": ["CODE1", "CODE2"]}}"""

    try:
        if provider == "openai":
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=60,
                timeout=timeout_secs,
                response_format={"type": "json_object"} if "mini" in model_name or "gpt" in model_name else None,
            )
            # Track budget
            usage = response.usage
            if usage:
                GLOBAL_BUDGET.record_usage(usage.prompt_tokens, usage.completion_tokens, model_name)

            content = response.choices[0].message.content or ""
            data = json.loads(content)
            raw_codes = data.get("codes", [])

        elif provider == "anthropic":
            response = client.messages.create(
                model=model_name,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.0,
                max_tokens=60,
                timeout=timeout_secs,
            )
            if hasattr(response, "usage") and response.usage:
                GLOBAL_BUDGET.record_usage(response.usage.input_tokens, response.usage.output_tokens, model_name)

            content = response.content[0].text if response.content else ""
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                raw_codes = data.get("codes", [])
            else:
                raw_codes = []
        else:
            raw_codes = []

        cleaned = clean_predictions(raw_codes, max_codes=3)
        if cleaned:
            return cleaned

    except Exception:
        # Graceful fallback on network error, invalid JSON, or timeout
        pass

    return rank_local_candidates(candidates, extracted_info)
