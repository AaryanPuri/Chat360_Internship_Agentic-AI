from django.urls import path
from .api import (
    PatientFamily,
    PatientAddresses,
    RedirectToShortUrl,
    ReportStatusByLabNo
)


urlpatterns = [
    path("patient/family", PatientFamily.as_view()),
    path("patient/addresses", PatientAddresses.as_view()),
    path("report/status-by-lab-no", ReportStatusByLabNo.as_view()),
    path("payment-redirect", RedirectToShortUrl.as_view())
]