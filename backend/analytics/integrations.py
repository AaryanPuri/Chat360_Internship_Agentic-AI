import requests
# from requests.auth import HTTPBasicAuth
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import IntegrationFeature, Integrations
from backend.settings import logger
from rest_framework.views import APIView


class shopifyView(APIView):
    permission_classes = [IsAuthenticated]

    # Move FEATURE_HASH_MAPPING to class level (outside methods)
    FEATURE_HASH_MAPPING = {
        "order_tracking": "1001",
        "list_orders": "1002",
        "return_processing": "1003",
        "product_recommendation": "1004",
    }

    def post(self, request):
        user = request.user
        logger.info(f"Shopify integration POST request received for user: {user}")

        features = {
            "order_tracking": request.data.get("order_tracking", False),
            "product_recommendation": request.data.get("product_recommendation", False),
            "return_processing": request.data.get("return_processing", False),
            "list_orders": request.data.get("list_orders", False),
        }

        configs = {
            "order_tracking": request.data.get("order_tracking_config"),
            "product_recommendation": request.data.get("product_recommendation_config"),
            "return_processing": request.data.get("return_processing_config"),
            "list_orders": request.data.get("list_orders_config"),
        }

        for feature_name, is_enabled in features.items():
            config = configs.get(feature_name)
            feature_hash = self.FEATURE_HASH_MAPPING[feature_name]

            if is_enabled:
                # Create integration for this specific feature
                integration, created = Integrations.objects.get_or_create(
                    user=user,
                    name='shopify',
                    feature_name=feature_name,
                    defaults={'details': {}}
                )

                # Create or update IntegrationFeature
                feature, f_created = IntegrationFeature.objects.get_or_create(
                    integration=integration,
                    defaults={"hash": feature_hash, "config": config or {}, "is_active": True}
                )

                if not f_created:
                    feature.config = config or {}
                    feature.is_active = True
                    feature.save()
                    logger.info(f"Updated feature: {feature_name} with hash: {feature_hash}")
                else:
                    logger.info(f"Created feature: {feature_name} with hash: {feature_hash}")
            else:
                # Delete feature and integration when disabled
                try:
                    integration = Integrations.objects.get(
                        user=user,
                        name='shopify',
                        feature_name=feature_name
                    )
                    # Delete IntegrationFeature first
                    IntegrationFeature.objects.filter(integration=integration).delete()
                    # Then delete the Integration
                    integration.delete()
                    logger.info(f"Deleted feature: {feature_name} with hash: {feature_hash}")
                except Integrations.DoesNotExist:
                    logger.info(f"Feature {feature_name} not found — nothing to delete")

        return Response({'message': 'Shopify integrations processed.'}, status=200)

    def get(self, request):
        try:
            user = request.user
            logger.info(f"Shopify GET request received for user: {user}")
            data = {}
            features = ['order_tracking', 'list_orders', 'product_recommendation', 'return_processing']

            for feature in features:
                try:
                    integration = Integrations.objects.get(user=user, name='shopify', feature_name=feature)
                    feature_obj = IntegrationFeature.objects.filter(
                        integration=integration,
                        is_active=True
                    ).first()

                    if feature_obj:
                        data[feature] = True
                        data[f"{feature}_config"] = feature_obj.config
                    else:
                        data[feature] = False
                        data[f"{feature}_config"] = None

                except Integrations.DoesNotExist:
                    data[feature] = False
                    data[f"{feature}_config"] = None

            logger.debug(f"Shopify GET response: {data}")
            return Response(data, status=200)

        except Exception as e:
            logger.error(f"Error fetching Shopify integrations: {str(e)}")
            return Response({'error': 'Failed to fetch integrations'}, status=500)

    def put(self, request):
        user = request.user
        logger.info(f"Shopify PUT request received for user: {user}")
        features = {
            "order_tracking": request.data.get("order_tracking"),
            "list_orders": request.data.get("list_orders"),
            "product_recommendation": request.data.get("product_recommendation"),
            "return_processing": request.data.get("return_processing"),
        }

        configs = {
            "order_tracking": request.data.get("order_tracking_config"),
            "list_orders": request.data.get("list_orders_config"),
            "product_recommendation": request.data.get("product_recommendation_config"),
            "return_processing": request.data.get("return_processing_config"),
        }

        for feature_name, enabled in features.items():
            config = configs.get(feature_name)
            feature_hash = self.FEATURE_HASH_MAPPING[feature_name]

            if enabled:
                # Create integration for this specific feature
                integration, created = Integrations.objects.get_or_create(
                    user=user,
                    name='shopify',
                    feature_name=feature_name,
                    defaults={'details': {}}
                )

                # Create or update IntegrationFeature
                feature, f_created = IntegrationFeature.objects.get_or_create(
                    integration=integration,
                    defaults={'hash': feature_hash, 'config': config or {}, 'is_active': True}
                )

                if not f_created:
                    feature.config = config or {}
                    feature.is_active = True
                    feature.save()
                    logger.info(f"Updated feature: {feature_name} with hash: {feature_hash}")
                else:
                    logger.info(f"Created feature: {feature_name} with hash: {feature_hash}")
            else:
                # Delete feature and integration when disabled
                try:
                    integration = Integrations.objects.get(
                        user=user,
                        name='shopify',
                        feature_name=feature_name
                    )
                    # Delete IntegrationFeature first
                    deleted = IntegrationFeature.objects.filter(integration=integration).delete()
                    # Then delete the Integration
                    integration.delete()

                    if deleted[0]:
                        logger.info(f"Deleted feature: {feature_name}")
                    else:
                        logger.info(f"No feature found to delete: {feature_name}")
                except Integrations.DoesNotExist:
                    logger.info(f"No integration found for feature: {feature_name}")

        return Response("Shopify integration updated successfully", status=200)


