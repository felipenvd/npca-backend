import nh3

ALLOWED_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "div",
    "em",
    "h2",
    "h3",
    "h4",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
}
ALLOWED_ATTRIBUTES = {"a": {"href", "target", "title"}}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


def sanitize_rich_text(value: str) -> str:
    """Return the restricted HTML subset accepted for editorial content."""
    return nh3.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        clean_content_tags={"script", "style"},
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer",
    ).strip()
