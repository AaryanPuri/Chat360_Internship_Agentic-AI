from django.urls import path, include


urlpatterns = [
    path("dlpl/", include("third_party_tasks.client_dlpl.urls")),
]

