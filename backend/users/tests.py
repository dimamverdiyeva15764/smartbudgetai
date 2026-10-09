from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from . import budget_engine as be
from .models import FinancialInquirySession

VALID_USER = {'fullName': 'Aysel Məmmədova', 'email': 'aysel@example.com', 'password': 'Parol123!'}


def full_onboarding(client, housing='Kirayədir', credits=True):
    """Answer all 10 steps through the real API endpoints."""
    steps = [
        ('update-salary', {'salary': 1500}),
        ('update-extra-income', {'hasExtraIncome': 'Bəli', 'extraIncome': 300}),
        ('update-housing', {'housingType': housing, 'housingAmount': 400 if housing != 'Özümündür' else None}),
        ('update-has-credit', {'hasCredit': 'Bəli' if credits else 'Xeyr'}),
    ]
    for name, body in steps:
        r = client.patch(reverse(name), body, format='json')
        assert r.status_code == 200, (name, r.json())
    if credits:
        r = client.put(reverse('credit-list-create'), {'credits': [
            {'monthly': 150, 'remaining': 1200, 'rate': 18, 'months': 8},
            {'monthly': 50, 'remaining': 1000, 'rate': 10, 'months': 20},
        ]}, format='json')
        assert r.status_code == 200, r.json()
    more = [
        ('update-savings-goals', {'goals': [
            {'id': 'travel', 'priority': 'Yuxarı prioritet', 'amount': 2000},
            {'id': 'other', 'customName': 'Noutbuk', 'priority': 'Aşağı prioritet', 'amount': 1500},
        ]}),
        ('update-monthly-expenses', {'market': 300, 'utilities': 80, 'transport': 60, 'restaurant': 150,
                                     'clothing': 70, 'entertainment': 100, 'onlineShopping': 50, 'other': ''}),
        ('update-recurring-expenses', {'recurringExpenses': ['market', 'utilities', 'transport']}),
        ('update-financial-assessment', {'financialAssessment': 'Bəzən planı poza bilirəm'}),
        ('update-monthly-savings-ability', {'monthlySavingsAbility': 'sometimes'}),
    ]
    for name, body in more:
        r = client.patch(reverse(name), body, format='json')
        assert r.status_code == 200, (name, r.json())


class RegistrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_creates_user_session_and_tokens(self):
        r = self.client.post(reverse('register'), VALID_USER, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r['Content-Type'], 'application/json')
        body = r.json()
        self.assertTrue(body['tokens']['access'])
        user = User.objects.get(email='aysel@example.com')
        self.assertNotEqual(user.password, VALID_USER['password'])  # hashed
        self.assertTrue(user.check_password(VALID_USER['password']))
        self.assertEqual(user.first_name, 'Aysel')
        self.assertTrue(FinancialInquirySession.objects.filter(user=user).exists())

    def test_duplicate_email_with_wrong_password_is_rejected(self):
        self.client.post(reverse('register'), VALID_USER, format='json')
        r = self.client.post(reverse('register'), {**VALID_USER, 'email': 'AYSEL@example.com', 'password': 'Yanlis123!'},
                             format='json')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()['success'])
        self.assertEqual(User.objects.count(), 1)

    def test_validation_errors_are_json(self):
        r = self.client.post(reverse('register'), {'fullName': ' ', 'email': 'bad', 'password': 'x'}, format='json')
        self.assertEqual(r.status_code, 400)
        body = r.json()
        self.assertIn('fullName', body['errors'])
        self.assertIn('email', body['errors'])
        self.assertIn('password', body['errors'])

    def test_unexpected_server_error_is_json_not_html(self):
        with patch('users.views.User.objects.filter', side_effect=OperationalError('no such table: auth_user')):
            with self.assertLogs('users.exceptions', level='ERROR'):
                r = self.client.post(reverse('register'), VALID_USER, format='json')
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r['Content-Type'], 'application/json')
        self.assertEqual(r.json()['code'], 'SERVER_ERROR')

    def test_unknown_api_route_returns_json_404(self):
        r = self.client.get('/api/does-not-exist/')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r['Content-Type'], 'application/json')


class OnboardingFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        r = self.client.post(reverse('register'), VALID_USER, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.json()['tokens']['access']}")

    def test_conditional_validation(self):
        r = self.client.patch(reverse('update-salary'), {'salary': -5}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.patch(reverse('update-extra-income'), {'hasExtraIncome': 'Bəli'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.patch(reverse('update-housing'), {'housingType': 'Kirayədir'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.put(reverse('credit-list-create'), {'credits': [
            {'monthly': 0, 'remaining': 10, 'rate': 5, 'months': 2}]}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.put(reverse('credit-list-create'), {'credits': [
            {'monthly': 10, 'remaining': 10, 'rate': 5, 'months': 2.5}]}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.patch(reverse('update-savings-goals'), {'goals': [
            {'id': 'other', 'priority': 'Orta prioritet', 'amount': 100}]}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_switching_extra_income_to_no_removes_amount(self):
        self.client.patch(reverse('update-extra-income'), {'hasExtraIncome': 'Bəli', 'extraIncome': 200}, format='json')
        self.client.patch(reverse('update-extra-income'), {'hasExtraIncome': 'Xeyr', 'extraIncome': 200}, format='json')
        session = FinancialInquirySession.objects.get()
        self.assertFalse(session.has_extra_income)
        self.assertIsNone(session.extra_income)

    def test_answers_endpoint_prefills_everything(self):
        full_onboarding(self.client)
        answers = self.client.get(reverse('onboarding-answers')).json()['answers']
        self.assertEqual(answers['salary'], '1500')
        self.assertEqual(answers['hasExtraIncome'], 'Bəli')
        self.assertEqual(answers['housingType'], 'Kirayədir')
        self.assertEqual(len(answers['credits']), 2)
        self.assertEqual({g['id'] for g in answers['savingsGoals']}, {'travel', 'other'})
        self.assertEqual(answers['monthlyExpenses']['other'], '0')
        self.assertEqual(set(answers['recurringExpenses']), {'market', 'utilities', 'transport'})
        self.assertEqual(answers['financialAssessment'], 'Bəzən planı poza bilirəm')

    def test_complete_requires_priority_and_all_answers(self):
        r = self.client.post(reverse('complete-onboarding'), {}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.post(reverse('complete-onboarding'), {'annualBudgetPriority': 'Borcları azaltmaq'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'ANSWERS_INCOMPLETE')

    def test_full_flow_generates_valid_plan_then_recalculates(self):
        full_onboarding(self.client)
        r = self.client.post(reverse('complete-onboarding'), {'annualBudgetPriority': 'Daha çox qənaət etmək'},
                             format='json')
        self.assertEqual(r.status_code, 200, r.json())
        self.assertEqual(r.json()['status'], 'completed')
        self.assertEqual(r.json()['planVersion'], 1)

        table = self.client.get(reverse('monthly-budget-table')).json()
        months = table['monthly_table']
        self.assertEqual(len(months), 12)
        for m in months:
            total = sum(m[k] for k in be.TABLE_CATEGORIES) + m['balance']
            self.assertAlmostEqual(total, m['income'], places=2)
            self.assertEqual(m['housing'], 400)
        self.assertGreater(len({m['restaurant'] for m in months}), 3)
        self.assertGreater(len({m['savings'] for m in months}), 3)
        self.assertAlmostEqual(table['annual_totals']['total_savings'], sum(m['savings'] for m in months), places=2)
        # first credit (8 months) ends -> credit drops from 200 to 50
        self.assertEqual(months[0]['credit'], 200)
        self.assertEqual(months[11]['credit'], 50)

        summary = self.client.get(reverse('financial-summary')).json()['data']
        self.assertEqual(summary['reliable_monthly_income'], 1800)

        # changing an answer marks the plan outdated -> dashboard not served
        self.client.patch(reverse('update-salary'), {'salary': 2500}, format='json')
        self.assertEqual(self.client.get(reverse('financial-summary')).status_code, 409)
        r = self.client.put(reverse('budget-recalculate'), {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['planVersion'], 2)
        months2 = self.client.get(reverse('monthly-budget-table')).json()['monthly_table']
        self.assertEqual(months2[0]['income'], 2800)

        xlsx = self.client.get(reverse('export-excel'))
        self.assertEqual(xlsx.status_code, 200)
        self.assertIn('budce_plani_v2_', xlsx['Content-Disposition'])
        pdf = self.client.get(reverse('export-pdf'))
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))

    def test_generation_failure_sets_failed_status_and_retry_works(self):
        full_onboarding(self.client)
        with patch('users.ai_services.build_plan', side_effect=be.PlanValidationError('boom')):
            with self.assertLogs('users', level='ERROR'):
                r = self.client.post(reverse('complete-onboarding'),
                                     {'annualBudgetPriority': 'Xərclərə nəzarət etmək'}, format='json')
        self.assertEqual(r.status_code, 500)
        self.assertEqual(self.client.get(reverse('inquiry-status')).json()['status'], 'failed')
        r = self.client.post(reverse('retry-plan'), {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], 'completed')

    def test_retry_conflicts_while_recently_processing_but_recovers_when_stale(self):
        full_onboarding(self.client)
        session = FinancialInquirySession.objects.get()
        session.annual_budget_priority = 'Borcları azaltmaq'
        session.status = 'processing'
        session.processing_started_at = timezone.now()
        session.save()
        self.assertEqual(self.client.post(reverse('retry-plan')).status_code, 409)
        FinancialInquirySession.objects.filter(pk=session.pk).update(
            processing_started_at=timezone.now() - timedelta(minutes=5))
        self.assertTrue(self.client.get(reverse('inquiry-status')).json()['isStale'])
        self.assertEqual(self.client.post(reverse('retry-plan')).status_code, 200)


class IsolationTests(TestCase):
    def test_users_only_see_their_own_plan_and_credits(self):
        a, b = APIClient(), APIClient()
        ta = a.post(reverse('register'), VALID_USER, format='json').json()['tokens']['access']
        tb = b.post(reverse('register'), {**VALID_USER, 'email': 'b@example.com'}, format='json').json()['tokens']['access']
        a.credentials(HTTP_AUTHORIZATION=f'Bearer {ta}')
        b.credentials(HTTP_AUTHORIZATION=f'Bearer {tb}')
        full_onboarding(a)
        a.post(reverse('complete-onboarding'), {'annualBudgetPriority': 'Borcları azaltmaq'}, format='json')
        self.assertEqual(b.get(reverse('financial-summary')).status_code, 409)
        self.assertEqual(b.get(reverse('export-excel')).status_code, 409)
        credit_id = a.get(reverse('credit-list-create')).json()['credits'][0]['id']
        self.assertEqual(b.delete(reverse('credit-detail', args=[credit_id])).status_code, 404)
        self.assertEqual(APIClient().get(reverse('financial-summary')).status_code, 401)


class BudgetEngineTests(TestCase):
    def base_answers(self, **kw):
        data = dict(
            salary=1500, extra_income=0, housing_type='Özümündür', housing_amount=0,
            expenses=dict(food=300, utilities=80, transport=60, restaurant=150, clothing=70,
                          entertainment=100, online_shopping=50, other_misc=40),
            annual_budget_priority='Gəliri daha düzgün bölüşdürmək',
        )
        data.update(kw)
        return be.Answers(**data)

    def test_twelve_individual_months_with_realistic_qaliq(self):
        plan = be.build_plan(self.base_answers(), variant=1)
        months = plan['monthly_table']
        self.assertEqual([m['month_name'] for m in months], be.MONTH_NAMES)
        for m in months:
            self.assertEqual(m['housing'], 0)
            self.assertGreaterEqual(m['balance'], 0)
            self.assertAlmostEqual(sum(m[k] for k in be.TABLE_CATEGORIES) + m['balance'], m['income'], places=2)
        self.assertGreater(len({m['balance'] for m in months}), 2)  # Qalıq differs by month
        self.assertTrue(any(m['balance'] > 0 for m in months))
        for key in ('restaurant', 'entertainment', 'food', 'utilities', 'transport', 'other', 'savings'):
            self.assertGreater(len({m[key] for m in months}), 1, key)
        # winter utilities higher than spring, December restaurants higher than October
        self.assertGreater(months[0]['utilities'], months[4]['utilities'])
        self.assertGreater(months[11]['restaurant'], months[9]['restaurant'])
        self.assertTrue(all(m['note'] for m in months))

    def test_user_priority_changes_the_plan(self):
        relaxed = be.build_plan(self.base_answers())
        saver = be.build_plan(self.base_answers(annual_budget_priority='Daha çox qənaət etmək',
                                                financial_assessment='nothing_left'))
        self.assertGreater(saver['recommended_annual_savings'], relaxed['recommended_annual_savings'])

    def test_deficit_is_reported_not_hidden(self):
        plan = be.build_plan(self.base_answers(
            salary=600, housing_type='Kirayədir', housing_amount=350,
            credits=[{'monthly': 150, 'remaining': 3000, 'rate': 20, 'months': 24}]))
        self.assertEqual(plan['financial_status'], 'Risklidir')
        for m in plan['monthly_table']:
            self.assertLess(m['balance'], 0)
            self.assertEqual(m['savings'], 0)
            self.assertEqual(m['restaurant'], 0)
            self.assertGreaterEqual(m['food'], 0.8 * 270)  # essentials only down to a realistic minimum
            self.assertEqual(m['credit'], 150)
            self.assertAlmostEqual(sum(m[k] for k in be.TABLE_CATEGORIES) + m['balance'], m['income'], places=2)

    def test_goals_prioritised_and_capped(self):
        plan = be.build_plan(self.base_answers(goals=[
            {'goal_id': 'home', 'custom_name': '', 'priority': 'Aşağı prioritet', 'amount': 50000, 'saved': 0, 'deadline': 12},
            {'goal_id': 'emergency', 'custom_name': '', 'priority': 'Yuxarı prioritet', 'amount': 1000, 'saved': 0, 'deadline': 12},
        ]))
        home, emergency = plan['savings_goals_breakdown']
        self.assertEqual(emergency['planned_contribution_12m'], 1000)  # capped at target
        self.assertEqual(emergency['projected_progress_percentage'], 100)
        total = home['planned_contribution_12m'] + emergency['planned_contribution_12m']
        self.assertAlmostEqual(total, plan['recommended_annual_savings'], places=1)
        self.assertFalse(home['on_track'])


class RecalculationTests(TestCase):
    """"Planı yenilə" must recalculate from the latest data, save it and never return the old plan."""

    def setUp(self):
        self.client = APIClient()
        token = self.client.post(reverse('register'), VALID_USER, format='json').json()['tokens']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        full_onboarding(self.client)
        self.client.post(reverse('complete-onboarding'), {'annualBudgetPriority': 'Daha çox qənaət etmək'}, format='json')

    def table(self):
        return self.client.get(reverse('monthly-budget-table')).json()['monthly_table']

    def test_dashboard_changes_are_applied_saved_and_rebalanced(self):
        before = self.table()
        r = self.client.put(reverse('budget-recalculate'), {'adjustments': [
            {'month_index': 1, 'category': 'restaurant', 'value': 300},
            {'month_index': 7, 'category': 'other', 'value': 50},
        ]}, format='json')
        self.assertEqual(r.status_code, 200, r.json())
        after = self.table()
        self.assertEqual(after[0]['restaurant'], 300)
        self.assertEqual(after[6]['other'], 50)
        self.assertEqual(after[6]['clothing'] + after[6]['online_shopping'] + after[6]['other_misc'], 50)
        # savings + Qalıq absorb exactly the extra spending, the month still balances
        self.assertAlmostEqual(after[0]['savings'] + after[0]['balance'],
                               before[0]['savings'] + before[0]['balance'] - (300 - before[0]['restaurant']), places=2)
        self.assertGreaterEqual(after[0]['balance'], 0)
        for m in after:
            self.assertAlmostEqual(sum(m[k] for k in be.TABLE_CATEGORIES) + m['balance'], m['income'], places=2)
        self.assertIn('restaurant', after[0]['adjusted'])
        # untouched months are calculated exactly as before
        self.assertEqual(after[3]['restaurant'], before[3]['restaurant'])
        # totals, savings summary and comparison are recalculated too
        totals = self.client.get(reverse('monthly-budget-table')).json()['annual_totals']
        self.assertAlmostEqual(totals['total_savings'], sum(m['savings'] for m in after), places=2)
        summary = self.client.get(reverse('financial-summary')).json()['data']
        self.assertAlmostEqual(summary['recommended_annual_savings'], totals['total_savings'], places=2)
        # the saved plan is returned again after a plain refresh / second update
        self.client.put(reverse('budget-recalculate'), {}, format='json')
        self.assertEqual(self.table()[0]['restaurant'], 300)

    def test_changed_answers_change_the_recalculated_plan(self):
        before = self.table()
        self.client.patch(reverse('update-monthly-expenses'), {'market': 500, 'utilities': 80, 'transport': 60, 'restaurant': 150,
                                                               'clothing': 70, 'entertainment': 100, 'onlineShopping': 50},
                          format='json')
        r = self.client.put(reverse('budget-recalculate'), {}, format='json')
        self.assertEqual(r.status_code, 200)
        after = self.table()
        self.assertGreater(after[0]['food'], before[0]['food'])
        self.assertLess(after[0]['savings'], before[0]['savings'])

    def test_answer_change_clears_old_dashboard_changes(self):
        self.client.put(reverse('budget-recalculate'), {'adjustments': [
            {'month_index': 1, 'category': 'restaurant', 'value': 300}]}, format='json')
        self.client.patch(reverse('update-salary'), {'salary': 2000}, format='json')
        self.client.put(reverse('budget-recalculate'), {}, format='json')
        first = self.table()[0]
        self.assertNotEqual(first['restaurant'], 300)
        self.assertNotIn('adjusted', first)
        self.assertEqual(first['income'], 2300)

    def test_invalid_adjustments_are_rejected(self):
        for bad in ({'month_index': 13, 'category': 'food', 'value': 1},
                    {'month_index': 1, 'category': 'income', 'value': 1},
                    {'month_index': 1, 'category': 'food', 'value': -5}):
            r = self.client.put(reverse('budget-recalculate'), {'adjustments': [bad]}, format='json')
            self.assertEqual(r.status_code, 400, bad)


FIXED_KEYS = ('income', 'housing', 'credit')
VARIABLE_KEYS = ('restaurant', 'entertainment', 'food', 'utilities', 'transport', 'other', 'savings', 'balance')


class RegenerationTests(TestCase):
    """Test 1-5 from the request: V1 -> V2 -> V3 alternatives, manual edit, answer change."""

    def setUp(self):
        self.client = APIClient()
        token = self.client.post(reverse('register'), VALID_USER, format='json').json()['tokens']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        full_onboarding(self.client)

    def table(self):
        return self.client.get(reverse('monthly-budget-table')).json()

    def assert_valid(self, data):
        months, totals = data['monthly_table'], data['annual_totals']
        self.assertEqual(len(months), 12)
        for m in months:
            for key in be.TABLE_CATEGORIES + ['balance', 'clothing', 'online_shopping', 'other_misc']:
                self.assertGreaterEqual(m[key], 0, (m['month_name'], key))
            self.assertAlmostEqual(sum(m[k] for k in be.TABLE_CATEGORIES) + m['balance'], m['income'], places=2)
        for key in be.TABLE_CATEGORIES + ['income', 'balance']:
            self.assertAlmostEqual(totals[f'total_{key}'], sum(m[key] for m in months), places=2)
        self.assertAlmostEqual(totals['total_income'],
                               sum(totals[f'total_{k}'] for k in be.TABLE_CATEGORIES) + totals['total_balance'], places=1)
        self.assertGreater(len({m['balance'] for m in months}), 1)

    def differing_categories(self, a, b):
        return {k for k in VARIABLE_KEYS if any(x[k] != y[k] for x, y in zip(a, b))}

    def test_versions_are_genuine_valid_alternatives(self):
        r = self.client.post(reverse('complete-onboarding'), {'annualBudgetPriority': 'Daha çox qənaət etmək'}, format='json')
        self.assertEqual(r.json()['planVersion'], 1)
        v1 = self.table(); self.assert_valid(v1)
        self.assertEqual(self.client.put(reverse('budget-recalculate'), {}, format='json').json()['planVersion'], 2)
        v2 = self.table(); self.assert_valid(v2)
        self.client.put(reverse('budget-recalculate'), {}, format='json')
        v3 = self.table(); self.assert_valid(v3)
        m1, m2, m3 = v1['monthly_table'], v2['monthly_table'], v3['monthly_table']
        for a, b in ((m1, m2), (m2, m3), (m1, m3)):
            self.assertGreaterEqual(len(self.differing_categories(a, b)), 5)
            for x, y in zip(a, b):
                for key in FIXED_KEYS:
                    self.assertEqual(x[key], y[key])
                # controlled variation: no extreme jumps for the same month
                for key in ('food', 'utilities', 'transport'):
                    if x[key]:
                        self.assertLess(abs(y[key] - x[key]) / x[key], 0.25, (x['month_name'], key))
        # seasonal logic kept: winter utilities above May in every version
        for m in (m1, m2, m3):
            self.assertGreater(m[0]['utilities'], m[4]['utilities'])
        self.assertTrue(any(m['balance'] > 0 for m in m1 + m2 + m3))

    def test_manual_edit_keeps_variant_and_respects_value(self):
        self.client.post(reverse('complete-onboarding'), {'annualBudgetPriority': 'Daha çox qənaət etmək'}, format='json')
        self.client.put(reverse('budget-recalculate'), {}, format='json')  # version 2
        v2 = self.table()['monthly_table']
        r = self.client.put(reverse('budget-recalculate'), {'adjustments': [
            {'month_index': 1, 'category': 'restaurant', 'value': 350}]}, format='json')
        self.assertEqual(r.json()['planVersion'], 3)
        data = self.table(); self.assert_valid(data)
        v3 = data['monthly_table']
        self.assertEqual(v3[0]['restaurant'], 350)
        self.assertAlmostEqual(v3[0]['savings'] + v3[0]['balance'],
                               v2[0]['savings'] + v2[0]['balance'] - (350 - v2[0]['restaurant']), places=2)
        # other months keep their expenses; only goal contributions / Savings /
        # Qalıq may shift because all months share one goal budget
        for a, b in zip(v3[1:], v2[1:]):
            for key in ('income', 'housing', 'credit', 'restaurant', 'entertainment', 'food', 'utilities', 'transport', 'other'):
                self.assertEqual(a[key], b[key])
        # a later "Planı yenilə" without edits: new alternative, edit still respected
        self.client.put(reverse('budget-recalculate'), {}, format='json')
        v4 = self.table()['monthly_table']
        self.assertEqual(v4[0]['restaurant'], 350)
        self.assertGreaterEqual(len(self.differing_categories(v3[1:], v4[1:])), 4)

    def test_questionnaire_change_is_used(self):
        self.client.post(reverse('complete-onboarding'), {'annualBudgetPriority': 'Daha çox qənaət etmək'}, format='json')
        self.client.patch(reverse('update-salary'), {'salary': 2500}, format='json')
        r = self.client.post(reverse('complete-onboarding'), {'annualBudgetPriority': 'Daha çox qənaət etmək'}, format='json')
        self.assertEqual(r.status_code, 200)
        data = self.table(); self.assert_valid(data)
        self.assertTrue(all(m['income'] == 2800 for m in data['monthly_table']))


class QaliqAndManualValueTests(TestCase):
    def tight_answers(self):
        # close to the user's real example: food≈500, utilities≈280, transport≈580
        return be.Answers(
            salary=2400, extra_income=300, housing_type='Kirayədir', housing_amount=600,
            credits=[{'monthly': 200, 'remaining': 3000, 'rate': 16, 'months': 15}],
            expenses=dict(food=500, utilities=280, transport=580, restaurant=200, clothing=120,
                          entertainment=150, online_shopping=80, other_misc=60),
            recurring=dict(food=True, utilities=True, transport=True),
            goals=[{'goal_id': 'travel', 'custom_name': '', 'priority': 'Yuxarı prioritet', 'amount': 3000}],
            financial_assessment='sometimes_breaks_plan', monthly_savings_ability='sometimes',
            annual_budget_priority='Daha çox qənaət etmək')

    def test_tight_budget_still_gets_realistic_qaliq(self):
        for variant in (1, 2, 3):
            months = be.build_plan(self.tight_answers(), variant=variant)['monthly_table']
            qaliq = [m['balance'] for m in months]
            self.assertTrue(any(q > 0 for q in qaliq), variant)
            self.assertTrue(all(q >= 0 for q in qaliq))
            for m in months:  # Savings = goal contributions; Qalıq = what is left
                self.assertAlmostEqual(m['savings'], sum(m['goal_contributions']), places=2)

    def test_manual_value_above_free_money_is_respected(self):
        plan = be.build_plan(self.tight_answers(), [{'month_index': 1, 'category': 'restaurant', 'value': 420}], variant=1)
        jan = plan['monthly_table'][0]
        self.assertEqual(jan['restaurant'], 420)
        self.assertAlmostEqual(sum(jan[k] for k in be.TABLE_CATEGORIES) + jan['balance'], jan['income'], places=2)


def _register(client, email):
    token = client.post(reverse('register'), {**VALID_USER, 'email': email}, format='json').json()['tokens']['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')


def _answer(client, salary=1800, extra=300, rent=500, credit=None, expenses=None, goals=None, priority='Daha çox qənaət etmək'):
    client.patch(reverse('update-salary'), {'salary': salary}, format='json')
    client.patch(reverse('update-extra-income'), {'hasExtraIncome': 'Bəli' if extra else 'Xeyr', 'extraIncome': extra or None}, format='json')
    client.patch(reverse('update-housing'), {'housingType': 'Kirayədir', 'housingAmount': rent}, format='json')
    client.patch(reverse('update-has-credit'), {'hasCredit': 'Bəli' if credit else 'Xeyr'}, format='json')
    if credit:
        client.put(reverse('credit-list-create'), {'credits': [credit]}, format='json')
    client.patch(reverse('update-savings-goals'), {'goals': goals or [
        {'id': 'travel', 'priority': 'Yuxarı prioritet', 'amount': 5000, 'savedAmount': 1000, 'deadlineMonths': 12}]}, format='json')
    client.patch(reverse('update-monthly-expenses'), expenses or {
        'market': 350, 'utilities': 120, 'transport': 100, 'restaurant': 150, 'clothing': 80,
        'entertainment': 100, 'onlineShopping': 40, 'other': 40}, format='json')
    client.patch(reverse('update-recurring-expenses'), {'recurringExpenses': ['market', 'utilities']}, format='json')
    client.patch(reverse('update-financial-assessment'), {'financialAssessment': 'Pulumu yaxşı idarə edə bilirəm'}, format='json')
    client.patch(reverse('update-monthly-savings-ability'), {'monthlySavingsAbility': 'sometimes'}, format='json')
    r = client.post(reverse('complete-onboarding'), {'annualBudgetPriority': priority}, format='json')
    assert r.status_code == 200, r.json()


def _assert_month_math(test, months):
    for m in months:
        test.assertAlmostEqual(sum(m[k] for k in be.TABLE_CATEGORIES) + m['balance'], m['income'], places=2)
        test.assertAlmostEqual(m['savings'], sum(m['goal_contributions']), places=2)


class RequirementTestsAtoH(TestCase):
    """Automated versions of the requested Tests A–H."""

    def setUp(self):
        self.client = APIClient()

    def table(self):
        return self.client.get(reverse('monthly-budget-table')).json()

    def goals(self):
        return self.client.get(reverse('savings-goals-progress')).json()['data']

    def test_A_normal_qaliq_is_calculated(self):
        _register(self.client, 'a@example.com')
        _answer(self.client, goals=[{'id': 'car', 'priority': 'Orta prioritet', 'amount': 3000, 'deadlineMonths': 24}])
        months = self.table()['monthly_table']
        _assert_month_math(self, months)
        qaliq = [m['balance'] for m in months]
        self.assertTrue(all(q >= 0 for q in qaliq))
        self.assertTrue(all(q > 0 for q in qaliq))  # goals need less than capacity → real free money
        self.assertGreater(len(set(qaliq)), 6)      # varies with monthly spending
        # Qalıq is exactly the leftover, not moved into Savings
        for m in months:
            spent = sum(m[k] for k in be.TABLE_CATEGORIES if k != 'savings')
            self.assertAlmostEqual(m['balance'], m['income'] - spent - m['savings'], places=2)
        self.assertGreater(months[0]['savings'], 0)
        car = self.goals()[0]
        # once the goal is reached Savings stop and the money stays free (Qalıq)
        self.assertLessEqual(car['planned_contribution_12m'], 3000)

    def test_B_impossible_budget(self):
        _register(self.client, 'b@example.com')
        _answer(self.client, salary=300, extra=0, rent=500,
                credit={'monthly': 800, 'remaining': 9000, 'rate': 20, 'months': 24})
        months = self.table()['monthly_table']
        _assert_month_math(self, months)
        for m in months:
            self.assertEqual(m['income'], 300)      # no invented income
            self.assertEqual(m['housing'], 500)     # fixed rent unchanged
            self.assertEqual(m['credit'], 800)      # mandatory credit unchanged
            self.assertEqual(m['savings'], 0)
            self.assertEqual(m['restaurant'] + m['entertainment'] + m['other'], 0)
            self.assertLess(m['balance'], 0)        # real deficit shown
        summary = self.client.get(reverse('financial-summary')).json()['data']
        self.assertFalse(summary['is_feasible'])
        self.assertEqual(summary['financial_status'], 'Risklidir')
        self.assertIn('mümkün deyil', summary['financial_status_description'])

    def test_C_regeneration_versions_differ(self):
        _register(self.client, 'c@example.com')
        _answer(self.client)
        versions = [self.table()['monthly_table']]
        for _ in range(2):
            self.client.put(reverse('budget-recalculate'), {}, format='json')
            versions.append(self.table()['monthly_table'])
        for v in versions:
            _assert_month_math(self, v)
        for a, b in ((versions[0], versions[1]), (versions[1], versions[2])):
            for x, y in zip(a, b):
                for key in ('income', 'housing', 'credit'):
                    self.assertEqual(x[key], y[key])
            changed = {k for k in ('restaurant', 'entertainment', 'food', 'utilities', 'transport', 'other', 'savings', 'balance')
                       if any(x[k] != y[k] for x, y in zip(a, b))}
            self.assertGreaterEqual(len(changed), 6)
        self.assertTrue(self.goals())  # goals kept

    def test_D_E_add_goals_one_budget_progress_kept(self):
        _register(self.client, 'd@example.com')
        _answer(self.client, credit={'monthly': 150, 'remaining': 3000, 'rate': 16, 'months': 20})
        before = self.table()['monthly_table']
        r = self.client.post(reverse('add-savings-goal'), {'goals': [
            {'id': 'car', 'priority': 'Orta prioritet', 'amount': 10000, 'savedAmount': 2000, 'deadlineMonths': 24}]}, format='json')
        self.assertEqual(r.status_code, 201, r.json())
        self.assertEqual(self.client.get(reverse('financial-summary')).status_code, 409)  # old plan not shown
        self.client.put(reverse('budget-recalculate'), {}, format='json')
        goals = self.goals()
        self.assertEqual([g['goal_id'] for g in goals], ['travel', 'car'])
        travel, car = goals
        self.assertEqual((travel['saved_amount'], travel['target_amount'], travel['progress_percentage']), (1000, 5000, 20))
        self.assertEqual((travel['deadline_months'], travel['priority']), (12, 'Yuxarı prioritet'))
        self.assertEqual((car['saved_amount'], car['target_amount'], car['deadline_months']), (2000, 10000, 24))
        months = self.table()['monthly_table']
        _assert_month_math(self, months)
        for m, old in zip(months, before):
            self.assertEqual(m['income'], 2100)   # income counted once
            self.assertEqual(m['housing'], 500)   # rent counted once
            self.assertEqual(m['credit'], old['credit'])
            self.assertEqual(len(m['goal_contributions']), 2)
        # high-priority, near-deadline travel gets the larger share of the first months
        self.assertGreater(sum(m['goal_contributions'][0] for m in months[:6]), sum(m['goal_contributions'][1] for m in months[:6]))
        # Test E: a third goal
        self.client.post(reverse('add-savings-goal'), {'goals': [
            {'id': 'emergency', 'priority': 'Aşağı prioritet', 'amount': 1500, 'savedAmount': 0, 'deadlineMonths': 12}]}, format='json')
        self.client.put(reverse('budget-recalculate'), {}, format='json')
        goals = self.goals()
        self.assertEqual([g['goal_id'] for g in goals], ['travel', 'car', 'emergency'])
        self.assertEqual((goals[0]['saved_amount'], goals[1]['saved_amount']), (1000, 2000))
        # a low-priority goal never pushes the high-priority, near-deadline goal off track
        self.assertTrue(goals[0]['on_track'], goals[0]['note'])
        _assert_month_math(self, self.table()['monthly_table'])
        self.assertTrue(all(len(m['goal_contributions']) == 3 for m in self.table()['monthly_table']))
        # duplicates are refused, nothing deleted
        r = self.client.post(reverse('add-savings-goal'), {'goals': [
            {'id': 'car', 'priority': 'Orta prioritet', 'amount': 1, 'deadlineMonths': 3}]}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(self.goals()), 3)

    def test_F_insufficient_capacity(self):
        _register(self.client, 'f@example.com')
        _answer(self.client, salary=2200, extra=0, rent=400, goals=[
            {'id': 'home', 'priority': 'Yuxarı prioritet', 'amount': 60000, 'savedAmount': 0, 'deadlineMonths': 12},
            {'id': 'car', 'priority': 'Orta prioritet', 'amount': 20000, 'savedAmount': 0, 'deadlineMonths': 12}])
        months = self.table()['monthly_table']
        _assert_month_math(self, months)
        for m in months:
            self.assertEqual(m['income'], 2200)
            self.assertEqual(m['housing'], 400)
            self.assertGreaterEqual(m['balance'], 0)   # goals never push Qalıq negative
            self.assertGreater(m['savings'], 0)        # real capacity is used ...
        required = (60000 + 20000) / 12
        self.assertLess(sum(m['savings'] for m in months), required * 12)  # ... but cannot fake the targets
        goals = self.goals()
        self.assertTrue(all(not g['on_track'] for g in goals))
        self.assertTrue(all(g['expected_amount_at_deadline'] < g['target_amount'] for g in goals))
        summary = self.client.get(reverse('financial-summary')).json()['data']
        self.assertEqual(len(summary['goal_warnings']), 2)
        self.assertTrue(summary['is_feasible'])

    def test_G_H_persistence_answers_and_exports(self):
        _register(self.client, 'g@example.com')
        _answer(self.client)
        self.client.post(reverse('add-savings-goal'), {'goals': [
            {'id': 'car', 'priority': 'Orta prioritet', 'amount': 10000, 'savedAmount': 2000, 'deadlineMonths': 24}]}, format='json')
        self.client.put(reverse('budget-recalculate'), {}, format='json')
        # "log out and in": a fresh client with a new token
        other = APIClient()
        token = other.post(reverse('register'), {**VALID_USER, 'email': 'g@example.com'}, format='json').json()['tokens']['access']
        other.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        goals = other.get(reverse('savings-goals-progress')).json()['data']
        self.assertEqual([(g['goal_id'], g['saved_amount']) for g in goals], [('travel', 1000), ('car', 2000)])
        answers = other.get(reverse('onboarding-answers')).json()['answers']['savingsGoals']
        self.assertEqual([(a['id'], a['savedAmount'], a['deadlineMonths']) for a in answers],
                         [('travel', '1000', '12'), ('car', '2000', '24')])
        import io
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(other.get(reverse('export-excel')).content))
        self.assertIn('Məqsədlər üzrə yığım', wb.sheetnames)
        pdf = other.get(reverse('export-pdf'))
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))


class DashboardEditAndSeasonTests(TestCase):
    """Requirements 1, 3, 4, 7 and 9 of the dashboard update."""

    def setUp(self):
        self.client = APIClient()
        _register(self.client, 'edits@example.com')
        _answer(self.client, credit={'monthly': 150, 'remaining': 3000, 'rate': 16, 'months': 20})
        self.client.post(reverse('add-savings-goal'), {'goals': [
            {'id': 'car', 'priority': 'Orta prioritet', 'amount': 10000, 'savedAmount': 2000, 'deadlineMonths': 24}]}, format='json')
        self.client.put(reverse('budget-recalculate'), {}, format='json')

    def table(self):
        return self.client.get(reverse('monthly-budget-table')).json()['monthly_table']

    def recalc(self, adjustments=(), regenerate=False):
        r = self.client.put(reverse('budget-recalculate'), {'adjustments': list(adjustments), 'regenerate': regenerate}, format='json')
        self.assertEqual(r.status_code, 200, r.json())

    def test_edit_recalculates_savings_and_goal_split_keeping_value(self):
        before = self.table()
        self.recalc([{'month_index': 2, 'category': 'restaurant', 'value': 400}])
        after = self.table()
        self.assertEqual(after[1]['restaurant'], 400)
        self.assertLess(after[1]['savings'] + after[1]['balance'], before[1]['savings'] + before[1]['balance'])
        _assert_month_math(self, after)
        self.assertNotEqual(after[1]['goal_contributions'], before[1]['goal_contributions'])

    def test_other_parts_and_savings_are_editable(self):
        self.recalc([{'month_index': 3, 'category': 'clothing', 'value': 10},
                     {'month_index': 3, 'category': 'online_shopping', 'value': 0},
                     {'month_index': 3, 'category': 'other_misc', 'value': 5},
                     {'month_index': 4, 'category': 'savings', 'value': 100}])
        months = self.table()
        _assert_month_math(self, months)
        self.assertEqual((months[2]['clothing'], months[2]['online_shopping'], months[2]['other_misc'], months[2]['other']), (10, 0, 5, 15))
        self.assertEqual(months[3]['savings'], 100)                  # user's Savings amount kept
        self.assertAlmostEqual(sum(months[3]['goal_contributions']), 100, places=2)
        self.assertGreater(months[3]['balance'], 0)                  # the rest stays as Qalıq

    def test_regenerate_after_edits_is_a_new_plan(self):
        self.recalc([{'month_index': 1, 'category': 'restaurant', 'value': 250}])
        before = self.table()
        self.recalc(regenerate=True)
        after = self.table()
        _assert_month_math(self, after)
        self.assertEqual(after[0]['restaurant'], 250)  # manual value still respected
        changed = {k for k in ('entertainment', 'food', 'utilities', 'transport', 'other', 'savings', 'balance')
                   if any(x[k] != y[k] for x, y in zip(before, after))}
        self.assertGreaterEqual(len(changed), 5)
        for x, y in zip(before, after):
            self.assertEqual((x['income'], x['housing'], x['credit']), (y['income'], y['housing'], y['credit']))

    def test_season_and_minimum_living_costs(self):
        answers = be.Answers(salary=2400, extra_income=0, housing_type='Kirayədir', housing_amount=500,
                             expenses=dict(food=400, utilities=120, transport=100, restaurant=150, clothing=80,
                                           entertainment=100, online_shopping=40, other_misc=40),
                             goals=[{'goal_id': 'car', 'custom_name': '', 'priority': 'Orta prioritet', 'amount': 30000,
                                     'saved': 0, 'deadline': 36}],
                             annual_budget_priority='Daha çox qənaət etmək')
        for variant in range(1, 8):
            months = be.build_plan(answers, variant=variant)['monthly_table']
            for m in months:
                self.assertGreaterEqual(m['food'], 0.9 * 400)       # realistic minimum living costs
                self.assertGreaterEqual(m['utilities'], 0.9 * 120)
                self.assertGreaterEqual(m['transport'], 0.9 * 100)
                self.assertGreaterEqual(m['balance'], 0)
            # expensive holiday / summer months save less than quiet months
            quiet = sum(months[i]['savings'] for i in (3, 4, 9)) / 3      # Apr, May, Oct
            busy = sum(months[i]['savings'] for i in (6, 7, 11)) / 3      # Jul, Aug, Dec
            self.assertLess(busy, quiet, variant)
            self.assertGreater(months[11]['restaurant'], months[9]['restaurant'])
