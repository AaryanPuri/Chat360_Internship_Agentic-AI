from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
from django.contrib.auth import get_user_model
import requests
from backend.settings import logger
import os


class RemoteBearerAuthentication(BaseAuthentication):
    """
    Custom DRF authentication class for remote Bearer token validation.
    """
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        url = os.getenv('REMOTE_AUTH_URL')
        headers = {
            'Authorization': auth_header,
            "Content-Type": "application/json",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                user_info = resp.json()
                User = get_user_model()
                email = user_info.get('email')
                if email:
                    user, created = User.objects.get_or_create(email=email, defaults={
                        'username': email,
                    })
                    user.first_name = user_info.get('first_name', '')
                    user.last_name = user_info.get('last_name', '')
                    user.is_active = user_info.get('is_active', True)
                    for field in ['phone_number', 'role', 'api_key', 'utc_offset', 'avatar']:
                        if hasattr(user, field) and user_info.get(field) is not None:
                            setattr(user, field, user_info.get(field))
                    user.save()
                    return (user, None)
                else:
                    raise exceptions.AuthenticationFailed('Invalid user info from remote service.')
            else:
                raise exceptions.AuthenticationFailed('Invalid token or remote auth failed.')
        except Exception as e:
            logger.error(f"RemoteBearerAuthentication: Exception: {e}")
            raise exceptions.AuthenticationFailed('Remote authentication error.')
