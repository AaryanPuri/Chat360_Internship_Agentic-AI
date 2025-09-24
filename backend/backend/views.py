import httpx
from django.shortcuts import redirect
from django.http import HttpRequest, HttpResponse
from django.core.cache import cache
import os  # Assuming client ID/secret might come from env vars later
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny


# TODO: Move these to Django settings or environment variables
ZOHO_CLIENT_ID = "1000.65S5BUWES8VYXZA5JYV4K7JTZ1A9BX"
# IMPORTANT: Add your actual Zoho Client Secret here!
ZOHO_CLIENT_SECRET = os.environ.get("ZOHO_CLIENT_SECRET", "YOUR_ZOHO_CLIENT_SECRET")
ZOHO_REDIRECT_URI = "http://localhost:8000/oauth/zoho"
ZOHO_TOKEN_URL = "https://accounts.zoho.in/oauth/v2/token"
# TODO: Define where to redirect the user in the frontend after success/failure
FRONTEND_REDIRECT_SUCCESS_URL = "http://localhost:5173/integrations?status=success"
FRONTEND_REDIRECT_FAILURE_URL = "http://localhost:5173/integrations?status=error"


def zoho_oauth_callback(request: HttpRequest) -> HttpResponse:
    """Handles the callback from Zoho after user authorization."""
    error = request.GET.get('error')
    if error:
        # Handle error case: User denied access or other issue
        print(f"Zoho OAuth Error: {error}")
        return redirect(f"{FRONTEND_REDIRECT_FAILURE_URL}&error={error}")

    code = request.GET.get('code')
    # _location = request.GET.get('location') # Removed for now (unused)
    # _accounts_server = request.GET.get('accounts-server') # Removed for now (unused)

    if not code:
        # Handle error case: No code provided
        print("Zoho OAuth Error: No code received.")
        return redirect(f"{FRONTEND_REDIRECT_FAILURE_URL}&error=nocode")

    # Ensure we use the correct token URL based on the location/accounts_server if necessary
    # For simplicity, assuming the initial token URL is correct, but Zoho might require
    # using the one provided in accounts_server for token exchange in some cases.
    token_url = ZOHO_TOKEN_URL  # Or potentially dynamically construct based on accounts_server

    # Prepare data for token exchange
    token_payload = {
        'grant_type': 'authorization_code',
        'client_id': ZOHO_CLIENT_ID,
        'client_secret': ZOHO_CLIENT_SECRET,
        'redirect_uri': ZOHO_REDIRECT_URI,
        'code': code,
    }

    try:
        print("Exchanging Zoho code for token...")
        with httpx.Client() as client:
            response = client.post(token_url, data=token_payload, timeout=10)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            token_data = response.json()

        access_token = token_data.get('access_token')

        if not access_token:
            print(f"Zoho OAuth Error: No access token in response. Data: {token_data}")
            return redirect(f"{FRONTEND_REDIRECT_FAILURE_URL}&error=no_access_token")

        print("Successfully obtained Zoho tokens.", access_token)
        cache.set('zoho_access_token_user_default', access_token, timeout=60 * 60)

        # Redirect user back to the frontend
        return redirect(FRONTEND_REDIRECT_SUCCESS_URL)

    except httpx.RequestError as e:
        print(f"Zoho OAuth Error: Failed to exchange code for token: {e}")
        print(f"Request URL: {e.request.url}")
        return redirect(f"{FRONTEND_REDIRECT_FAILURE_URL}&error=token_exchange_failed")
    except Exception as e:
        print(f"Zoho OAuth Error: An unexpected error occurred: {e}")
        return redirect(f"{FRONTEND_REDIRECT_FAILURE_URL}&error=internal_error")


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        if not username or not password:
            return Response({'error': 'Username and password required.'}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.create_user(username=username, password=password)
        return Response({'message': f'User registered successfully. {user.created_at}'}, status=status.HTTP_201_CREATED)
