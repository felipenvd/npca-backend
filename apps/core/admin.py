from django import forms
from django.conf import settings
from django.templatetags.static import static
from unfold.admin import ModelAdmin, StackedInline

from .admin_labels import style_required_labels


class NPCAAdmin(ModelAdmin):
    """Share the admin's select component across forms and editable lists."""

    class Media:
        extra = "" if settings.DEBUG else ".min"
        js = (
            f"admin/js/vendor/jquery/jquery{extra}.js",
            "admin/js/vendor/select2/select2.full.js",
            "admin/js/jquery.init.js",
            f"{static('core/admin/select.js')}?v=2",
            "core/admin/required_labels.js",
        )
        css = {
            "screen": (
                "admin/css/vendor/select2/select2.css",
                "admin/css/autocomplete.css",
                f"{static('core/admin/select.css')}?v=2",
                "core/admin/required_labels.css",
            ),
        }

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        return style_required_labels(form, self.model._meta.label_lower)


class BilingualContentAdmin(NPCAAdmin):
    """Show publication first, followed by shared data and paired content."""

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
        style_required_labels(formset.form, self.parent_model._meta.label_lower)
        return formset
