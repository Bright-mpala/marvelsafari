from django.shortcuts import render


def _render_error(request, template_name, status_code, extra_context=None):
    """Shared renderer for branded error pages."""
    context = extra_context or {}
    return render(request, template_name, context=context, status=status_code)


def custom_400(request, exception):
    return _render_error(request, '400.html', 400)


def custom_403(request, exception):
    return _render_error(request, '403.html', 403)


def custom_404(request, exception):
    return _render_error(request, '404.html', 404)


def custom_500(request):
    return _render_error(request, '500.html', 500)


def custom_505(request, exception=None):
    return _render_error(request, '505.html', 505)
