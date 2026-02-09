from django.urls import path

from apps.template import views

urlpatterns = [
    path('', views.billing_form, name='billing-form'),
    path('bill/<str:order_code>/', views.billing_result, name='billing-result'),
    path('history/', views.purchase_history, name='purchase-history'),
]
