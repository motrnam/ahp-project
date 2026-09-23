from django import template

register = template.Library()


@register.filter
def get_item(d, key):
    try:
        return d[key]
    except (KeyError, TypeError):
        return None


@register.simple_tag
def make_key(prefix, r, c, g):
    return f"{prefix}___{r}___{c}___{g}"

@register.simple_tag
def make_key_plus(prefix, r, c):
    return f"{prefix}___{r}___{c}"