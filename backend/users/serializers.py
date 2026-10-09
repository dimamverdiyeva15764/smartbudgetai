import re
from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Credit, SavingsGoal, FinancialInquirySession


class RegisterSerializer(serializers.ModelSerializer):
    fullName = serializers.CharField(
        write_only=True, required=True, max_length=150,
        error_messages={'required': 'Ad və soyad hissəsini doldurun.', 'blank': 'Ad və soyad hissəsini doldurun.'},
    )
    password = serializers.CharField(
        write_only=True, required=True, trim_whitespace=False,
        error_messages={'required': 'Şifrə daxil edilməlidir.', 'blank': 'Şifrə daxil edilməlidir.'},
    )
    email = serializers.EmailField(
        required=True,
        error_messages={
            'required': 'E-poçt daxil edilməlidir.',
            'blank': 'E-poçt daxil edilməlidir.',
            'invalid': 'Düzgün e-poçt ünvanı daxil edin.',
        },
    )

    class Meta:
        model = User
        fields = ('fullName', 'email', 'password')

    def validate_fullName(self, value):
        if not value.strip():
            raise serializers.ValidationError("Ad və soyad hissəsini doldurun.")
        return value.strip()

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Bu email artıq istifadə olunub.")
        return value

    def validate_password(self, value):
        if len(value) < 8 or not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', value):
            raise serializers.ValidationError(
                "Şifrə ən azı 8 simvol olmalı və xüsusi simvol ehtiva etməlidir."
            )
        return value

    def create(self, validated_data):
        full_name = validated_data['fullName'].strip()
        parts = full_name.split(' ', 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ''

        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            first_name=first_name,
            last_name=last_name,
            password=validated_data['password'],
        )
        return user


class SalaryUpdateSerializer(serializers.Serializer):
    salary = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate_salary(self, value):
        if value <= 0:
            raise serializers.ValidationError("Əmək haqqı müsbət ədəd olmalıdır.")
        return value


class ExtraIncomeUpdateSerializer(serializers.Serializer):
    hasExtraIncome = serializers.ChoiceField(choices=['Bəli', 'Xeyr'])
    extraIncome = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)

    def validate(self, attrs):
        has_extra = attrs['hasExtraIncome'] == 'Bəli'

        if has_extra:
            amount = attrs.get('extraIncome')
            if amount is None or amount <= 0:
                raise serializers.ValidationError(
                    {"extraIncome": "Əlavə gəlir varsa, məbləğ daxil edilməlidir."}
                )
        else:
            attrs['extraIncome'] = None

        return attrs


class HousingUpdateSerializer(serializers.Serializer):
    housingType = serializers.ChoiceField(choices=['Özümündür', 'Kirayədir', 'İpotekadır'])
    housingAmount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)

    def validate(self, attrs):
        housing_type = attrs['housingType']

        if housing_type == 'Özümündür':
            attrs['housingAmount'] = None
        else:
            amount = attrs.get('housingAmount')
            if amount is None or amount <= 0:
                field_name = 'Aylıq kirayə' if housing_type == 'Kirayədir' else 'Aylıq ipoteka'
                raise serializers.ValidationError(
                    {"housingAmount": f"{field_name} məbləği məcburidir."}
                )

        return attrs


class HasCreditSerializer(serializers.Serializer):
    hasCredit = serializers.ChoiceField(choices=['Bəli', 'Xeyr'])


class CreditSerializer(serializers.ModelSerializer):
    class Meta:
        model = Credit
        fields = ('id', 'monthly', 'remaining', 'rate', 'months')

    def validate_rate(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("İllik faiz 0 ilə 100 arasında rəqəm olmalıdır.")
        return value

    def validate_monthly(self, value):
        if value <= 0:
            raise serializers.ValidationError("Aylıq ödəniş 0-dan böyük olmalıdır.")
        return value

    def validate_remaining(self, value):
        if value <= 0:
            raise serializers.ValidationError("Qalıq məbləğ 0-dan böyük olmalıdır.")
        return value

    def validate_months(self, value):
        if value <= 0:
            raise serializers.ValidationError("Qalan ay sayı müsbət tam ədəd olmalıdır.")
        return value


class SavingsGoalSerializer(serializers.Serializer):
    # FIXED: was a plain CharField, accepting any string. Tied to the model's
    # actual GOAL_CHOICES now, so an invalid/typo'd goal id is rejected here
    # instead of silently reaching the database.
    id = serializers.ChoiceField(choices=[c[0] for c in SavingsGoal.GOAL_CHOICES])
    customName = serializers.CharField(required=False, allow_blank=True, max_length=100)

    priority = serializers.ChoiceField(choices=[c[0] for c in SavingsGoal.PRIORITY_CHOICES])
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    savedAmount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0, min_value=0,
                                           error_messages={'min_value': 'Artıq yığılmış məbləğ mənfi ola bilməz.'})
    deadlineMonths = serializers.IntegerField(required=False, default=12, min_value=1, max_value=600,
                                              error_messages={'min_value': 'Müddət ən azı 1 ay olmalıdır.',
                                                              'max_value': 'Müddət 600 aydan çox ola bilməz.',
                                                              'invalid': 'Müddət tam ədəd (ay) olmalıdır.'})

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Hədəf məbləği müsbət ədəd olmalıdır.")
        return value

    def validate(self, attrs):
        if attrs['id'] == 'other' and not attrs.get('customName', '').strip():
            raise serializers.ValidationError(
                {"customName": "'Digər' seçildikdə məqsədin adı daxil edilməlidir."}
            )
        if attrs.get('savedAmount', 0) > attrs['amount']:
            raise serializers.ValidationError(
                {"savedAmount": "Artıq yığılmış məbləğ hədəf məbləğindən çox ola bilməz."}
            )
        return attrs


