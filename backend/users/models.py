from django.db import models
from django.contrib.auth.models import User


class FinancialInquirySession(models.Model):
    # pending = Gözləmədə, processing = Emal olunur, completed = Hazırdır,
    # failed = Xəta baş verib
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    HOUSING_CHOICES = [
        ('Özümündür', 'Özümündür'),
        ('Kirayədir', 'Kirayədir'),
        ('İpotekadır', 'İpotekadır'),
    ]

    ASSESSMENT_CHOICES = [
        ('good_manager', 'Pulumu yaxşı idarə edə bilirəm'),
        ('sometimes_breaks_plan', 'Bəzən planı poza bilirəm'),
        ('nothing_left', 'Ay sonuna pul qalmır'),
    ]

    SAVINGS_ABILITY_CHOICES = [
        ('can_save', 'Bəli, müntəzəm'),
        ('sometimes', 'Bəzən'),
        ('cannot_save', 'Xeyr'),
    ]

    ANNUAL_PRIORITY_CHOICES = [
        ('Daha çox qənaət etmək', 'Daha çox qənaət etmək'),
        ('Xərclərə nəzarət etmək', 'Xərclərə nəzarət etmək'),
        ('Borcları azaltmaq', 'Borcları azaltmaq'),
        ('Gəliri daha düzgün bölüşdürmək', 'Gəliri daha düzgün bölüşdürmək'),
        ('Gözlənilməz xərclərə hazır olmaq', 'Gözlənilməz xərclərə hazır olmaq'),
        ('Gələcək üçün pul toplamaq', 'Gələcək üçün pul toplamaq'),]

    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='financial_session')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Step 1: Salary
    salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Step 2: Extra Income
    has_extra_income = models.BooleanField(null=True, blank=True)
    extra_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Step 3: Housing
    housing_type = models.CharField(max_length=50, choices=HOUSING_CHOICES, null=True, blank=True)
    housing_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Step 4: Credit Flag
    has_credit = models.BooleanField(null=True, blank=True)

    # Step 6: Monthly Expenses
    expense_market = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expense_utilities = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expense_transport = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expense_restaurant = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expense_clothing = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expense_entertainment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expense_online_shopping = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expense_other = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Step 7: Recurring Expense Flags
    recurring_market = models.BooleanField(default=False)
    recurring_utilities = models.BooleanField(default=False)
    recurring_transport = models.BooleanField(default=False)
    recurring_restaurant = models.BooleanField(default=False)
    recurring_clothing = models.BooleanField(default=False)
    recurring_entertainment = models.BooleanField(default=False)
    recurring_online_shopping = models.BooleanField(default=False)
    recurring_other = models.BooleanField(default=False)

    # Step 8: Financial Assessment
    financial_assessment = models.CharField(max_length=50, choices=ASSESSMENT_CHOICES, null=True, blank=True)

    # Step 9: Monthly Savings Ability
    monthly_savings_ability = models.CharField(max_length=50, choices=SAVINGS_ABILITY_CHOICES, null=True, blank=True)

    # Step 10: Annual Budget Priority
    annual_budget_priority = models.CharField(max_length=50, choices=ANNUAL_PRIORITY_CHOICES, null=True, blank=True)

    recommended_monthly_savings = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    recommended_annual_savings = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    financial_status = models.CharField(max_length=100, blank=True)
    financial_status_description = models.TextField(blank=True)
    ai_response_text = models.TextField(blank=True)
    savings_goals_breakdown = models.JSONField(default=list, blank=True)
    monthly_table = models.JSONField(default=list, blank=True)
    annual_totals = models.JSONField(default=dict, blank=True)
    budget_comparison = models.JSONField(default=list, blank=True)

    # Plan bookkeeping (US-12 / US-17)
    plan_version = models.PositiveIntegerField(default=0)
    plan_text_source = models.CharField(max_length=20, blank=True)
    plan_error = models.TextField(blank=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    # Monthly amounts the user changed on the dashboard and applied with
    # "Planı yenilə": [{"month_index": 1-12, "category": ..., "value": ...}].
    # Cleared whenever the onboarding answers change.
    plan_adjustments = models.JSONField(default=list, blank=True)
    # Variation seed of the current plan (budget_engine "variant"). A new value
    # gives a genuine alternative plan; the same value reproduces the plan.
    plan_variant = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_monthly_expense(self):
        return (
            self.expense_market +
            self.expense_utilities +
            self.expense_transport +
            self.expense_restaurant +
            self.expense_clothing +
            self.expense_entertainment +
            self.expense_online_shopping +
            self.expense_other
        )

    def __str__(self):
        return f"{self.user.username} - Financial Session ({self.status})"


class Credit(models.Model):
    session = models.ForeignKey(FinancialInquirySession, on_delete=models.CASCADE, related_name='credits')
    monthly = models.DecimalField(max_digits=12, decimal_places=2)
    remaining = models.DecimalField(max_digits=12, decimal_places=2)
    rate = models.DecimalField(max_digits=5, decimal_places=2)
    months = models.PositiveIntegerField()

    def __str__(self):
        return f"Credit {self.id} for {self.session.user.username}"


class SavingsGoal(models.Model):
    GOAL_CHOICES = [
        ('emergency', 'Təcili vəziyyətlər fondu'),
        ('travel', 'Səyahət / Tətil'),
        ('home', 'Ev / Mənzil almaq'),
        ('car', 'Avtomobil almaq'),
        ('education', 'Təhsil / İnkişaf'),
        ('business', 'Biznes qurmaq'),
        ('wedding', 'Toy üçün'),
        ('other', 'Digər'),
    ]

    PRIORITY_CHOICES = [
        ('Yuxarı prioritet', 'Yüksək'),
        ('Orta prioritet', 'Orta'),
        ('Aşağı prioritet', 'Aşağı'),
    ]

    session = models.ForeignKey(FinancialInquirySession, on_delete=models.CASCADE, related_name='savings_goals')
    goal_id = models.CharField(max_length=50, choices=GOAL_CHOICES)
    custom_name = models.CharField(max_length=100, blank=True, null=True)
    priority = models.CharField(max_length=50, choices=PRIORITY_CHOICES, default='Orta prioritet')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    # Amount the user has already accumulated for this goal (progress) and the
    # requested deadline in months from the start of the plan.
    saved_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deadline_months = models.PositiveIntegerField(default=12)

    def __str__(self):
        return f"Goal {self.goal_id} ({self.amount}) for {self.session.user.username}"