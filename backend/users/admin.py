from django.contrib import admin
from .models import FinancialInquirySession, Credit, SavingsGoal


class CreditInline(admin.TabularInline):
    model = Credit
    extra = 0


class SavingsGoalInline(admin.TabularInline):
    model = SavingsGoal
    extra = 0


@admin.register(FinancialInquirySession)
class FinancialInquirySessionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 
        'status', 
        'salary', 
        'housing_type', 
        'annual_budget_priority', 
        'created_at', 
        'updated_at'
    )
    list_filter = ('status', 'housing_type', 'annual_budget_priority', 'created_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'total_monthly_expense')
    
    inlines = [CreditInline, SavingsGoalInline]

    fieldsets = (
        ('User & Status', {
            'fields': ('user', 'status')
        }),
        ('Income & Housing', {
            'fields': ('salary', 'has_extra_income', 'extra_income', 'housing_type', 'housing_amount')
        }),
        ('Expenses (Step 6)', {
            'fields': (
                'expense_market', 
                'expense_utilities', 
                'expense_transport', 
                'expense_restaurant', 
                'expense_clothing', 
                'expense_entertainment', 
                'expense_online_shopping', 
                'expense_other',
                'total_monthly_expense'
            )
        }),
        ('Recurring Expenses (Step 7)', {
            'fields': (
                'recurring_market', 
                'recurring_utilities', 
                'recurring_transport', 
                'recurring_restaurant', 
                'recurring_clothing', 
                'recurring_entertainment', 
                'recurring_online_shopping', 
                'recurring_other'
            )
        }),
        ('Assessments & Preferences', {
            'fields': ('has_credit', 'financial_assessment', 'monthly_savings_ability', 'annual_budget_priority')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Credit)
class CreditAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_user', 'monthly', 'remaining', 'rate', 'months')
    search_fields = ('session__user__username', 'session__user__email')

    def get_user(self, obj):
        return obj.session.user.username
    get_user.short_description = 'User'


@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_user', 'goal_id', 'custom_name', 'priority', 'amount')
    list_filter = ('goal_id', 'priority')
    search_fields = ('session__user__username', 'session__user__email', 'custom_name')

    def get_user(self, obj):
        return obj.session.user.username
    get_user.short_description = 'User'