class CreditsReplaceSerializer(serializers.Serializer):
    """PUT /financial-inquiry/credits/ — replaces the user's credit list in one request."""
    credits = CreditSerializer(many=True)


class SavingsGoalsUpdateSerializer(serializers.Serializer):
    goals = SavingsGoalSerializer(many=True)


class SavingsGoalsAddSerializer(serializers.Serializer):
    """POST /financial-inquiry/savings-goals/add/ — append goals ("Yeni plan əlavə et")."""
    goals = SavingsGoalSerializer(many=True, allow_empty=False)

    def validate_goals(self, value):
        ids = [g['id'] for g in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Eyni məqsəd iki dəfə seçilə bilməz.")
        return value

    def validate_goals(self, value):
        ids = [g['id'] for g in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Eyni məqsəd iki dəfə seçilə bilməz.")
        return value


class MonthlyExpensesSerializer(serializers.Serializer):
    market = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    utilities = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    transport = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    restaurant = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    clothing = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    entertainment = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    onlineShopping = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    other = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)

    def validate(self, attrs):
        for field, value in attrs.items():
            if value is not None and value < 0:
                raise serializers.ValidationError({field: "Mənfi məbləğ qəbul edilmir."})
        return attrs


EXPENSE_CATEGORY_KEYS = ['market', 'clothing', 'restaurant', 'entertainment', 'transport', 'onlineShopping', 'utilities', 'other']

class RecurringExpensesSerializer(serializers.Serializer):
    recurringExpenses = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )

    def validate_recurringExpenses(self, value):
        invalid = set(value) - set(EXPENSE_CATEGORY_KEYS)
        if invalid:
            raise serializers.ValidationError(f"Naməlum xərc kateqoriyası: {', '.join(invalid)}")
        return value


ASSESSMENT_TEXT_TO_CODE = {
    'Pulumu yaxşı idarə edə bilirəm': 'good_manager',
    'Bəzən planı poza bilirəm': 'sometimes_breaks_plan',
    'Ay sonuna pul qalmır': 'nothing_left',
}

class FinancialAssessmentSerializer(serializers.Serializer):
    financialAssessment = serializers.ChoiceField(choices=list(ASSESSMENT_TEXT_TO_CODE.keys()))


class MonthlySavingsAbilitySerializer(serializers.Serializer):
    monthlySavingsAbility = serializers.ChoiceField(
        choices=[c[0] for c in FinancialInquirySession.SAVINGS_ABILITY_CHOICES]
    )


VALID_ANNUAL_PRIORITIES = [c[0] for c in FinancialInquirySession.ANNUAL_PRIORITY_CHOICES]


class CompleteOnboardingSerializer(serializers.Serializer):
    """Step 10: the main priority is mandatory (US-11)."""
    annualBudgetPriority = serializers.ChoiceField(
        choices=VALID_ANNUAL_PRIORITIES,
        error_messages={
            'required': 'Əsas maliyyə prioritetini seçin.',
            'invalid_choice': 'Əsas maliyyə prioritetini seçin.',
            'blank': 'Əsas maliyyə prioritetini seçin.',
        },
    )
    monthlySavingsAbility = serializers.ChoiceField(
        choices=[c[0] for c in FinancialInquirySession.SAVINGS_ABILITY_CHOICES],
        required=False,
    )


class FinancialInquirySessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialInquirySession
        fields = '__all__'
        read_only_fields = ['user']

class PlanAdjustmentSerializer(serializers.Serializer):
    """One dashboard change applied with "Planı yenilə"."""
    month_index = serializers.IntegerField(min_value=1, max_value=12)
    category = serializers.ChoiceField(choices=["restaurant", "entertainment", "food", "utilities", "transport", "other",
                                                "clothing", "online_shopping", "other_misc", "savings"])
    value = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)


class RecalculateSerializer(serializers.Serializer):
    adjustments = PlanAdjustmentSerializer(many=True, required=False, default=list)
    # True for "Planı yenilə": always a genuinely new alternative plan.
    regenerate = serializers.BooleanField(required=False, default=False)
