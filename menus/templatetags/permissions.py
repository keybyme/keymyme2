from django import template

register = template.Library()


@register.filter
def has_module_access(user, module_codename):
    """Usage: {% if request.user|has_module_access:"contacts" %} — used in
    base.html to hide nav links the user doesn't have access to."""
    if not user.is_authenticated:
        return False
    return user.has_module_access(module_codename)
