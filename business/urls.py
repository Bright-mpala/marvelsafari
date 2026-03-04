from django.urls import path
from . import views

app_name = 'business'

urlpatterns = [
    path('', views.business_dashboard, name='business_dashboard'),
    # Temporary alias until dedicated departments view/page is built
    path('departments/', views.business_dashboard, name='departments'),
    # Temporary alias until dedicated employees view/page is built
    path('employees/', views.business_dashboard, name='employees'),
]