"""SmartBudget 12-month planning engine.

Implements the numeric rules of "SmartBudget AI — Final System Prompt":

* 12 individually calculated months (January → December), never one month
  copied 12 times;
* fixed categories: Income, Rent/Housing, mandatory Credit payment;
* variable categories (Restaurants, Entertainment, Food & Groceries, Utilities,
  Transportation, Other Expenses, Savings) are calculated per month from the
  user's own answers, adjusted by explainable seasonal factors (Azerbaijan
  context: New Year, Novruz, summer heat / vacations, winter heating, autumn
  school season, November promotions);
* Income = Housing + Restaurants + Entertainment + Food + Utilities +
  Transportation + Credit + Other + Savings + Remaining Balance (Qalıq).
  Savings = the planned monthly contributions to the user's savings goals
  (priority, deadline, already-saved amount, monthly cash flow). Qalıq is NOT
  forced to 0: it is the mathematical result Income − expenses − Savings;
* deficits are never hidden: discretionary spending and Savings go first,
  then essentials only down to a realistic minimum; if fixed obligations and
  minimum essentials still exceed income, the negative Qalıq is reported and
  the plan is flagged as financially infeasible;
* every plan version has a "variant": a seeded, controlled variation of the
  discretionary trim, the seasonal intensity, per-month amounts and the
  savings capacity, so "Planı yenilə" produces a genuine alternative plan
  (reproducible for the same variant, never extreme);
* annual totals are the SUM of the 12 monthly values.

The numbers are produced here (deterministically for a given variant, so they
can always be validated and reproduced). ai_services.py may ask the LLM to phrase the texts, but the LLM
never changes the numbers.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List

MONTH_NAMES = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "İyun",
    "İyul", "Avqust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr",
]

# Columns of the 12-month table, in the order required by the specification.
TABLE_CATEGORIES = [
    "housing", "restaurant", "entertainment", "food", "utilities",
    "transport", "credit", "other", "savings",
]

CATEGORY_LABELS = {
    "housing": "Kirayə / Yaşayış",
    "food": "Qida və market",
    "restaurant": "Restoran və kafe",
    "entertainment": "Əyləncə",
    "utilities": "Kommunal ödənişlər",
    "transport": "Nəqliyyat",
    "clothing": "Geyim",
    "online_shopping": "Onlayn alış-veriş",
    "other_misc": "Digər xərclər",
    "credit": "Kredit və borclar",
    "savings": "Yığım",
}

# Expense categories collected in Step 6 → planning categories.
# "Other Expenses" in the 12-month table = clothing + online shopping + other.
OTHER_PARTS = ("clothing", "online_shopping", "other_misc")
ESSENTIAL = ("food", "utilities", "transport")
DISCRETIONARY = ("restaurant", "entertainment", "clothing", "online_shopping", "other_misc")

# Seasonal factors (1.0 = a normal month). They are normalised to an average of
# 1.0 per category, so they move money between months without changing the
# yearly budget of the category. Reasons are shown in the monthly notes.
SEASONAL_FACTORS = {
    #               Yan   Fev   Mar   Apr   May   İyn   İyl   Avq   Sen   Okt   Noy   Dek
    "food":        [1.00, 0.95, 1.15, 0.95, 0.95, 1.00, 1.00, 1.00, 1.00, 0.95, 0.95, 1.15],
    "restaurant":  [0.85, 0.95, 1.15, 0.90, 1.00, 1.10, 1.20, 1.20, 0.90, 0.85, 0.90, 1.30],
    "entertainment": [0.90, 0.85, 1.10, 0.90, 1.00, 1.15, 1.30, 1.25, 0.85, 0.80, 0.85, 1.20],
    "utilities":   [1.25, 1.20, 1.05, 0.90, 0.85, 0.95, 1.10, 1.10, 0.90, 0.90, 1.05, 1.20],
    "transport":   [0.95, 0.95, 1.00, 1.00, 1.05, 1.10, 1.15, 1.15, 1.00, 0.95, 0.95, 1.00],
    "clothing":    [0.90, 0.80, 1.15, 1.00, 0.90, 0.95, 0.90, 1.00, 1.25, 0.95, 1.10, 1.20],
    "online_shopping": [0.90, 0.85, 1.10, 0.90, 0.90, 0.95, 0.95, 1.00, 1.00, 0.95, 1.30, 1.25],
    "other_misc":  [0.95, 0.90, 1.20, 0.90, 0.90, 1.00, 1.05, 1.10, 1.10, 0.85, 0.95, 1.10],
}

MONTH_REASONS = [
    "Yeni il bayramından sonrakı ay; qış istiliyi kommunal xərcləri artırır, əyləncə xərcləri azalır.",
    "Sakit qış ayı; kommunal xərclər hələ yüksəkdir, gündəlik xərclər normaldır.",
    "Novruz bayramı və 8 Mart: qida, restoran, hədiyyə və digər xərclər artır, yığım bir qədər azalır.",
    "Bayramdan sonra xərclər sabitləşir, mülayim hava kommunal xərcləri azaldır — yığım artır.",
    "Sabit ay; kommunal xərclər ən aşağı səviyyədədir, yaydan əvvəl yığım artırılır.",
    "Yayın başlanğıcı: əyləncə, restoran və nəqliyyat xərcləri artmağa başlayır.",
    "Yayın ən yüksək xərc ayı: istirahət, səfər, restoran və kondisioner (elektrik) xərcləri artır.",
    "Yay xərcləri davam edir: səfər, əyləncə və elektrik xərcləri yüksəkdir, yığım azalır.",
    "Xərclər normallaşır; dərs ili və payız geyimi xərcləri, səfər xərcləri azalır.",
    "Sakit payız ayı: qeyri-vacib xərclər azalır, yığım bərpa olunur.",
    "Noyabr endirimləri (11.11, Black Friday) və ilsonu hazırlıq: alış-veriş bir qədər artır.",
    "Yeni il: hədiyyələr, bayram süfrəsi, restoran və əyləncə xərcləri artır, qış kommunalı yüksəkdir.",
]

PRIORITY_REDUCTION = {
    "Daha çox qənaət etmək": 0.20,
    "Xərclərə nəzarət etmək": 0.15,
    "Borcları azaltmaq": 0.15,
    "Gələcək üçün pul toplamaq": 0.15,
    "Gözlənilməz xərclərə hazır olmaq": 0.10,
    "Gəliri daha düzgün bölüşdürmək": 0.05,
}
ASSESSMENT_REDUCTION = {"good_manager": 0.0, "sometimes_breaks_plan": 0.05, "nothing_left": 0.10}
SAVINGS_ABILITY_REDUCTION = {"can_save": 0.05, "sometimes": 0.0, "cannot_save": -0.05}

# Savings capacity: the largest share of a month's free money
# (income - housing - credit - expenses) that may be planned as Savings.
# The rest always stays as Qalıq, so Savings never swallow everything.
SAVINGS_SHARE_BY_PRIORITY = {
    "Daha çox qənaət etmək": 0.92,
    "Gələcək üçün pul toplamaq": 0.90,
    "Borcları azaltmaq": 0.86,
    "Xərclərə nəzarət etmək": 0.87,
    "Gəliri daha düzgün bölüşdürmək": 0.84,
    "Gözlənilməz xərclərə hazır olmaq": 0.80,  # wants more cash at hand
}
SAVINGS_SHARE_ABILITY = {"can_save": 0.03, "sometimes": 0.0, "cannot_save": -0.05}
SAVINGS_SHARE_ASSESSMENT = {"good_manager": 0.02, "sometimes_breaks_plan": -0.02, "nothing_left": -0.03}

# When the goals' required contributions leave spare capacity, this share of
# the spare money speeds up unfinished goals; the rest stays free as Qalıq.
ACCELERATION_BY_PRIORITY = {
    "Daha çox qənaət etmək": 0.60,
    "Gələcək üçün pul toplamaq": 0.55,
    "Xərclərə nəzarət etmək": 0.45,
    "Gəliri daha düzgün bölüşdürmək": 0.40,
    "Borcları azaltmaq": 0.35,
    "Gözlənilməz xərclərə hazır olmaq": 0.35,
}
ACCELERATION_ABILITY = {"can_save": 0.10, "sometimes": 0.0, "cannot_save": -0.20}
GOAL_PRIORITY_BOOST = {"Yuxarı prioritet": 1.15, "Orta prioritet": 1.05, "Aşağı prioritet": 1.0}
DEFAULT_GOAL_DEADLINE_MONTHS = 12
# Food / utilities / transport may be reduced to this share of the planned
# amount in a deficit month, never lower (realistic minimum living costs).
ESSENTIAL_MINIMUM_SHARE = 0.80
# In a normal (feasible) month seasonal variation never takes food, utilities
# or transport below this share of what the user said they really spend.
ESSENTIAL_SEASONAL_FLOOR = 0.90

GOAL_LABELS = {
    "emergency": "Fövqəladə hallar üçün ehtiyat fondu",
    "travel": "Səyahət",
    "home": "Ev almaq",
    "car": "Avtomobil almaq",
    "education": "Təhsil",
    "business": "Biznes qurmaq",
    "wedding": "Toy",
    "other": "Digər",
}
PRIORITY_WEIGHT = {"Yuxarı prioritet": 3, "Orta prioritet": 2, "Aşağı prioritet": 1}
LONG_TERM_GOALS = {"home", "education", "business"}


# Dashboard columns the user may change before "Planı yenilə" (US-17).
ADJUSTABLE_CATEGORIES = ("restaurant", "entertainment", "food", "utilities", "transport", "other",
                         "clothing", "online_shopping", "other_misc", "savings")


def normalize_adjustments(adjustments) -> Dict:
    """[{month_index: 1..12, category, value}, ...] -> {(month_index0, category): value}."""
    result = {}
    for item in adjustments or []:
        try:
            month = int(item["month_index"]) - 1
            category = str(item["category"])
            value = float(item["value"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= month < 12 and category in ADJUSTABLE_CATEGORIES and value >= 0:
            result[(month, category)] = round(value)
    return result


class PlanValidationError(Exception):
    """Raised when a generated plan breaks one of the mandatory rules."""


@dataclass
class Answers:
    salary: float
    extra_income: float = 0.0
    housing_type: str = ""
    housing_amount: float = 0.0
    credits: List[Dict] = field(default_factory=list)  # monthly, remaining, rate, months
    expenses: Dict[str, float] = field(default_factory=dict)  # Step 6 keys
    recurring: Dict[str, bool] = field(default_factory=dict)
    goals: List[Dict] = field(default_factory=list)  # goal_id, custom_name, priority, amount
    financial_assessment: str = ""
    monthly_savings_ability: str = ""
    annual_budget_priority: str = ""


def answers_from_session(session) -> Answers:
    """Collect all 10 onboarding answers stored for a FinancialInquirySession."""
    f = lambda v: float(v or 0)  # noqa: E731
    return Answers(
        salary=f(session.salary),
        extra_income=f(session.extra_income) if session.has_extra_income else 0.0,
        housing_type=session.housing_type or "",
        housing_amount=f(session.housing_amount) if session.housing_type in ("Kirayədir", "İpotekadır") else 0.0,
        credits=[
            {"monthly": f(c.monthly), "remaining": f(c.remaining), "rate": f(c.rate), "months": int(c.months or 0)}
            for c in session.credits.all()
        ] if session.has_credit else [],
        expenses={
            "food": f(session.expense_market),
            "utilities": f(session.expense_utilities),
            "transport": f(session.expense_transport),
            "restaurant": f(session.expense_restaurant),
            "clothing": f(session.expense_clothing),
            "entertainment": f(session.expense_entertainment),
            "online_shopping": f(session.expense_online_shopping),
            "other_misc": f(session.expense_other),
        },
        recurring={
            "food": session.recurring_market,
            "utilities": session.recurring_utilities,
            "transport": session.recurring_transport,
            "restaurant": session.recurring_restaurant,
            "clothing": session.recurring_clothing,
            "entertainment": session.recurring_entertainment,
            "online_shopping": session.recurring_online_shopping,
            "other_misc": session.recurring_other,
        },
        goals=[
            {"id": g.id, "goal_id": g.goal_id, "custom_name": g.custom_name or "", "priority": g.priority,
             "amount": f(g.amount), "saved": f(g.saved_amount),
             "deadline": int(g.deadline_months or DEFAULT_GOAL_DEADLINE_MONTHS)}
            for g in session.savings_goals.order_by("id")
        ],
        financial_assessment=session.financial_assessment or "",
        monthly_savings_ability=session.monthly_savings_ability or "",
        annual_budget_priority=session.annual_budget_priority or "",
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _r2(value: float) -> float:
    return round(value + 0.0, 2)


def _money(value: float) -> str:
    return f"{round(value):,}".replace(",", " ") + " AZN"


def _seasonal_factors(category: str, answers: Answers, rng=None, intensity: float = 1.0) -> List[float]:
    base = list(SEASONAL_FACTORS[category])
    has_travel_goal = any(g["goal_id"] == "travel" for g in answers.goals)
    if has_travel_goal and category in ("entertainment", "transport", "other_misc"):
        # The user plans to travel: summer travel costs are expected to be higher.
        for i in (6, 7):
            base[i] += 0.10
    damp = 0.5 if answers.recurring.get(category) else 1.0  # recurring → steadier
    factors = [1.0 + (f - 1.0) * damp * intensity for f in base]
    if rng is not None:
        # Controlled per-month variation of an alternative plan version:
        # essentials ±3 %, discretionary ±8 % (halved for recurring expenses).
        spread = (0.03 if category in ESSENTIAL else 0.08) * damp
        factors = [f * (1 + rng.uniform(-spread, spread)) for f in factors]
    mean = sum(factors) / 12
    return [f / mean for f in factors]


def _reduction_rate(answers: Answers, income: float, current: Dict[str, float]) -> float:
    rate = PRIORITY_REDUCTION.get(answers.annual_budget_priority, 0.05)
    rate += ASSESSMENT_REDUCTION.get(answers.financial_assessment, 0.0)
    rate += SAVINGS_ABILITY_REDUCTION.get(answers.monthly_savings_ability, 0.0)
    discretionary = sum(current[c] for c in DISCRETIONARY)
    if income > 0 and discretionary / income > 0.30:
        rate += 0.10  # discretionary spending clearly too high
    return max(0.0, min(rate, 0.40))


def _credit_for_month(credits: List[Dict], month_index: int) -> float:
    """Mandatory payment for a month. Payments stop after the remaining months."""
    total = 0.0
    for c in credits:
        months_left = int(c.get("months") or 0)
        if months_left <= 0 or month_index < months_left:
            total += float(c.get("monthly") or 0)
    return total


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------

def build_plan(answers: Answers, adjustments=None, variant: int = 0) -> Dict:
    """Calculate the 12-month plan.

    1. Planned expenses of each month (seasonal, user's answers, manual
       ``adjustments``, deficit rules).
    2. Free money of each month is allocated to the savings goals
       (priority, deadline, already-saved amount, monthly cash flow) within
       the savings capacity -> Savings.
    3. Qalıq = Income − expenses − Savings (never forced to 0).

    ``variant`` selects a controlled alternative of the plan (0 = no variation).
    The same answers + adjustments + variant always give the same plan.
    """
    rng = random.Random(1_000_003 * variant + 7) if variant else None
    adjusted = normalize_adjustments(adjustments)
    income = _r2(answers.salary + answers.extra_income)
    if income <= 0:
        raise PlanValidationError("Gəlir 0-dan böyük olmalıdır.")

    housing = _r2(answers.housing_amount)
    current = {k: float(answers.expenses.get(k, 0) or 0) for k in ESSENTIAL + DISCRETIONARY}
    current_credit = _credit_for_month(answers.credits, 0)

    # Recommended monthly base per category (expense optimisation, §24):
    # essentials stay as the user reported, discretionary spending is trimmed
    # according to the user's priority, habits and savings ability.
    reduction = _reduction_rate(answers, income, current)
    intensity = 1.0
    if rng is not None:
        reduction = max(0.0, min(0.40, reduction + rng.uniform(-0.04, 0.04)))
        intensity = rng.uniform(0.85, 1.25)
    recommended_base = {}
    for cat in ESSENTIAL:
        recommended_base[cat] = current[cat]
    for cat in DISCRETIONARY:
        recommended_base[cat] = current[cat] * (1 - reduction)
    factors = {cat: _seasonal_factors(cat, answers, rng, intensity) for cat in ESSENTIAL + DISCRETIONARY}

    savings_share = (SAVINGS_SHARE_BY_PRIORITY.get(answers.annual_budget_priority, 0.85)
                     + SAVINGS_SHARE_ABILITY.get(answers.monthly_savings_ability, 0.0)
                     + SAVINGS_SHARE_ASSESSMENT.get(answers.financial_assessment, 0.0))
    acceleration = (ACCELERATION_BY_PRIORITY.get(answers.annual_budget_priority, 0.40)
                    + ACCELERATION_ABILITY.get(answers.monthly_savings_ability, 0.0))
    if rng is not None:
        savings_share += rng.uniform(-0.03, 0.03)
        acceleration += rng.uniform(-0.08, 0.08)
    savings_share = max(0.70, min(0.95, savings_share))
    acceleration = max(0.0, min(0.80, acceleration))

    # ---- 1) planned expenses of every month -------------------------------
    months = []
    for i, name in enumerate(MONTH_NAMES):
        credit = _r2(_credit_for_month(answers.credits, i))
        planned = {cat: round(recommended_base[cat] * factors[cat][i]) for cat in ESSENTIAL + DISCRETIONARY}
        for cat in ESSENTIAL:  # realistic minimum living costs
            planned[cat] = max(planned[cat], round(current[cat] * ESSENTIAL_SEASONAL_FLOOR))
        changed = []
        savings_target = None
        for (month, category), value in adjusted.items():
            if month != i:
                continue
            changed.append(category)
            if category == "savings":
                savings_target = float(value)  # user's own monthly Savings amount
            elif category == "other":
                parts_total = sum(planned[c] for c in OTHER_PARTS)
                if parts_total > 0:
                    for c in OTHER_PARTS[:-1]:
                        planned[c] = round(value * planned[c] / parts_total)
                    planned[OTHER_PARTS[-1]] = int(value) - sum(planned[c] for c in OTHER_PARTS[:-1])
                else:
                    planned["clothing"] = planned["online_shopping"] = 0
                    planned["other_misc"] = int(value)
            else:
                planned[category] = int(value)

        # Amounts the user set by hand are never reduced by the deficit rules.
        locked = set(OTHER_PARTS) if "other" in changed else set()
        locked |= {c for c in changed if c in ESSENTIAL + DISCRETIONARY}
        available = income - housing - credit
        notes = []

        # §26 deficit rules — step 1: non-essential spending (Savings are
        # planned later from the free money, so they are already 0 here).
        if sum(planned.values()) > available:
            _cut(planned, [c for c in DISCRETIONARY if c not in locked], sum(planned.values()) - available, {})
            notes.append("Bu ay qeyri-vacib xərclər (restoran, əyləncə, digər) gəlirə uyğunlaşdırmaq üçün azaldılıb.")
        # step 2: essentials only down to a realistic minimum
        if sum(planned.values()) > available:
            floors = {c: round(planned[c] * ESSENTIAL_MINIMUM_SHARE) for c in ESSENTIAL}
            _cut(planned, [c for c in ESSENTIAL if c not in locked], sum(planned.values()) - available, floors)
            notes.append("Qida, kommunal və nəqliyyat realistik minimuma endirilib.")

        free = _r2(available - sum(planned.values()))
        row = {
            "month_index": i + 1,
            "month_name": name,
            "income": income,
            "housing": housing,
            "restaurant": float(planned["restaurant"]),
            "entertainment": float(planned["entertainment"]),
            "food": float(planned["food"]),
            "utilities": float(planned["utilities"]),
            "transport": float(planned["transport"]),
            "credit": credit,
            "clothing": float(planned["clothing"]),
            "online_shopping": float(planned["online_shopping"]),
            "other_misc": float(planned["other_misc"]),
            "other": float(planned["clothing"] + planned["online_shopping"] + planned["other_misc"]),
            "free": free,
            "_notes": notes,
            "_savings_target": savings_target,
        }
        if changed:
            row["adjusted"] = sorted(set(changed))
        months.append(row)

    # ---- 2) savings goals share one budget --------------------------------
    goal_state, contributions = _allocate_goals(answers, months, savings_share, acceleration)

    # ---- 3) Savings and Qalıq ----------------------------------------------
    labels = {"food": "qida", "restaurant": "restoran", "entertainment": "əyləncə",
              "utilities": "kommunal", "transport": "nəqliyyat", "other": "digər xərclər",
              "clothing": "geyim", "online_shopping": "onlayn alış-veriş", "other_misc": "digər", "savings": "yığım"}
    for i, m in enumerate(months):
        free = m.pop("free")
        notes = m.pop("_notes")
        target = m.pop("_savings_target")
        m["goal_contributions"] = [_r2(c[i]) for c in contributions]
        if goal_state:
            m["savings"] = _r2(sum(m["goal_contributions"]))
        elif target is not None:
            m["savings"] = _r2(max(0.0, min(target, free)))
        else:
            m["savings"] = _general_savings(free, savings_share, acceleration)
        m["balance"] = _r2(free - m["savings"])
        if m["balance"] < 0:
            notes.append(
                "Büdcə bu ay mümkün deyil: məcburi ödənişlər və minimum vacib xərclər gəliri "
                f"{_money(-m['balance'])} aşır. Yığım 0-dır; gəliri artırmaq və ya öhdəlikləri azaltmaq lazımdır."
            )
        if m.get("adjusted"):
            notes.insert(0, f"Bu ay sizin dəyişdirdiyiniz məbləğlər nəzərə alınıb ({', '.join(labels[c] for c in m['adjusted'])}).")
        m["note"] = _month_note(i, m, months[i - 1] if i else None, " ".join(notes), answers)

    annual = {"total_income": _r2(sum(m["income"] for m in months))}
    for key in TABLE_CATEGORIES + list(OTHER_PARTS) + ["balance"]:
        annual[f"total_{key}"] = _r2(sum(m[key] for m in months))
    annual["net_annual_balance"] = annual["total_balance"]

    avg_savings = annual["total_savings"] / 12
    deficit_months = [m["month_name"] for m in months if m["balance"] < 0]
    status, status_desc = _financial_status(income, housing, current_credit, recommended_base, avg_savings, deficit_months, months)
    goals = _goal_summary(goal_state, contributions)

    plan = {
        "reliable_monthly_income": income,
        "current_total_monthly_expenses": _r2(sum(current.values()) + housing + current_credit),
        "recommended_monthly_savings": _r2(avg_savings),
        "recommended_annual_savings": annual["total_savings"],
        "financial_status": status,
        "financial_status_description": status_desc,
        "monthly_table": months,
        "annual_totals": annual,
        "budget_comparison": _comparison(income, housing, current, current_credit, months, answers),
        "savings_goals_breakdown": goals,
        "deficit_months": deficit_months,
        "is_feasible": not deficit_months,
        "goal_warnings": [g["note"] for g in goals if not g["on_track"]],
        "reduction_rate": reduction,
        "variant": variant,
    }
    plan["monthly_budget_plan"] = _summary_text(plan, answers)
    validate_plan(plan, answers, {category for (_, category) in adjusted})
    return plan


def _cut(planned, categories, gap, floors):
    """Reduce ``categories`` by ``gap`` AZN in proportion to what each can give
    (never below its floor; whole AZN)."""
    room = {c: max(0, planned[c] - floors.get(c, 0)) for c in categories}
    total = sum(room.values())
    if gap <= 0 or total <= 0:
        return
    if gap >= total:
        for c in room:
            planned[c] -= room[c]
        return
    taken = 0
    for c in room:
        take = min(room[c], int(room[c] * gap / total))
        planned[c] -= take
        room[c] -= take
        taken += take
    # whole-AZN rounding rest, from the categories with most room left
    for c in sorted(room, key=room.get, reverse=True):
        if taken >= gap:
            break
        take = min(room[c], int(-(-(gap - taken) // 1)))
        planned[c] -= take
        taken += take


def _general_savings(free, savings_share, acceleration):
    """Savings when the user has no goals: a planned part of the free money."""
    if free <= 0:
        return 0.0
    return float(int(free * savings_share * max(acceleration, 0.5)))


def _allocate_goals(answers: Answers, months, savings_share, acceleration):
    """Monthly contributions of every goal, sharing one budget.

    * required monthly average = (target − already saved) / months to deadline
      (guidance only);
    * this month's demand = required average × priority boost × cash-flow
      factor (quiet months give more, expensive months less);
    * if the demands exceed this month's savings capacity, the capacity is
      shared by priority and deadline urgency;
    * spare capacity partly speeds up unfinished goals (by priority), the rest
      stays as Qalıq;
    * a goal stops receiving money once it is reached; already-saved amounts
      are kept as the starting point.
    """
    goals = []
    for g in answers.goals:
        target = float(g["amount"] or 0)
        saved = min(float(g.get("saved") or 0), target)
        goals.append({**g, "target": target, "saved": saved, "start_remaining": max(0.0, target - saved),
                      "remaining": max(0.0, target - saved),
                      "deadline": max(1, int(g.get("deadline") or DEFAULT_GOAL_DEADLINE_MONTHS)),
                      "weight": PRIORITY_WEIGHT.get(g.get("priority"), 2),
                      "boost": GOAL_PRIORITY_BOOST.get(g.get("priority"), 1.0)})
    contributions = [[0.0] * 12 for _ in goals]
    if not goals:
        return goals, contributions

    positive = [m["free"] for m in months if m["free"] > 0]
    avg_free = sum(positive) / len(positive) if positive else 0.0
    for i, m in enumerate(months):
        if m["free"] <= 0:
            continue
        capacity = m["free"] * savings_share
        target = m.get("_savings_target")
        if target is not None:
            # the user set this month's Savings: use it (never above the free money)
            capacity = max(0.0, min(target, m["free"]))
        cash_factor = max(0.6, min(1.4, m["free"] / avg_free)) if avg_free else 1.0
        open_goals = [k for k, g in enumerate(goals) if g["remaining"] > 0.005]
        if not open_goals:
            continue
        demand, urgency, required = {}, {}, {}
        for k in open_goals:
            g = goals[k]
            months_left = g["deadline"] - i
            required[k] = min(g["remaining"], g["remaining"] / months_left if months_left >= 1 else g["remaining"])
            if months_left <= 1:
                demand[k] = g["remaining"]  # deadline month (or overdue): try to finish
            else:
                demand[k] = min(g["remaining"], required[k] * g["boost"] * cash_factor)
            urgency[k] = g["weight"] * (12 / max(1, min(months_left, 60)) if months_left >= 1 else 24)
        if sum(demand.values()) <= capacity:
            give = dict(demand)
        else:
            # Not enough for everyone: first cover the required monthly amount
            # of goals in priority / deadline order, then share what is left.
            # The priority pass may use at most 75 % of the capacity when several
            # goals compete, so lower-priority goals still receive a share.
            give = {k: 0.0 for k in open_goals}
            first_pass = capacity * (0.75 if len(open_goals) > 1 else 1.0)
            for k in sorted(open_goals, key=lambda k: (-goals[k]["weight"], goals[k]["deadline"])):
                take = min(required[k], first_pass)
                give[k] = take
                first_pass -= take
            left = capacity - sum(give.values())
            if left > 0.005:
                extra = _water_fill(left, {k: demand[k] - give[k] for k in open_goals}, urgency)
                for k, v in extra.items():
                    give[k] += v
        spare = capacity - sum(give.values())
        month_acceleration = 1.0 if target is not None else acceleration
        if spare > 1 and month_acceleration > 0:
            extra_room = {k: goals[k]["remaining"] - give[k] for k in open_goals if goals[k]["remaining"] - give[k] > 0.005}
            extra = _water_fill(spare * month_acceleration, extra_room, {k: goals[k]["weight"] for k in extra_room})
            for k, v in extra.items():
                give[k] += v
        for k, v in give.items():
            amount = float(int(v))  # whole AZN
            if goals[k]["remaining"] - amount < 1:
                amount = _r2(min(v, goals[k]["remaining"]))  # finish the goal exactly
                if goals[k]["remaining"] - amount < 1:
                    amount = _r2(goals[k]["remaining"])
            amount = min(amount, goals[k]["remaining"])
            contributions[k][i] = amount
            goals[k]["remaining"] = _r2(goals[k]["remaining"] - amount)
        if target is not None:
            # the user's own Savings amount: put the whole-AZN rounding rest on
            # the goals that still need money, so Yığım matches it exactly
            rest = _r2(capacity - sum(contributions[k][i] for k in range(len(goals))))
            for k in sorted(open_goals, key=lambda k: -goals[k]["weight"]):
                if rest <= 0.005:
                    break
                add = min(rest, goals[k]["remaining"])
                contributions[k][i] = _r2(contributions[k][i] + add)
                goals[k]["remaining"] = _r2(goals[k]["remaining"] - add)
                rest = _r2(rest - add)
        # safety: never above capacity after rounding
        total = sum(contributions[k][i] for k in range(len(goals)))
        if total > capacity + 0.01:
            raise PlanValidationError(f"{m['month_name']}: məqsəd ödənişləri yığım imkanını aşır.")
    return goals, contributions


def _water_fill(budget, caps, weights):
    """Split ``budget`` by ``weights`` without giving anyone more than ``caps``."""
    result = {k: 0.0 for k in caps}
    open_keys = [k for k in caps if caps[k] > 0]
    remaining = budget
    while remaining > 0.005 and open_keys:
        total_w = sum(weights[k] for k in open_keys) or len(open_keys)
        spent, still = 0.0, []
        for k in open_keys:
            share = remaining * (weights[k] or 1) / total_w
            room = caps[k] - result[k]
            give = min(share, room)
            result[k] += give
            spent += give
            if caps[k] - result[k] > 0.005:
                still.append(k)
        remaining -= spent
        if spent < 0.005:
            break
        open_keys = still
    return result


def _goal_summary(goal_state, contributions) -> List[Dict]:
    result = []
    for g, contrib in zip(goal_state, contributions):
        planned = _r2(sum(contrib))
        target, saved, deadline = g["target"], g["saved"], g["deadline"]
        projected = _r2(min(target, saved + planned))
        start_remaining = g["start_remaining"]
        required_avg = start_remaining / deadline if deadline else start_remaining
        avg = planned / 12
        if start_remaining <= 0.005:
            completion = 0
        elif g["remaining"] <= 0.005:
            running, completion = saved, None
            for idx, c in enumerate(contrib):
                running += c
                if running >= target - 0.005:
                    completion = idx + 1
                    break
        elif avg > 0:
            completion = 12 + -(-g["remaining"] // avg)  # ceil
        else:
            completion = None
        if deadline <= 12:
            at_deadline = min(target, saved + sum(contrib[:deadline]))
        else:
            at_deadline = min(target, saved + planned + avg * (deadline - 12))
        on_track = at_deadline >= target - 0.5
        name = g["custom_name"] if g["goal_id"] == "other" and g["custom_name"] else GOAL_LABELS.get(g["goal_id"], g["goal_id"])
        if start_remaining <= 0.005:
            note = "Bu məqsəd üçün lazım olan məbləğ artıq yığılıb."
        elif on_track and completion is not None and completion <= 12:
            note = f"Məqsədə təxminən {completion} ayda çatılır (müddət: {deadline} ay)."
        elif on_track:
            note = f"Plan üzrə məqsədə {deadline} aylıq müddətdə çatmaq mümkündür."
        elif completion:
            note = (f"{deadline} ay ərzində tam yığmaq mümkün deyil: müddətin sonunda təxminən "
                    f"{_money(at_deadline)} olacaq. Real müddət ≈ {int(completion)} ay.")
        else:
            note = (f"{deadline} ay ərzində tam yığmaq mümkün deyil: hazırkı büdcədə bu məqsədə vəsait qalmır. "
                    "Hədəfi, müddəti və ya xərcləri dəyişməyi düşünün.")
        result.append({
            "id": g.get("id"),
            "goal_id": g["goal_id"],
            "goal_name": name,
            "target_amount": _r2(target),
            "saved_amount": _r2(saved),
            "current_amount": _r2(saved),  # progress already accumulated (kept when goals are added)
            "progress_percentage": _r2(saved / target * 100 if target else 0.0),
            "planned_contribution_12m": planned,
            "projected_amount_12m": projected,
            "projected_progress_percentage": _r2(projected / target * 100 if target else 0.0),
            "monthly_contributions": [_r2(c) for c in contrib],
            "recommended_monthly_saving": _r2(avg),
            "required_monthly_average": _r2(required_avg),
            "deadline_months": deadline,
            "months_to_goal": int(completion) if completion is not None else None,
            "expected_amount_at_deadline": _r2(at_deadline),
            "on_track": bool(on_track),
            "is_realistic": bool(on_track),
            "priority": g.get("priority"),
            "note": note,
        })
    return result


# ---------------------------------------------------------------------------
# texts (deterministic defaults; the LLM may rephrase them)
# ---------------------------------------------------------------------------

def _month_note(i, row, prev, extra_note, answers: Answers) -> str:
    parts = [MONTH_REASONS[i]]
    if prev is not None and prev["credit"] != row["credit"]:
        parts.append(f"Kredit ödənişi bitdi: aylıq kredit {_money(prev['credit'])} → {_money(row['credit'])}.")
    if i in (6, 7) and any(g["goal_id"] == "travel" for g in answers.goals):
        parts.append("Səyahət məqsədiniz nəzərə alınıb.")
    if extra_note:
        parts.append(extra_note)
    parts.append(f"Yığım: {_money(row['savings'])}.")
    if row["balance"] > 0:
        parts.append(f"Qalıq (sərbəst pul): {_money(row['balance'])}.")
    return " ".join(parts)


def _financial_status(income, housing, credit, base, avg_savings, deficit_months, months):
    obligations = housing + credit
    essentials = sum(base[c] for c in ESSENTIAL)
    savings_rate = avg_savings / income if income else 0
    if deficit_months:
        worst = min(m["balance"] for m in months)
        return ("Risklidir",
                "Büdcə mövcud gəlir və öhdəliklərlə mümkün deyil: məcburi ödənişlər və minimum vacib xərclər "
                f"gəliri ayda {_money(-worst)}-a qədər aşır. Gəliri artırmaq və ya öhdəlikləri azaltmaq lazımdır.")
    if obligations + essentials >= income:
        return "Risklidir", "Vacib xərclər və öhdəliklər gəlirin demək olar ki, hamısını tutur — xərcləri azaltmaq lazımdır."
    if savings_rate < 0.10 or obligations / income > 0.5:
        return "Diqqət", "Gəlirin böyük hissəsi məcburi ödənişlərə gedir, yığım imkanı məhduddur."
    return "Balanslı", f"Xərclərdən sonra gəlirin orta hesabla {round(savings_rate * 100)}%-ni yığa bilərsiniz."


def _comparison(income, housing, current, current_credit, months, answers):
    rows = []

    def add(key, cur, rec, status, text):
        rows.append({
            "category_key": key,
            "category_name": CATEGORY_LABELS[key],
            "percentage": _r2(rec / income * 100) if income else 0.0,
            "current_monthly_amount": _r2(cur),
            "recommended_monthly_amount": _r2(rec),
            "annual_amount": _r2(sum(m[key] for m in months)),
            "status": status,
            "ai_recommendation": text,
        })

    avg = lambda key: sum(m[key] for m in months) / 12  # noqa: E731

    if housing > 0:
        add("housing", housing, housing, "Prioritet ödəniş", "Kirayə/ipoteka ödənişini hər ay vaxtında et.")
    for key in ("food", "restaurant", "entertainment", "utilities", "transport", "clothing", "online_shopping", "other_misc"):
        cur, rec = current[key], avg(key)
        gap = round(cur - rec)
        if key == "utilities":
            status, text = "Prioritet ödəniş", "Kommunal ödənişləri vaxtında et; qışda və yayda daha çox ayır."
        elif cur == 0:
            status, text = "Qənaətlidir", "Bu sahədə xərcin yoxdur — əla qənaətdir."
        elif cur > rec * 1.20:
            status, text = "Yüksək xərc", f"Bu xərci ayda təxminən {gap} AZN azalt və yığıma yönəlt."
        elif cur > rec * 1.05:
            status, text = "Diqqət", f"Bu xərci ayda {gap} AZN qədər azaltsan yaxşı olar."
        else:
            status, text = "Uyğundur", "Xərcin tövsiyə olunan səviyyədədir."
        add(key, cur, rec, status, text)
    if any(m["credit"] > 0 for m in months):
        high_rate = max((c.get("rate") or 0) for c in answers.credits) if answers.credits else 0
        text = "Kredit ödənişini hər ay vaxtında et."
        ending = [m["month_name"] for prev, m in zip(months, months[1:]) if m["credit"] < prev["credit"]]
        if ending:
            text = f"Məcburi ödənişi vaxtında et; bir kredit {ending[0]} ayından bağlanır və həmin pul yığıma keçir."
        if answers.annual_budget_priority == "Borcları azaltmaq" and high_rate >= 15:
            text = f"Faiz yüksəkdir ({high_rate:g}%) — yığımın bir hissəsini əlavə kredit ödənişinə yönəlt."
        add("credit", current_credit, avg("credit"), "Prioritet ödəniş", text)

    current_savings = max(0.0, income - housing - current_credit - sum(current.values()))
    rec_savings = avg("savings")
    if rec_savings > current_savings:
        text = f"Hər ay orta hesabla {_money(rec_savings)} yığ — indikindən {_money(rec_savings - current_savings)} çox."
    else:
        text = f"Hər ay orta hesabla {_money(rec_savings)} yığmaq realdır."
    add("savings", current_savings, rec_savings, "Uyğundur" if rec_savings > 0 else "Diqqət", text)
    return rows


def _summary_text(plan, answers: Answers) -> str:
    priority = answers.annual_budget_priority or "Gəliri daha düzgün bölüşdürmək"
    monthly = [m["savings"] for m in plan["monthly_table"]]
    best = MONTH_NAMES[monthly.index(max(monthly))]
    worst = MONTH_NAMES[monthly.index(min(monthly))]
    text = (
        f"Plan sizin \"{priority}\" prioritetinizə uyğun qurulub. "
        f"Orta aylıq yığım {_money(plan['recommended_monthly_savings'])}, illik {_money(plan['recommended_annual_savings'])} təşkil edir. "
        f"Ən çox yığım {best}, ən az yığım isə xərclərin artdığı {worst} ayına düşür."
    )
    if answers.monthly_savings_ability == "cannot_save":
        text += " Hazırda yığa bilmədiyinizi qeyd etdiyiniz üçün kiçik, real addımlarla başlamaq tövsiyə olunur."
    if plan["deficit_months"]:
        text += " Diqqət: bəzi aylarda vacib xərclər gəliri aşır."
    return text


# ---------------------------------------------------------------------------
# validation (§30–§34)
# ---------------------------------------------------------------------------

def validate_plan(plan: Dict, answers: Answers, user_set_categories=()) -> None:
    months = plan["monthly_table"]
    if len(months) != 12 or [m["month_name"] for m in months] != MONTH_NAMES:
        raise PlanValidationError("Plan Yanvar–Dekabr üçün 12 ayrı sətir olmalıdır.")

    income = plan["reliable_monthly_income"]
    goals = plan["savings_goals_breakdown"]
    for m in months:
        if abs(m["income"] - income) > 0.005:
            raise PlanValidationError(f"{m['month_name']}: gəlir sabit olmalıdır.")
        if abs(m["housing"] - _r2(answers.housing_amount)) > 0.005:
            raise PlanValidationError(f"{m['month_name']}: kirayə sabit olmalıdır.")
        for key in TABLE_CATEGORIES + list(OTHER_PARTS):
            if m[key] < 0:
                raise PlanValidationError(f"{m['month_name']}: {key} mənfi ola bilməz.")
        total = sum(m[k] for k in TABLE_CATEGORIES) + m["balance"]
        if abs(total - m["income"]) > 0.01:
            raise PlanValidationError(f"{m['month_name']}: gəlir = xərclər + yığım + qalıq tənliyi pozulub.")
        if abs(m["other"] - sum(m[k] for k in OTHER_PARTS)) > 0.01:
            raise PlanValidationError(f"{m['month_name']}: digər xərclər cəmi düzgün deyil.")
        if goals and abs(m["savings"] - sum(m["goal_contributions"])) > 0.01:
            raise PlanValidationError(f"{m['month_name']}: yığım məqsəd ödənişlərinin cəmi deyil.")
        if any(c < 0 for c in m["goal_contributions"]):
            raise PlanValidationError(f"{m['month_name']}: məqsəd ödənişi mənfi ola bilməz.")
        user_set = set(m.get("adjusted", []))
        if "other" in user_set:
            user_set |= set(OTHER_PARTS)
        if m["balance"] < 0 and (m["savings"] > 0 or any(m[c] > 0 for c in DISCRETIONARY if c not in user_set)):
            # Negative Qalıq only for a genuinely infeasible month: Savings and
            # all adjustable non-essential spending are already 0.
            raise PlanValidationError(f"{m['month_name']}: qalıq mənfi ola bilməz.")

    for g in goals:
        if g["planned_contribution_12m"] > g["target_amount"] - g["saved_amount"] + 0.01:
            raise PlanValidationError(f"{g['goal_name']}: hədəfdən artıq pul ayrılıb.")

    annual = plan["annual_totals"]
    for key in TABLE_CATEGORIES + ["income", "balance"]:
        if abs(annual[f"total_{key}"] - sum(m[key] for m in months)) > 0.01:
            raise PlanValidationError(f"İllik {key} cəmi aylıq dəyərlərin cəmi deyil.")
    if abs(annual["total_income"] - sum(annual[f"total_{k}"] for k in TABLE_CATEGORIES) - annual["total_balance"]) > 0.05:
        raise PlanValidationError("İllik gəlir = illik xərclər + yığım + qalıq tənliyi pozulub.")

    # Variation check (§32): a variable category with a real amount must not
    # be identical in all 12 months. Categories the user set by hand are exempt.
    for key in ("restaurant", "entertainment", "food", "utilities", "transport", "other"):
        if key in user_set_categories:
            continue
        values = {m[key] for m in months}
        if sum(m[key] for m in months) >= 12 * 10 and len(values) == 1 and not plan["deficit_months"]:
            raise PlanValidationError(f"{key} 12 ayın hamısında eynidir.")
