from django import forms

from .models import Budget, Expense, ExpenseCategory, Income


class DateInput(forms.DateInput):
    input_type = 'date'


class StyledModelForm(forms.ModelForm):
    input_class = 'w-full rounded-2xl border border-slate-300 px-4 py-3 text-sm text-slate-900 focus:border-academy focus:outline-none focus:ring-2 focus:ring-rose-100'
    checkbox_class = 'h-4 w-4 rounded border-slate-300 text-academy focus:ring-academy'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs['class'] = self.checkbox_class
                continue
            classes = widget.attrs.get('class', '')
            widget.attrs['class'] = f"{classes} {self.input_class}".strip()
            if isinstance(widget, forms.Textarea):
                widget.attrs['rows'] = 3


class ExpenseCategoryForm(StyledModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'description', 'is_active', 'sort_order']


class ExpenseForm(StyledModelForm):
    class Meta:
        model = Expense
        fields = ['date', 'category', 'description', 'amount', 'receipt']
        widgets = {
            'date': DateInput(),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class BudgetForm(StyledModelForm):
    class Meta:
        model = Budget
        fields = ['category', 'period_type', 'year', 'month', 'amount', 'notes']


class IncomeForm(StyledModelForm):
    class Meta:
        model = Income
        fields = ['source', 'amount', 'date', 'description']
        widgets = {
            'date': DateInput(),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
