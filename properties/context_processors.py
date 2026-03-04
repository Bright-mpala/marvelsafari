from .forms import PropertySearchForm

def search_form(request):
    """Add property search form to context."""
    return {
        'property_search_form': PropertySearchForm(request.GET or None)
    }