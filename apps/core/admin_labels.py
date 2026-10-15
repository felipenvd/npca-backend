from django.utils.html import format_html

CONDITIONAL_REQUIRED = {
    "events.event": {
        "start_time": ("is_all_day", "unchecked"),
        "end_time": ("is_all_day", "unchecked"),
        "online_url": ("modality", "online,hybrid"),
        "location_name": ("modality", "in_person,hybrid"),
    },
    "projects.project": {
        "end_date": ("situation", "completed"),
    },
}


def style_required_labels(form, model_label):
    """Style publication requirements without making draft fields mandatory."""
    conditions = CONDITIONAL_REQUIRED.get(model_label, {})
    for name, field in form.base_fields.items():
        label = str(field.label or "")
        if label.rstrip().endswith("*"):
            label = label.rstrip().removesuffix("*").rstrip()
            # Truly required fields already receive Unfold's red suffix.
            field.label = (
                label
                if field.required
                else format_html('{} <span class="npca-required-marker">*</span>', label)
            )
        elif name in conditions and not field.required:
            controller, values = conditions[name]
            field.label = format_html(
                '{} <span class="npca-required-marker" data-required-controller="{}" '
                'data-required-values="{}" hidden>*</span>',
                label,
                controller,
                values,
            )
    return form
