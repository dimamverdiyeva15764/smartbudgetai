import logging
from datetime import timedelta

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .ai_services import generate_ai_budget_plan
from .models import Credit, FinancialInquirySession, SavingsGoal
from .serializers import (
    ASSESSMENT_TEXT_TO_CODE, CompleteOnboardingSerializer, CreditSerializer, CreditsReplaceSerializer,
    ExtraIncomeUpdateSerializer, FinancialAssessmentSerializer, HasCreditSerializer, HousingUpdateSerializer,
    MonthlyExpensesSerializer, MonthlySavingsAbilitySerializer, RecalculateSerializer, RecurringExpensesSerializer,
    RegisterSerializer,
    SalaryUpdateSerializer, SavingsGoalsAddSerializer, SavingsGoalsUpdateSerializer,
)

logger = logging.getLogger(__name__)

# A plan stuck in "processing" longer than this (e.g. the serverless function
# was killed) can be retried by the user.
PROCESSING_STALE_AFTER = timedelta(seconds=90)

STATUS_MESSAGES = {
    'pending': 'Plan hələ hazırlanmayıb. Sorğunu tamamlayın və ya planı yenidən hesablayın.',
    'processing': 'AI maliyyə məlumatlarınızı təhlil edir və 12 aylıq planı qurur...',
    'completed': 'Planınız hazırdır!',
    'failed': 'Plan hazırlanarkən xəta baş verdi. Yenidən cəhd edin.',
}

ASSESSMENT_CODE_TO_TEXT = {code: text for text, code in ASSESSMENT_TEXT_TO_CODE.items()}
EXPENSE_FIELDS = {
    'market': 'expense_market',
    'utilities': 'expense_utilities',
    'transport': 'expense_transport',
    'restaurant': 'expense_restaurant',
    'clothing': 'expense_clothing',
    'entertainment': 'expense_entertainment',
    'onlineShopping': 'expense_online_shopping',
    'other': 'expense_other',
}


def _get_session(user):
    session, _ = FinancialInquirySession.objects.get_or_create(user=user)
    return session


def _answers_changed(session):
    """Answers changed after a plan was made -> the old plan is outdated.

    The dashboard is only shown for status "completed", so resetting the
    status prevents stale values from being displayed (US-17).
    """
    if session.status in ('completed', 'failed'):
        session.status = 'pending'
    # Dashboard changes belonged to the old answers; the new plan starts clean.
    session.plan_adjustments = []


def _is_stale(session):
    started = session.processing_started_at or session.updated_at
    return session.status == 'processing' and started and timezone.now() - started > PROCESSING_STALE_AFTER


def validate_session_answers(session):
    """Server-side validation of all 10 answers before generating a plan (US-11)."""
    errors = {}
    if not session.salary or session.salary <= 0:
        errors['step1'] = 'Aylıq əmək haqqı daxil edilməyib.'
    if session.has_extra_income is None:
        errors['step2'] = 'Əlavə gəlir sualını cavablandırın.'
    elif session.has_extra_income and (not session.extra_income or session.extra_income <= 0):
        errors['step2'] = 'Əlavə gəlir məbləği 0-dan böyük olmalıdır.'
    if not session.housing_type:
        errors['step3'] = 'Yaşayış formasını seçin.'
    elif session.housing_type != 'Özümündür' and (not session.housing_amount or session.housing_amount <= 0):
        errors['step3'] = 'Kirayə/ipoteka məbləği daxil edilməlidir.'
    if session.has_credit is None:
        errors['step4'] = 'Kredit sualını cavablandırın.'
    elif session.has_credit and not session.credits.exists():
        errors['step4'] = 'Ən azı 1 kredit daxil edilməlidir.'
    if not session.financial_assessment:
        errors['step8'] = 'Maliyyə davranışınızı seçin.'
    if not session.monthly_savings_ability:
        errors['step9'] = 'Aylıq yığım qabiliyyətinizi seçin.'
    if not session.annual_budget_priority:
        errors['step10'] = 'Əsas maliyyə prioritetini seçin.'
    return errors


