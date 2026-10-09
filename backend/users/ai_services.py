"""AI plan generation for SmartBudget.

Pipeline (BE-12 / BE-13 / BE-14):
1. All 10 onboarding answers are read from the database.
2. budget_engine.build_plan() calculates 12 separate monthly budgets following
   SmartBudget_AI_Final_System_Prompt.docx and validates every rule
   (balance equation, no negatives, fixed vs variable categories, annual sums).
3. If GROQ_API_KEY is configured, the LLM rewrites the explanation texts
   (status description, plan summary, category recommendations) in friendly
   Azerbaijani. The LLM never changes numbers, so an LLM mistake cannot break
   the mathematics. Without a key / on timeout the rule-based texts are used.
4. The plan is saved and the session status becomes "completed" (Ready).
   Any failure leaves the status "failed" (Error) so the user can retry.
"""

import json
import logging

from django.conf import settings
from django.db import transaction
from django.db.models import F

from .budget_engine import CATEGORY_LABELS, answers_from_session, build_plan
from .models import FinancialInquirySession

logger = logging.getLogger(__name__)


class AIProviderRateLimitError(Exception):
    def __init__(self, retry_after=None):
        self.retry_after = retry_after if retry_after and str(retry_after).isdigit() else None
        super().__init__('AI provider rate limit reached')


def _llm_prompt(plan, answers):
    categories = {
        row["category_key"]: {
            "name": row["category_name"],
            "current": row["current_monthly_amount"],
            "recommended_avg": row["recommended_monthly_amount"],
            "status": row["status"],
        }
        for row in plan["budget_comparison"]
    }
    facts = {
        "monthly_income_azn": plan["reliable_monthly_income"],
        "housing_type": answers.housing_type,
        "credits": answers.credits,
        "goals": [
            {"name": g["goal_name"], "target": g["target_amount"], "priority": g["priority"],
             "monthly": g["recommended_monthly_saving"], "months_to_goal": g["months_to_goal"]}
            for g in plan["savings_goals_breakdown"]
        ],
        "financial_assessment": answers.financial_assessment,
        "monthly_savings_ability": answers.monthly_savings_ability,
        "annual_budget_priority": answers.annual_budget_priority,
        "financial_status": plan["financial_status"],
        "avg_monthly_savings": plan["recommended_monthly_savings"],
        "annual_savings": plan["recommended_annual_savings"],
        "deficit_months": plan["deficit_months"],
        "categories": categories,
    }
    return (
        "You are SmartBudget AI, a friendly Azerbaijani financial advisor. The 12-month budget "
        "below is ALREADY calculated and validated. Do NOT invent or change any number; only use "
        "numbers that appear in the data. Write in plain everyday Azerbaijani.\n\n"
        f"DATA:\n{json.dumps(facts, ensure_ascii=False)}\n\n"
        "Return ONLY a JSON object with these keys:\n"
        '{"financial_status_description": "1 short sentence",\n'
        ' "monthly_budget_plan": "max 3 sentences, must name the annual_budget_priority",\n'
        ' "category_recommendations": {"<category key>": "1 short sentence (max 14 words) matching its status"}}\n'
        "Use exactly the category keys from DATA.categories."
    )


def _polish_texts_with_llm(plan, answers):
    """Optional LLM wording. Returns True if LLM texts were applied."""
    api_key = getattr(settings, 'GROQ_API_KEY', '')
    if not api_key:
        return False
    try:
        from groq import Groq, RateLimitError
    except ImportError:  # pragma: no cover - dependency is in requirements.txt
        return False

    try:
        client = Groq(api_key=api_key, timeout=getattr(settings, 'AI_TIMEOUT_SECONDS', 12), max_retries=0)
        completion = client.chat.completions.create(
            model=getattr(settings, 'GROQ_MODEL', 'llama-3.1-8b-instant'),
            messages=[{"role": "user", "content": _llm_prompt(plan, answers)}],
            max_tokens=1200,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        data = json.loads(completion.choices[0].message.content or "{}")
    except RateLimitError:
        logger.warning("LLM rate-limited; using rule-based texts")
        return False
    except Exception:
        logger.exception("LLM text generation failed; using rule-based texts")
        return False

    if not isinstance(data, dict):
        return False

    def clean(value, limit):
        return value.strip()[:limit] if isinstance(value, str) and value.strip() else None

    applied = False
    desc = clean(data.get("financial_status_description"), 300)
    if desc:
        plan["financial_status_description"] = desc
        applied = True
    summary = clean(data.get("monthly_budget_plan"), 700)
    if summary:
        plan["monthly_budget_plan"] = summary
        applied = True
    recs = data.get("category_recommendations")
    if isinstance(recs, dict):
        for row in plan["budget_comparison"]:
            text = clean(recs.get(row["category_key"]), 200)
            if text:
                row["ai_recommendation"] = text
                applied = True
    return applied


def generate_ai_budget_plan(session_id):
    """Generate, validate and store the plan. Raises on failure (status=failed)."""
    logger.info("Plan generation started for session %s", session_id)
    session = FinancialInquirySession.objects.get(id=session_id)
    try:
        answers = answers_from_session(session)
        plan = build_plan(answers, session.plan_adjustments, session.plan_variant)  # raises PlanValidationError if any rule fails
        plan["text_source"] = "llm" if _polish_texts_with_llm(plan, answers) else "rules"

        with transaction.atomic():
            session.recommended_monthly_savings = plan["recommended_monthly_savings"]
            session.recommended_annual_savings = plan["recommended_annual_savings"]
            session.financial_status = plan["financial_status"]
            session.financial_status_description = plan["financial_status_description"]
            session.ai_response_text = plan["monthly_budget_plan"]
            session.savings_goals_breakdown = plan["savings_goals_breakdown"]
            session.monthly_table = plan["monthly_table"]
            session.annual_totals = plan["annual_totals"]
            session.budget_comparison = plan["budget_comparison"]
            session.plan_text_source = plan["text_source"]
            session.plan_error = ''
            session.status = 'completed'
            session.save()
            FinancialInquirySession.objects.filter(pk=session.pk).update(plan_version=F('plan_version') + 1)
        session.refresh_from_db()
    except Exception as exc:
        logger.exception("Plan generation failed for session %s", session_id)
        FinancialInquirySession.objects.filter(pk=session_id).update(
            status='failed', plan_error=str(exc)[:500]
        )
        raise

    logger.info("Plan generation completed for session %s (version %s, texts: %s)",
                session_id, session.plan_version, plan["text_source"])
    return {"used_fallback": plan["text_source"] != "llm", "plan": plan}


__all__ = ["AIProviderRateLimitError", "generate_ai_budget_plan", "CATEGORY_LABELS"]
