from django import template

register = template.Library()

@register.filter(name="getfield")
def getfield(obj, attr_name):
    """
    Uso en template: {{ row|getfield:"severity" }}
    Retorna dinámicamente row.severity
    """
    # getattr() de Python: getattr(obj, "campo", None)
    return getattr(obj, attr_name, None)