def _status_payload(session):
    return {
        "success": True,
        "status": session.status,
        "isCompleted": session.status == 'completed',
        "isStale": bool(_is_stale(session)),
        "planVersion": session.plan_version,
        "session_id": session.id,
        "message": STATUS_MESSAGES.get(session.status, 'Yüklənir...'),
        "canRetry": session.status in ('failed', 'pending') or bool(_is_stale(session)),
    }


def _run_generation(session, action):
    """Mark the plan as processing, generate it and return a JSON Response."""
    session.status = 'processing'
    session.processing_started_at = timezone.now()
    session.plan_error = ''
    session.save(update_fields=['status', 'processing_started_at', 'plan_error', 'updated_at'])
    try:
        result = generate_ai_budget_plan(session.id)
    except Exception:
        logger.exception("Plan generation failed during %s for session %s", action, session.pk)
        session.refresh_from_db()
        return Response(
            {**_status_payload(session), "success": False, "code": "AI_PLAN_GENERATION_FAILED",
             "message": STATUS_MESSAGES['failed']},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    session.refresh_from_db()
    return Response(
        {**_status_payload(session), "textSource": result["plan"].get("text_source")},
        status=status.HTTP_200_OK,
    )


def _auth_payload(user, session, message, is_returning):
    refresh = RefreshToken.for_user(user)
    return {
        "success": True,
        "message": message,
        "user": {
            "fullName": f"{user.first_name} {user.last_name}".strip(),
            "email": user.email,
        },
        "tokens": {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        },
        "sessionStatus": session.status,
        "session_id": session.id,
        "isReturningUser": is_returning,
    }


class RegisterView(generics.CreateAPIView):
    """POST /api/register/ -> creates the user (or logs in a returning user
    with the same e-mail and correct password) and returns JWT tokens.

    Unexpected errors are converted to JSON by users.exceptions.
    """
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        email = str(request.data.get('email', '') or '').strip()
        password = request.data.get('password', '') or ''

        existing_user = User.objects.filter(email__iexact=email).first() if email else None
        if existing_user:
            user = authenticate(username=existing_user.username, password=password)
            if user is None:
                return Response(
                    {
                        "success": False,
                        "message": "Bu e-poçt artıq qeydiyyatdan keçib, şifrə yanlışdır.",
                        "errors": {"email": ["Bu e-poçt artıq qeydiyyatdan keçib, şifrə yanlışdır."]},
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            session, _ = FinancialInquirySession.objects.get_or_create(user=user)
            return Response(
                _auth_payload(user, session, "Giriş uğurla tamamlandı.", True),
                status=status.HTTP_200_OK,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = serializer.save()
            session = FinancialInquirySession.objects.create(user=user)
        return Response(
            _auth_payload(user, session, "Qeydiyyat uğurla tamamlandı.", False),
            status=status.HTTP_201_CREATED,
        )


class UpdateSalaryView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = SalaryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = _get_session(request.user)
        _answers_changed(session)
        session.salary = serializer.validated_data['salary']
        session.save()

        return Response({
            "success": True,
            "message": "Aylıq əmək haqqı saxlanıldı.",
            "salary": str(session.salary)
        }, status=status.HTTP_200_OK)


class UpdateExtraIncomeView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = ExtraIncomeUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = _get_session(request.user)
        _answers_changed(session)
        session.has_extra_income = serializer.validated_data['hasExtraIncome'] == 'Bəli'
        session.extra_income = serializer.validated_data['extraIncome']
        session.save()

        return Response({
            "success": True,
            "message": "Əlavə gəlir məlumatı saxlanıldı.",
            "hasExtraIncome": session.has_extra_income,
            "extraIncome": str(session.extra_income) if session.extra_income else None
        }, status=status.HTTP_200_OK)


class UpdateHousingView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = HousingUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = _get_session(request.user)
        _answers_changed(session)
        session.housing_type = serializer.validated_data['housingType']
        session.housing_amount = serializer.validated_data['housingAmount']
        session.save()

        return Response({
            "success": True,
            "message": "Yaşayış məlumatı saxlanıldı.",
            "housingType": session.housing_type,
            "housingAmount": str(session.housing_amount) if session.housing_amount else None
        }, status=status.HTTP_200_OK)


class UpdateHasCreditView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = HasCreditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = _get_session(request.user)
        _answers_changed(session)
        has_credit = serializer.validated_data['hasCredit'] == 'Bəli'
        session.has_credit = has_credit

        if not has_credit:
            session.credits.all().delete()

        session.save()

        return Response({"success": True, "hasCredit": session.has_credit}, status=status.HTTP_200_OK)


class CreditListCreateView(generics.ListCreateAPIView):
    serializer_class = CreditSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        session = _get_session(self.request.user)
        return session.credits.all()

    def perform_create(self, serializer):
        session = _get_session(self.request.user)
        _answers_changed(session)
        session.save()
        serializer.save(session=session)

    def put(self, request, *args, **kwargs):
        """Replace all credits at once (used by Step 4, atomic)."""
        serializer = CreditsReplaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = _get_session(request.user)
        with transaction.atomic():
            _answers_changed(session)
            session.save()
            session.credits.all().delete()
            for item in serializer.validated_data['credits']:
                item.pop('id', None)
                Credit.objects.create(session=session, **item)
        return Response({
            "success": True,
            "message": "Kreditlər saxlanıldı.",
            "credits": CreditSerializer(session.credits.all(), many=True).data,
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({
            "success": True,
            "message": "Kredit əlavə edildi.",
            "credit": serializer.data
        }, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"success": True, "credits": serializer.data})


class CreditDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CreditSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Credit.objects.filter(session__user=self.request.user)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _answers_changed(instance.session)
        instance.session.save()
        return Response({"success": True, "message": "Kredit yeniləndi.", "credit": serializer.data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        session = instance.session
        instance.delete()
        _answers_changed(session)
        session.save()
        return Response({"success": True, "message": "Kredit silindi."}, status=status.HTTP_200_OK)


class UpdateSavingsGoalsView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = SavingsGoalsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = _get_session(request.user)
        with transaction.atomic():
            _answers_changed(session)
            session.save()
            session.savings_goals.all().delete()
            for goal in serializer.validated_data['goals']:
                _create_goal(session, goal)

        return Response({
            "success": True,
            "message": "Yığım məqsədləri saxlanıldı.",
            "count": session.savings_goals.count()
        }, status=status.HTTP_200_OK)


def _create_goal(session, goal):
    return SavingsGoal.objects.create(
        session=session,
        goal_id=goal['id'],
        custom_name=goal.get('customName', '').strip() if goal['id'] == 'other' else '',
        priority=goal['priority'],
        amount=goal['amount'],
        saved_amount=goal.get('savedAmount') or 0,
        deadline_months=goal.get('deadlineMonths') or 12,
    )


class AddSavingsGoalView(APIView):
    """POST /api/financial-inquiry/savings-goals/add/ ("Yeni plan əlavə et").

    Appends goals to the user's existing goals — existing goals, their saved
    amounts, priorities and deadlines are never deleted or changed. The plan is
    then recalculated as ONE budget (see /summary/recalculate/).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SavingsGoalsAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = _get_session(request.user)
        existing = set(session.savings_goals.values_list('goal_id', flat=True))
        duplicates = [g['id'] for g in serializer.validated_data['goals'] if g['id'] in existing]
        if duplicates:
            return Response({
                "success": False,
                "message": "Bu məqsəd artıq planınızda var. Başqa məqsəd seçin.",
                "errors": {"goals": duplicates},
            }, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            created = [_create_goal(session, goal) for goal in serializer.validated_data['goals']]
            # The plan must be recalculated with the new goal; manual dashboard
            # values (expenses) stay valid, so they are kept.
            if session.status in ('completed', 'failed'):
                session.status = 'pending'
            session.save()
        return Response({
            "success": True,
            "message": "Yeni məqsəd planınıza əlavə edildi.",
            "added": [g.id for g in created],
            "count": session.savings_goals.count(),
        }, status=status.HTTP_201_CREATED)


class UpdateMonthlyExpensesView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        raw = request.data
        cleaned = {
            key: (0 if raw.get(key) in (None, '') else raw.get(key))
            for key in ['market', 'utilities', 'transport', 'restaurant', 'clothing', 'entertainment', 'onlineShopping', 'other']
        }

        serializer = MonthlyExpensesSerializer(data=cleaned)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        session = _get_session(request.user)
        _answers_changed(session)
        session.expense_market = data['market']
        session.expense_utilities = data['utilities']
        session.expense_transport = data['transport']
        session.expense_restaurant = data['restaurant']
        session.expense_clothing = data['clothing']
        session.expense_entertainment = data['entertainment']
        session.expense_online_shopping = data['onlineShopping']
        session.expense_other = data['other']
        session.save()

        return Response({
            "success": True,
            "message": "Aylıq xərclər saxlanıldı.",
            "totalMonthlyExpense": str(session.total_monthly_expense)
        }, status=status.HTTP_200_OK)


FIELD_MAP = {
    'market': 'recurring_market',
    'utilities': 'recurring_utilities',
    'transport': 'recurring_transport',
    'restaurant': 'recurring_restaurant',
    'clothing': 'recurring_clothing',
    'entertainment': 'recurring_entertainment',
    'onlineShopping': 'recurring_online_shopping',
    'other': 'recurring_other',
}


class UpdateRecurringExpensesView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = RecurringExpensesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        selected = set(serializer.validated_data['recurringExpenses'])

        session = _get_session(request.user)
        _answers_changed(session)

        for key, field_name in FIELD_MAP.items():
            setattr(session, field_name, key in selected)

        session.save()

        return Response({
            "success": True,
            "message": "Mütəmadi xərclər saxlanıldı.",
            "recurringExpenses": list(selected)
        }, status=status.HTTP_200_OK)


class UpdateFinancialAssessmentView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = FinancialAssessmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = _get_session(request.user)
        _answers_changed(session)
        session.financial_assessment = ASSESSMENT_TEXT_TO_CODE[serializer.validated_data['financialAssessment']]
        session.save()

        return Response({
            "success": True,
            "message": "Maliyyə davranışı saxlanıldı.",
            "financialAssessment": session.financial_assessment
        }, status=status.HTTP_200_OK)


class UpdateMonthlySavingsAbilityView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = MonthlySavingsAbilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = _get_session(request.user)
        _answers_changed(session)
        session.monthly_savings_ability = serializer.validated_data['monthlySavingsAbility']
        session.save()

        return Response({
            "success": True,
            "message": "Aylıq yığım qabiliyyəti saxlanıldı.",
            "monthlySavingsAbility": session.monthly_savings_ability
        }, status=status.HTTP_200_OK)   


class OnboardingAnswersView(APIView):
    """GET /api/financial-inquiry/answers/ — all saved answers in the shape the
    onboarding form uses, so steps are pre-filled after refresh, on another
    device, or when the user edits answers from the dashboard (US-17)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session = _get_session(request.user)

        def num(value):
            return '' if value is None else format(value.normalize(), 'f')

        expenses = {key: num(getattr(session, field)) for key, field in EXPENSE_FIELDS.items()}
        recurring = [key for key, field in FIELD_MAP.items() if getattr(session, field)]
        answers = {
            "salary": num(session.salary),
            "hasExtraIncome": None if session.has_extra_income is None else ('Bəli' if session.has_extra_income else 'Xeyr'),
            "extraIncome": num(session.extra_income) if session.has_extra_income else '',
            "housingType": session.housing_type,
            "housingAmount": num(session.housing_amount) if session.housing_type in ('Kirayədir', 'İpotekadır') else '',
            "hasCredit": None if session.has_credit is None else ('Bəli' if session.has_credit else 'Xeyr'),
            "credits": [
                {"monthly": num(c.monthly), "remaining": num(c.remaining), "rate": num(c.rate), "months": str(c.months)}
                for c in session.credits.all()
            ],
            "savingsGoals": [
                {"id": g.goal_id, "customName": g.custom_name or '', "priority": g.priority, "amount": num(g.amount),
                 "savedAmount": num(g.saved_amount) if g.saved_amount else '',
                 "deadlineMonths": str(g.deadline_months)}
                for g in session.savings_goals.order_by('id')
            ],
            "monthlyExpenses": expenses,
            "recurringExpenses": recurring,
            "financialAssessment": ASSESSMENT_CODE_TO_TEXT.get(session.financial_assessment, ''),
            "monthlySavingsAbility": session.monthly_savings_ability or '',
            "annualBudgetPriority": session.annual_budget_priority or '',
        }
        return Response({
            "success": True,
            "answers": answers,
            "status": session.status,
            "planVersion": session.plan_version,
            "hasAnswers": session.salary is not None,
        })


class CompleteOnboardingView(APIView):
    """POST /api/financial-inquiry/complete/ (Step 10).

    Saves the priority, validates ALL answers on the server, sets the status to
    "processing" and generates the plan. The frontend shows the processing
    screen and polls /financial-inquiry/status/ independently, so a page
    refresh does not lose the state.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CompleteOnboardingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = _get_session(request.user)
        if session.status == 'processing' and not _is_stale(session):
            return Response({**_status_payload(session), "code": "PLAN_ALREADY_PROCESSING"},
                            status=status.HTTP_202_ACCEPTED)

        session.annual_budget_priority = serializer.validated_data['annualBudgetPriority']
        session.plan_adjustments = []  # completing the questionnaire = fresh plan from the answers
        session.plan_variant = session.plan_version + 1  # new plan version → new variant
        if serializer.validated_data.get('monthlySavingsAbility'):
            session.monthly_savings_ability = serializer.validated_data['monthlySavingsAbility']
        session.save()

        errors = validate_session_answers(session)
        if errors:
            return Response(
                {"success": False, "message": next(iter(errors.values())), "errors": errors,
                 "code": "ANSWERS_INCOMPLETE"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _run_generation(session, 'onboarding completion')


class FinancialInquiryStatusView(APIView):
    """GET /api/financial-inquiry/status/ — Pending / Processing / Ready / Error."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session = _get_session(request.user)
        return Response(_status_payload(session), status=status.HTTP_200_OK)


class RetryPlanGenerationView(APIView):
    """POST /api/financial-inquiry/retry/ — re-run a failed / stuck / outdated plan."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session = _get_session(request.user)
        if session.status == 'processing' and not _is_stale(session):
            return Response({**_status_payload(session), "success": False, "code": "PLAN_ALREADY_PROCESSING",
                             "message": "Plan hazırda hazırlanır. Zəhmət olmasa gözləyin."},
                            status=status.HTTP_409_CONFLICT)
        errors = validate_session_answers(session)
        if errors:
            return Response({"success": False, "message": next(iter(errors.values())), "errors": errors,
                             "code": "ANSWERS_INCOMPLETE"}, status=status.HTTP_400_BAD_REQUEST)
        if not session.plan_variant:
            session.plan_variant = session.plan_version + 1
            session.save(update_fields=['plan_variant', 'updated_at'])
        return _run_generation(session, 'plan retry')


class RecalculateBudgetAPIView(APIView):
    """PUT/POST /api/summary/recalculate/ — recalculate the plan from the saved
    answers (US-17). Each successful calculation increases planVersion."""
    permission_classes = [IsAuthenticated]

    def put(self, request):
        serializer = RecalculateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = _get_session(request.user)
        if session.status == 'processing' and not _is_stale(session):
            return Response({**_status_payload(session), "success": False, "code": "PLAN_ALREADY_PROCESSING",
                             "message": "Plan hazırda hazırlanır."}, status=status.HTTP_409_CONFLICT)
        errors = validate_session_answers(session)
        if errors:
            return Response({"success": False, "message": next(iter(errors.values())), "errors": errors,
                             "code": "ANSWERS_INCOMPLETE"}, status=status.HTTP_400_BAD_REQUEST)

        # The user's latest dashboard values: newer changes replace older ones
        # for the same month/category; untouched cells keep earlier changes.
        merged = {(a['month_index'], a['category']): a for a in (session.plan_adjustments or [])}
        parts = ('clothing', 'online_shopping', 'other_misc')
        for item in serializer.validated_data['adjustments']:
            # "Digər" total and its parts must not both be stored for one month.
            if item['category'] in parts:
                merged.pop((item['month_index'], 'other'), None)
            elif item['category'] == 'other':
                for part in parts:
                    merged.pop((item['month_index'], part), None)
            merged[(item['month_index'], item['category'])] = {
                'month_index': item['month_index'], 'category': item['category'], 'value': float(item['value']),
            }
        session.plan_adjustments = sorted(merged.values(), key=lambda a: (a['month_index'], a['category']))
        if (serializer.validated_data['regenerate'] or not serializer.validated_data['adjustments']
                or not session.plan_variant):
            # "Planı yenilə" (regenerate) or no new edits: a genuine alternative
            # plan. Automatic recalculation after a dashboard edit keeps the
            # current variant so only the edit and dependent values change.
            session.plan_variant = session.plan_version + 1
        session.save(update_fields=['plan_adjustments', 'plan_variant', 'updated_at'])
        return _run_generation(session, 'recalculation')

    post = put


def _plan_not_ready(session):
    return Response({**_status_payload(session), "success": False,
                     "message": "Plan hələ hazır deyil."}, status=status.HTTP_409_CONFLICT)


class FinancialSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session = _get_session(request.user)
        if session.status != 'completed':
            return _plan_not_ready(session)
        return Response({
            "status": "success",
            "data": {
                "recommended_monthly_savings": float(session.recommended_monthly_savings or 0),
                "recommended_annual_savings": float(session.recommended_annual_savings or 0),
                "reliable_monthly_income": float(session.salary or 0) + (
                    float(session.extra_income or 0) if session.has_extra_income else 0.0),
                "financial_status": session.financial_status,
                "financial_status_description": session.financial_status_description,
                "is_feasible": not any(float(m.get("balance", 0)) < 0 for m in (session.monthly_table or [])),
                "deficit_months": [m.get("month_name") for m in (session.monthly_table or []) if float(m.get("balance", 0)) < 0],
                "goal_warnings": [g.get("note") for g in (session.savings_goals_breakdown or []) if g.get("on_track") is False],
                "monthly_budget_plan": session.ai_response_text,
                "annual_budget_priority": session.annual_budget_priority,
                "plan_version": session.plan_version,
                "text_source": session.plan_text_source,
                "generated_at": session.updated_at.isoformat(),
                "currency": "AZN",
            },
        })


class SavingsGoalsProgressAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session = _get_session(request.user)
        if session.status != 'completed':
            return _plan_not_ready(session)
        return Response({"status": "success", "data": session.savings_goals_breakdown or []})


class MonthlyBudgetTableAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session = _get_session(request.user)
        if session.status != 'completed':
            return _plan_not_ready(session)
        annual = dict(session.annual_totals or {})
        annual["is_negative"] = float(annual.get("total_balance", 0)) < 0
        rows = [{**row, "is_negative": float(row.get("balance", 0)) < 0} for row in (session.monthly_table or [])]
        return Response({"status": "success", "monthly_table": rows, "annual_totals": annual})


class BudgetComparisonAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session = _get_session(request.user)
        if session.status != 'completed':
            return _plan_not_ready(session)
        return Response({"status": "success", "budget_comparison": session.budget_comparison or []})


class ExportExcelAPIView(APIView):
    """GET /api/summary/export/excel/ — only the owner's plan (request.user)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session = _get_session(request.user)
        if session.status != 'completed':
            return _plan_not_ready(session)
        # Imported here: openpyxl/reportlab are only needed for exports, so
        # login, registration and the first request of a new instance stay fast.
        from .exports import build_excel_response
        return build_excel_response(session)


class ExportPDFAPIView(APIView):
    """GET /api/summary/export/pdf/ — only the owner's plan (request.user)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session = _get_session(request.user)
        if session.status != 'completed':
            return _plan_not_ready(session)
        from .exports import build_pdf_response
        return build_pdf_response(session)
