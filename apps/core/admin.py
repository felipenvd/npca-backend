from django import forms
from unfold.admin import ModelAdmin, StackedInline


class BilingualContentAdmin(ModelAdmin):
    """Keep shared data first, paired content next and publication last."""

    change_form_template = "admin/bilingual_change_form.html"


class BilingualTranslationInline(StackedInline):
    """Render the existing, validated locale formsets as fixed field pairs."""

    template = "admin/edit_inline/bilingual.html"
    bilingual = True
    verbose_name_plural = "conteúdo em português e inglês"
    extra = 2
    max_num = 2
    can_delete = False

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        # Django generates a fresh form class here; don't change the source form.
        if "language" in formset.form.base_fields:
            formset.form.base_fields["language"].widget = forms.HiddenInput()
        return formset
