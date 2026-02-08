from django.urls import path

from apps.api.views import AmountDenominationListView, CalculateTotalView, GenerateBillView

urlpatterns = [
    path('denominations-list/', AmountDenominationListView.as_view(), name='denomination-list'),
    path('calculate-total/', CalculateTotalView.as_view(), name='calculate-total'),
    path('generate-bill/', GenerateBillView.as_view(), name='generate-bill'),
]
