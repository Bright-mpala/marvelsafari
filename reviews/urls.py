# urls.py
from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    path('', views.review_list, name='review_list'),
    path('my-reviews/', views.my_reviews, name='my_reviews'),
    path('property/<int:property_id>/', views.property_reviews, name='property_reviews'),
    path('create/<uuid:booking_id>/', views.review_create, name='review_create'),
    path('<int:pk>/', views.review_detail, name='review_detail'),
    path('<int:pk>/helpful/', views.review_helpful, name='review_helpful'),
    path('<int:pk>/report/', views.review_report, name='review_report'),
]