def get_integration_details(email, technology, api_key):
    logger.debug(f"Fetching integration details for technology: {technology} with API key: {api_key}")
    technology = technology.lower()
    # return None
    token_genration_url = "https://app.chat360.io/api/auth/bitrix-tokens"
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "Cookie": "multidb_pin_writes=y"
    }

    try:
        logger.info("Sending POST request to Chat360 API...")
        response = requests.post(token_genration_url, headers=headers)
        logger.info(f"Received response with status code {response.status_code}")

        data = response.json()
        access_token = data.get("access")
        if access_token:
            logger.info("Access token retrieved successfully.")
        else:
            logger.error("Access token not found in the response.")
            raise ValueError("Missing 'access' token in response.")

        url = "https://staging.chat360.io/api/integration"
        logger.info(f"Integration URL: {url}, Email: {email}")
        headers = {
            "accept": "application/json, text/plain, */*",
            "authorization": f"Bearer {access_token}"
        }

        params = {"email": email}

        logger.info("Sending GET request to fetch integration details...")
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        integrations = response.json()
        logger.debug("Fetched response and integrations")

        # Filter by technology (case-insensitive match)
        for integration in integrations:
            if integration.get("technology", "").lower() == technology.lower():
                filtered = integration

        logger.info(f"Filtered integrations: {filtered}")
        logger.debug("here is the integration details")
        if not filtered:
            raise ValueError("no integration found for client")
        return filtered

    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None


class IntegrationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        logger.info(f"Integrations GET request received for user: {user}")

        # Get all integrations for this user
        integrations = Integrations.objects.filter(user=user).prefetch_related('features')  # uses related_name from FK

        response_data = []

        for integration in integrations:
            features = integration.features.filter(is_active=True)  # only include active features
            feature_data = []

            for feature in features:
                logger.debug(f"Feature object: hash={feature.hash}")
                feature_data.append({
                    "feature_name": integration.feature_name,
                    "hash": feature.hash,
                })

            response_data.append({
                "integration_name": integration.name,
                "details": integration.details or {},
                "features": feature_data
            })

        logger.debug(f"Integrations GET response: {response_data}")
        return Response(response_data, status=200)
