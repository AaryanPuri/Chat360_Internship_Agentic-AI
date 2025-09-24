"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse, StreamingHttpResponse
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .views import zoho_oauth_callback
from backend.views import RegisterView


def hello_api(request):
    return JsonResponse({"message": "Hello from Django API!"})


def stream_lorem(request):
    import time

    def lorem_stream():
        text = (
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
            "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
            "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. "
        )
        for word in text.split():
            yield word + ' '
            time.sleep(0.08)
    return StreamingHttpResponse(lorem_stream(), content_type='text/plain')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/hello/', hello_api),
    path('api/stream/', stream_lorem),
    path('api/analytics/', include('analytics.urls')),
    path('oauth/zoho', zoho_oauth_callback, name='zoho_oauth_callback'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/register/', RegisterView.as_view(), name='register'),
    path('api/',include('third_party_tasks.urls')),
]
