from django import template

register = template.Library()

ADVANCED_FIELDS = {"slug", "seo_title", "seo_description"}
DEFERRED_SECTIONS = {"Opções avançadas", "Auditoria", "Publicação"}


@register.simple_tag
def content_fieldsets(adminform, section="main"):
    if section == "main":
        return [fieldset for fieldset in adminform if fieldset.name not in DEFERRED_SECTIONS]
    fieldsets = [fieldset for fieldset in adminform if fieldset.name == section]
    if section == "Opções avançadas":
        # The enclosing details already provides the heading.
        for fieldset in fieldsets:
            fieldset.name = None
    return fieldsets


@register.simple_tag
def bilingual_rows(inline, advanced=False):
    if not (inline.has_add_permission or inline.has_change_permission):
        return []

    forms_by_language = {}
    unmatched = []
    for form in inline.formset.forms:
        if "language" not in form.fields:
            continue
        language = form["language"].value()
        if language in {"pt-br", "en"} and language not in forms_by_language:
            forms_by_language[language] = form
        else:
            unmatched.append(form)
    # A malformed POST must still show every field and its entered value/error.
    for language in ("pt-br", "en"):
        if language not in forms_by_language and unmatched:
            forms_by_language[language] = unmatched.pop(0)
    # Existing records can be ordered differently; pair by locale, never by index.
    forms = [
        (forms_by_language.get(code), label)
        for code, label in (("pt-br", "Português"), ("en", "Inglês"))
    ]
    field_names = dict.fromkeys(
        name for form, _ in forms if form is not None for name in form.fields
    )
    rows = []
    for name in field_names:
        if (name in ADVANCED_FIELDS) != advanced:
            continue
        fields = [
            {"field": form[name], "language": language}
            for form, language in forms
            if form is not None and name in form.fields and not form[name].is_hidden
        ]
        if fields:
            rows.append({"fields": fields, "help_text": fields[0]["field"].help_text})
    return rows
