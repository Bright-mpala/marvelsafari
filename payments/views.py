from django.shortcuts import render

def payment_list(request):
    """List payments."""
    return render(request, 'payments/payment_list.html')
