from rest_framework.views import APIView
from rest_framework import status
from django.http import StreamingHttpResponse
import os
import json
from openai import OpenAI
from django.utils import timezone
from uuid import uuid4

from analytics.integrations import get_integration_details
from .tools import (analytics_tools,
                    AGENT_TOOLS,
                    WEBHOOK_TOOLS,
                    INTEGRATION_TOOLS
                    )
from .constants import (
    ANALYTICS_SYSTEM_PROMPT,
    GENERATE_TEST_SUITE_PROMPT,
    TEST_GENERATION_MODEL
)
import requests
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import (
    AssistantConfiguration,
    IntegrationFeature,
    Integrations,
    KnowledgeBase,
    TestSuite,
    WebsiteLink,
    KnowledgeFile,
    KnowledgeExcel,
    UserTool
)
from .serializers import (
    AssistantConfigurationSerializer,
    TestSuiteSerializer,
    WebsiteLinkSerializer,
    KnowledgeFileSerializer,
    KnowledgeExcelSerializer,
    AssistantConfigurationWithToolsSerializer,
)
from rest_framework.generics import (
    RetrieveUpdateAPIView,
    ListAPIView,
)
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import uuid
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404
from jinja2 import Template
from rest_framework.decorators import (
    api_view,
    permission_classes,
)
import redis
from django.conf import settings
from .tasks import (
    fetch_all_products,
    get_fulfillment_line_items_by_order_id,
    get_order_id_by_name,
    get_product_recommendation,
    order_tracking_with_order_id,
    get_shopify_orders,
    remove_prefix_and_suffix,
    return_processing,
    run_test_task,
    build_final_prompt,
    index_knowledge_base_task,
    refine_query,
    get_data_from_excel,
)
from celery.result import AsyncResult
from pinecone import Pinecone
import time
from .indexing import retrieve
from backend.settings import logger
from .functions import user_tool_to_openai_tool, execute_user_tool
from django.contrib.auth import get_user_model
from .tasks import export_all_rooms_data_to_excel

User = get_user_model()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Setup Redis connection
redis_client = redis.StrictRedis(
    host=getattr(settings, 'REDIS_HOST', 'redis'),
    port=getattr(settings, 'REDIS_PORT', 6379),
    db=0,
    decode_responses=True
)


def get_response(messages):
    messages = [{
        "role": "system",
        "content": ANALYTICS_SYSTEM_PROMPT
    }] + messages

    logger.info("Initiating OpenAI chat completion stream.")
    try:
        while True:
            completion = client.chat.completions.create(
                model="gpt-4.1",
                messages=messages,
                stream=True,
                tools=analytics_tools,
                tool_choice="auto",
                temperature=0.0,
            )
            current_tool_calls = {}
            tool_call_results = []
            finish_reason = None
            for chunk in completion:
                logger.debug("Received chunk")
                if not chunk.choices:
                    logger.warning("Received chunk with no choices.")
                    continue
                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason
                logger.debug(f"get_response | Delta: {delta}, Finish Reason: {finish_reason}")

                if delta.tool_calls:
                    logger.info("Processing tool call chunks.")
                    for tool_call_chunk in delta.tool_calls:
                        index = tool_call_chunk.index
                        tc_name = tool_call_chunk.function.name if tool_call_chunk.function else 'N/A'
                        logger.debug(f"Processing tool call chunk index {index}: id={tool_call_chunk.id}, name={tc_name}")
                        if index not in current_tool_calls:
                            if tool_call_chunk.id and tool_call_chunk.function and tool_call_chunk.function.name:
                                logger.debug(f"New tool call: id={tool_call_chunk.id}, name={tool_call_chunk.function.name}")
                                current_tool_calls[index] = {
                                    "id": tool_call_chunk.id,
                                    "type": "function",
                                    "name": tool_call_chunk.function.name,
                                    "arguments": tool_call_chunk.function.arguments or ""
                                }
                            else:
                                logger.warning(f"Tool call chunk index {index} missing id/func info.")
                        else:
                            if tool_call_chunk.function and tool_call_chunk.function.arguments:
                                tc_id = current_tool_calls[index]['id']
                                logger.debug(f"Appending args to tool id {tc_id}: {tool_call_chunk.function.arguments}")
                                current_tool_calls[index]["arguments"] += tool_call_chunk.function.arguments
                            else:
                                logger.debug(f"No new args in chunk for tool index {index}.")

                if finish_reason == "tool_calls":
                    logger.info(f"Finish reason 'tool_calls' detected. Processing {len(current_tool_calls)} tool calls.")
                    tool_call_results = []
                    for index, tool_call in current_tool_calls.items():
                        tool_call_id = tool_call.get("id", f"unknown_id_{index}")
                        tool_name = tool_call.get("name", "unknown_name")
                        tool_args_str = tool_call.get("arguments", "")
                        logger.info(f"""
                                    Processing collected tool call: id={tool_call_id}, name={tool_name}, args='{tool_args_str}'
                                    """)

                        if tool_name == "get_data_from_database":
                            try:
                                logger.debug(f"Attempting to parse JSON arguments for tool call {tool_call_id}")
                                args = json.loads(tool_args_str)
                                description = args.get("description", "Fetching data from database...")
                                query = args.get("query")
                                logger.info(f"Parsed arguments for {tool_name}: description='{description}', query='{query}'")

                                logger.debug(f"Yielding 'thinking' state for tool call {tool_call_id}")
                                yield json.dumps({"type": "thinking", "description": description}) + "\n"

                                if query:
                                    api_url = os.getenv("WHATSAPP_ANALYTICS_URL")
                                    headers = {
                                        'Content-Type': 'application/json',
                                        'Cookie': 'multidb_pin_writes=y'
                                    }
                                    data = {"query": query}
                                    logger.info(f"Executing API call for {tool_name} to {api_url}")
                                    logger.debug(f"Request Headers: {headers}")
                                    logger.debug(f"Request Data: {data}")

                                    try:
                                        response = requests.post(api_url, headers=headers, json=data, timeout=30)
                                        logger.info(
                                            f"""
                                            API call to {api_url} completed with status code: {response.status_code}
                                            """
                                        )
                                        logger.debug(f"API Response Headers: {response.headers}")
                                        result_data = response.json()
                                        logger.debug(f"API Response JSON Data: {result_data}")
                                        response.raise_for_status()

                                        if isinstance(result_data, dict) and ("table_data" in result_data):
                                            table = result_data.get("table") or result_data.get("table_data")
                                            yield json.dumps({"type": "table_data", "data": table}) + "\n"
                                        if isinstance(result_data, dict) and ("graph_data" in result_data):
                                            graph = result_data.get("graph") or result_data.get("graph_data")
                                            yield json.dumps({"type": "graph_data", "data": graph}) + "\n"

                                        tool_call_results.append({
                                            "role": "tool",
                                            "tool_call_id": tool_call_id,
                                            "content": json.dumps(result_data)
                                        })
                                        logger.info(f"Successfully processed tool call {tool_call_id} and got result.")

                                    except requests.exceptions.Timeout:
                                        logger.error(f"API call to {api_url} timed out.", exc_info=True)
                                        tool_call_results.append({
                                            "role": "tool", "tool_call_id": tool_call_id,
                                            "content": json.dumps({"error": "API call timed out."})
                                        })
                                    except requests.exceptions.RequestException as e:
                                        logger.error(f"API call to {api_url} failed: {e}", exc_info=True)
                                        tool_call_results.append({
                                            "role": "tool", "tool_call_id": tool_call_id,
                                            "content": json.dumps({"error": "API call failed."})
                                        })
                                    except json.JSONDecodeError as e:
                                        logger.error(f"Failed to decode JSON from {api_url}: {e}", exc_info=True)
                                        logger.debug(f"Raw API response text: {response.text}")
                                        tool_call_results.append({
                                            "role": "tool",
                                            "tool_call_id": tool_call_id,
                                            "content": json.dumps({"error": "Invalid API JSON response."})
                                        })
                                else:
                                    logger.warning(f"Tool {tool_call_id} ({tool_name}) missing 'query'.")
                                    tool_call_results.append(
                                        {
                                            "role": "tool", "tool_call_id": tool_call_id,
                                            "content": json.dumps({"error": "Missing query argument"})
                                        }
                                    )

                            except json.JSONDecodeError as e:
                                logger.error(
                                    f"Error decoding args for {tool_call_id}: '{tool_args_str}'. Err: {e}",
                                    exc_info=True
                                )
                                yield json.dumps({"type": "thinking", "description": "Error processing tool args..."}) + "\n"
                                tool_call_results.append({
                                    "role": "tool", "tool_call_id": tool_call_id,
                                    "content": json.dumps({"error": "Invalid args format."})
                                })
                            except Exception as e:
                                logger.error(
                                    f"Unexpected error processing tool {tool_call_id} ({tool_name}): {e}",
                                    exc_info=True
                                )
                                tool_call_results.append({
                                    "role": "tool", "tool_call_id": tool_call_id,
                                    "content": json.dumps({"error": f"Unexpected tool processing error: {e}"})
                                })
                        elif tool_name == "make_graph":
                            try:
                                logger.debug(f"Attempting to parse JSON arguments for tool call {tool_call_id}")
                                args = json.loads(tool_args_str)
                                x_label = args.get("x_label", "X Axis")
                                y_label = args.get("y_label", "Y Axis")
                                x_coordinates = args.get("x_coordinates", [])
                                y_coordinates = args.get("y_coordinates", [])
                                description = args.get("description", "Graph")
                                logger.info(
                                    f"""
                                    arguments for make_graph:
                                    x_label='{x_label}',
                                    y_label='{y_label}',
                                    description='{description}'
                                    """
                                )

                                yield json.dumps({
                                    "type": "graph_data",
                                    "data": {
                                        "x_label": x_label,
                                        "y_label": y_label,
                                        "x_coordinates": x_coordinates,
                                        "y_coordinates": y_coordinates
                                    }
                                }) + "\n"

                                tool_call_results.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call_id,
                                    "content": json.dumps({
                                        "x_label": x_label,
                                        "y_label": y_label,
                                        "x_coordinates": x_coordinates,
                                        "y_coordinates": y_coordinates
                                    })
                                })
                                logger.info(f"Successfully processed make_graph tool call {tool_call_id}.")
                            except Exception as e:
                                logger.error(
                                    f"Error processing make_graph tool call {tool_call_id}: {e}",
                                    exc_info=True
                                )
                                tool_call_results.append({
                                    "role": "tool", "tool_call_id": tool_call_id,
                                    "content": json.dumps({"error": f"Unexpected error in make_graph: {e}"})
                                })
                        elif tool_name == "make_bar_graph":
                            try:
                                args = json.loads(tool_args_str)
                                yield json.dumps({
                                    "type": "bar_graph_data",
                                    "data": args
                                }) + "\n"
                                tool_call_results.append({
                                    "role": "tool", "tool_call_id": tool_call_id,
                                    "content": json.dumps(args)
                                })
                            except Exception as e:
                                logger.error(
                                    f"Error processing make_bar_graph tool call {tool_call_id}: {e}",
                                    exc_info=True
                                )
                                tool_call_results.append({
                                    "role": "tool", "tool_call_id": tool_call_id,
                                    "content": json.dumps({"error": f"Unexpected error in make_bar_graph: {e}"})
                                })
                        elif tool_name == "make_line_graph":
                            try:
                                args = json.loads(tool_args_str)
                                yield json.dumps({
                                    "type": "line_graph_data",
                                    "data": args
                                }) + "\n"
                                tool_call_results.append({
                                    "role": "tool", "tool_call_id": tool_call_id,
                                    "content": json.dumps(args)
                                })
                            except Exception as e:
                                logger.error(
                                    f"Error processing make_line_graph tool call {tool_call_id}: {e}",
                                    exc_info=True
                                )
                                tool_call_results.append({
                                    "role": "tool", "tool_call_id": tool_call_id,
                                    "content": json.dumps({"error": f"Unexpected error in make_line_graph: {e}"})
                                })
                        elif tool_name == "make_area_graph":
                            try:
                                args = json.loads(tool_args_str)
                                yield json.dumps({
                                    "type": "area_graph_data",
                                    "data": args
                                }) + "\n"
                                tool_call_results.append({
                                    "role": "tool", "tool_call_id": tool_call_id,
                                    "content": json.dumps(args)
                                })
                            except Exception as e:
                                logger.error(
                                    f"Error processing make_area_graph tool call {tool_call_id}: {e}",
                                    exc_info=True
                                )
                                tool_call_results.append({
                                    "role": "tool", "tool_call_id": tool_call_id,
                                    "content": json.dumps(
                                        {
                                            "error": f"Unexpected error in make_area_graph: {e}"
                                        }
                                    )
                                })
                        elif tool_name == "make_doughnut_graph":
                            try:
                                args = json.loads(tool_args_str)
                                yield json.dumps({
                                    "type": "doughnut_graph_data",
                                    "data": args
                                }) + "\n"
                                tool_call_results.append({
                                    "role": "tool", "tool_call_id": tool_call_id,
                                    "content": json.dumps(args)
                                })
                            except Exception as e:
                                logger.error(
                                    f"Error processing make_doughnut_graph tool call {tool_call_id}: {e}",
                                    exc_info=True
                                )
                                tool_call_results.append({
                                    "role": "tool", "tool_call_id": tool_call_id,
                                    "content": json.dumps({"error": f"Unexpected error in make_doughnut_graph: {e}"})
                                })
                        else:
                            logger.warning(f"Unhandled tool call: id={tool_call_id}, name={tool_name}")
                            tool_call_results.append({
                                "role": "tool", "tool_call_id": tool_call_id,
                                "content": json.dumps({"error": f"Tool '{tool_name}' not implemented."})
                            })

                    if tool_call_results:
                        logger.info("Finished processing tool calls for this round. Preparing to send results back to OpenAI.")
                        logger.debug(f"Tool call results being sent: {tool_call_results}")
                        logger.debug("Appending original assistant tool_calls message to history.")
                        messages.append(
                            {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": tc["id"],
                                        "type": tc.get("type", "function"),
                                        "function": {
                                            "name": tc["name"],
                                            "arguments": tc["arguments"]
                                        }
                                    }
                                    for tc in current_tool_calls.values()
                                ]
                            }
                        )
                        logger.debug("Appending tool results messages to history.")
                        messages.extend(tool_call_results)
                        logger.debug(f"Messages history after adding tool calls and results: {messages}")
                        break
                elif finish_reason == "stop":
                    logger.info("Finish reason 'stop' detected. Completion finished.")
                    break
                elif delta.content is not None:
                    logger.debug(f"Yielding content token: {delta.content}")
                    yield json.dumps({"type": "token", "content": delta.content}) + "\n"
                elif finish_reason:
                    logger.warning(f"Unhandled finish reason encountered: {finish_reason}")
            if finish_reason == "tool_calls":
                continue
            else:
                break

    except Exception as e:
        logger.error(f"Error processing OpenAI stream: {e}", exc_info=True)
        yield json.dumps({"type": "error", "content": "Stream processing error."}) + "\n"
    finally:
        logger.info("Exiting get_response generator.")
        yield "\n"


# Helper to get all tools for a user (static + dynamic)
def get_agent_tools_for_user(user, webhook=False, agent_uuid=None):
    logger.info(f"get-agent_tools | Fetching agent tools for user, webhook: {webhook}")
    static_tools = []
    static_tools.extend(AGENT_TOOLS)
    if webhook:
        tools = static_tools + WEBHOOK_TOOLS
    else:
        tools = static_tools

    agent = AssistantConfiguration.objects.filter(assistant_uuid=agent_uuid).first()
    if not agent:
        logger.warning(f"No agent found for UUID: {agent_uuid}")
        return tools

    user_tools = []
    integration_tools = []

    for tool_uuid in agent.selected_tools:
        logger.debug(f"Checking tool UUID: {tool_uuid}")

        if user:
            user_tool = UserTool.objects.filter(user=user, uuid=tool_uuid).first()
            if user_tool:
                logger.debug(f"Found user tool: {user_tool.name}")
                user_tools.append(user_tool)
    if user:
        user_integrations = Integrations.objects.filter(user=user)
        all_features = IntegrationFeature.objects.filter(integration__in=user_integrations, is_active=True)

        for tool in agent.integration_tools:
            logger.debug(f"Integration tool selected by agent: {agent.integration_tools}")
            matching_feature = all_features.filter(hash=tool).first()

            if matching_feature:
                integration_tool = INTEGRATION_TOOLS.get(tool)

                if integration_tool:
                    integration_tools.append(integration_tool)
                else:
                    logger.warning(f"No static tool definition found for feature: {tool}")
            else:
                logger.warning(f"Feature '{tool}' not active for user: {user}")

    # Convert user tools to OpenAI format
    for tool in user_tools:
        tools.append(user_tool_to_openai_tool(tool))

    # Add all function definitions from integration tools
    tools += integration_tools

    logger.debug(f"get_agent_tools_for_user | Final tools registered with OpenAI: {[t.get('function', {}).get('name') for t in tools]}")
    return tools


class AnalyticsChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info(f"Received POST request for AnalyticsChatView from {request.META.get('REMOTE_ADDR')}")
        try:
            messages = request.data.get("messages")
            logger.debug(f"Request messages payload: {messages}")
            if not messages:
                logger.warning("Request received with no messages payload.")
                return StreamingHttpResponse(
                    json.dumps({"error": "No messages provided."}) + "\n",
                    content_type="application/json",
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.info("Calling get_response to generate streaming response.")
            response_stream = get_response(messages)
            return StreamingHttpResponse(
                response_stream,
                content_type="application/json; charset=utf-8",
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error in AnalyticsChatView before streaming started: {e}", exc_info=True)
            return StreamingHttpResponse(
                json.dumps(
                    {
                        "error": f"Failed to initiate request processing: {e}"
                    }
                ) + "\n",
                content_type="application/json",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        def safe_str(val):
            return str(val) if val is not None else ""
        return Response({
            "username": safe_str(getattr(user, "username", "")),
            "first_name": safe_str(getattr(user, "first_name", "")),
            "last_name": safe_str(getattr(user, "last_name", "")),
            "email": safe_str(getattr(user, "email", "")),
            "avatar": safe_str(getattr(user, "avatar", "")),
        })


class AssistantConfigurationView(RetrieveUpdateAPIView):
    queryset = AssistantConfiguration.objects.all()
    serializer_class = AssistantConfigurationSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        obj, created = AssistantConfiguration.objects.get_or_create(id=1)
        return obj


class AssistantConfigListView(ListAPIView):
    serializer_class = AssistantConfigurationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not self.request.user or not getattr(self.request.user, 'is_authenticated', False):
            logger.warning("User is not authenticated, returning empty queryset.")
            return AssistantConfiguration.objects.none()
        return AssistantConfiguration.objects.filter(
            user=self.request.user,
            is_deleted=False
        ).order_by('-updated_at')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = [
            {
                'assistant_name': obj.assistant_name,
                'updated_at': obj.updated_at,
                'assistant_uuid': str(obj.assistant_uuid),
                'selected_tools': obj.selected_tools if hasattr(obj, 'selected_tools') else [],
                'integration_tools': obj.selected_tools if hasattr(obj, 'integration_tools') else [],
                'selected_boards': obj.selected_boards if hasattr(obj, 'selected_boards') else [],
            }
            for obj in queryset
        ]
        return Response(data)


class AssistantConfigRetrieveUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, uuid):
        config = get_object_or_404(
            AssistantConfiguration,
            assistant_uuid=uuid,
            user=request.user,
            is_deleted=False
        )
        serializer = AssistantConfigurationSerializer(config)
        data = serializer.data
        data['agent_name'] = getattr(config, 'agent_name', 'Agent360')
        data['organisation_name'] = getattr(config, 'organisation_name', None)
        data['selected_tools'] = getattr(config, 'selected_tools', [])
        # Only include the knowledge base uuid (or None)
        data['knowledge_base'] = str(config.knowledge_base.uuid) if config.knowledge_base else None
        data['selected_boards'] = getattr(config, 'selected_boards', [])
        if config.integration_tools:
            data['integration_tools'] = config.integration_tools

        # Get all integrations and their features
        integrations = Integrations.objects.filter(user=request.user)
        integrations_payload = []

        for integration in integrations:
            features = integration.features.filter(is_active=True)
            integrations_payload.append({
                "integration_name": integration.name,
                "details": integration.details or {},
                "features": [
                    {
                        "feature_name": integration.feature_name,
                        "hash": f.hash
                    }
                    for f in features
                ]
            })

        data["integrations"] = integrations_payload
        return Response(data)

    def put(self, request, uuid):
        config = get_object_or_404(
            AssistantConfiguration,
            assistant_uuid=uuid,
            user=request.user,
            is_deleted=False
        )
        serializer = AssistantConfigurationSerializer(
            config, data=request.data,
            partial=True
        )
        examples = request.data.get("examples")
        goal = request.data.get("goal")
        if examples is not None:
            config.examples = examples
        if goal is not None:
            config.goal = goal
        use_last_user_language = request.data.get("use_last_user_language", True)
        languages = request.data.get("languages")
        config.use_last_user_language = use_last_user_language
        config.languages = languages
        enable_emojis = request.data.get("enable_emojis")
        if enable_emojis is not None:
            config.enable_emojis = bool(enable_emojis)
        answer_competitor_queries = request.data.get("answer_competitor_queries")
        if answer_competitor_queries is not None:
            config.answer_competitor_queries = bool(answer_competitor_queries)
        competitor_response_bias = request.data.get("competitor_response_bias")
        if competitor_response_bias in ("genuine", "biased"):
            config.competitor_response_bias = competitor_response_bias
        selected_tools = request.data.get("selected_tools")
        if selected_tools is not None:
            config.selected_tools = selected_tools
        selected_boards = request.data.get("selected_boards")
        if selected_boards is not None:
            config.selected_boards = selected_boards
        integration_tools = request.data.get("integration_tools", [])
        integrations = request.data.get("integrations", [])
        hashes = []
        # Extract hashes from integrations if present
        for integration_data in integrations:
            feature_hashes = [f.get("hash") for f in integration_data.get("features", []) if f.get("hash")]
            hashes.extend(feature_hashes)
        # Use hashes from integrations if available, else fallback to integration_tools list
        if hashes:
            config.integration_tools = hashes
        elif integration_tools is not None:
            config.integration_tools = integration_tools
        # Save integrations and features (activate/deactivate features)
        for integration_data in integrations:
            feature_hashes = [f.get("hash") for f in integration_data.get("features", []) if f.get("hash")]
            logger.info(f"the hash for a feature {feature_hashes}")
            if not feature_hashes:
                continue
            first_feature_hash = feature_hashes[0]
            feature = IntegrationFeature.objects.select_related('integration').filter(
                hash=first_feature_hash,
                integration__user=request.user
            ).first()
            logger.info(f"feature for integration: {feature}")
            if not feature:
                continue
            integration = feature.integration
            IntegrationFeature.objects.filter(integration=integration).update(is_active=False)
            IntegrationFeature.objects.filter(integration=integration, hash__in=feature_hashes).update(is_active=True)

        if serializer.is_valid():
            organisation_description = request.data.get("organisationDescription")
            # Set organisation_description if provided
            if organisation_description is not None:
                config.organisation_description = organisation_description
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class AssistantConfigSoftDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uuid):
        config = get_object_or_404(
            AssistantConfiguration,
            assistant_uuid=uuid,
            user=request.user,
            is_deleted=False
        )

        config.is_deleted = True
        config.save()
        return Response({'success': True})


class AssistantConfigDuplicateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uuid):
        try:
            original_config = AssistantConfiguration.objects.get(
                assistant_uuid=uuid,
                user=request.user,
                is_deleted=False
            )
            original_config.pk = None
            original_config.id = None

            original_config.assistant_name = f"{original_config.assistant_name} (Copy)"
            original_config.assistant_uuid = uuid4()
            original_config.save()

            duplicate_config = original_config

            serializer = AssistantConfigurationSerializer(duplicate_config)
            return Response({
                'success': True,
                'message': 'Assistant configuration duplicated successfully.',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        except AssistantConfiguration.DoesNotExist:
            return Response({'success': False, 'message': 'Assistant configuration not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error duplicating assistant config: {str(e)}")
            return Response({'success': False, 'message': 'Failed to duplicate configuration.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AssistantConfigExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, uuid):
        try:
            config = AssistantConfiguration.objects.get(
                assistant_uuid=uuid,
                user=request.user,
                is_deleted=False
            )
            serializer = AssistantConfigurationSerializer(config)
            export_data = {
                'export_metadata': {
                    'export_date': timezone.now().isoformat(),
                    'exported_by': request.user.email,
                },
                'configuration': serializer.data
            }
            response = JsonResponse(export_data, json_dumps_params={'indent': 2})
            response['Content-Disposition'] = f'attachment; filename="assistant_{config.name}_export.json"'
            return response
        except AssistantConfiguration.DoesNotExist:
            return Response({'success': False, 'message': 'Assistant configuration not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error exporting assistant config: {str(e)}")
            return Response({'success': False, 'message': 'Failed to export configuration.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AssistantConfigArchiveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uuid):
        try:
            config = AssistantConfiguration.objects.get(
                assistant_uuid=uuid,
                user=request.user
            )
            action = request.data.get('action')

            if action == 'archive':
                config.archived_at = timezone.now()
                message = 'Assistant configuration archived.'
            elif action == 'unarchive':
                config.archived_at = None
                message = 'Assistant configuration restored.'
            else:
                return Response({'success': False, 'message': 'Invalid action provided.'}, status=status.HTTP_400_BAD_REQUEST)
            config.save()

            serializer = AssistantConfigurationSerializer(config)
            return Response({
                'success': True,
                'message': message,
                'data': serializer.data
            })
        except AssistantConfiguration.DoesNotExist:
            return Response({'success': False, 'message': 'Assistant configuration not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error archiving assistant config: {str(e)}")
            return Response({'success': False, 'message': 'Failed to archive configuration.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SaveConfigurationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        model_uuid = data.get("model_uuid")
        agent_name = data.get("agent_name")
        organisation_name = data.get("organisation_name")
        organisation_description = data.get("organisation_description")
        examples = data.get("examples")
        goal = data.get("goal")
        selected_tools = data.get("selected_tools")
        integration_tools = data.get("integration_tools")
        selected_boards = data.get("selected_boards")
        if not model_uuid:
            model_uuid = str(uuid.uuid4())
        config, _ = AssistantConfiguration.objects.get_or_create(user=request.user, assistant_uuid=model_uuid)
        # Set agent_name if provided
        if agent_name is not None:
            config.agent_name = agent_name
        # Set organisation_name if provided
        if organisation_name is not None:
            config.organisation_name = organisation_name
        # Set organisation_description if provided
        if organisation_description is not None:
            config.organisation_description = organisation_description
        # Set examples if provided
        if examples is not None:
            config.examples = examples
        # Set goal if provided
        if goal is not None:
            config.goal = goal
        # Set selected_tools if provided
        if selected_tools is not None:
            config.selected_tools = selected_tools
        if selected_boards is not None:
            config.selected_boards = selected_boards
        if isinstance(integration_tools, list) and integration_tools:
            for integration in integration_tools:
                if "features" not in integration or "integration_name" not in integration:
                    return JsonResponse({"error": "Each integration must have 'hash' and 'features'"}, status=400)
                for feature in integration["features"]:
                    if "hash" not in feature or "feature_name" not in integration:
                        return JsonResponse({"error": "Each feature in 'features' must have a 'hash'"}, status=400)
            config.integration_tools = integration_tools
        use_last_user_language = data.get("use_last_user_language")
        languages = data.get("languages")
        config.use_last_user_language = use_last_user_language
        config.languages = languages
        enable_emojis = data.get("enable_emojis")
        if enable_emojis is not None:
            config.enable_emojis = bool(enable_emojis)
        answer_competitor_queries = data.get("answer_competitor_queries")
        if answer_competitor_queries is not None:
            config.answer_competitor_queries = bool(answer_competitor_queries)
        competitor_response_bias = data.get("competitor_response_bias")
        if competitor_response_bias in ("genuine", "biased"):
            config.competitor_response_bias = competitor_response_bias
        config.save()
        serializer = AssistantConfigurationSerializer(config, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(
                {
                    "message": "Configuration saved successfully!",
                    "model_uuid": str(config.assistant_uuid),
                    "integration_tools": config.integration_tools
                }
            )
        else:
            return JsonResponse(serializer.errors, status=400)


class WhatsAppChatView(APIView):
    permission_classes = [IsAuthenticated]

    def stream_openai_response(self, completion, json_mode=False):
        buffer = ""
        for chunk in completion:
            content = getattr(chunk.choices[0].delta, "content", None)
            if content:
                buffer += content
                if not json_mode:
                    while " " in buffer:
                        word, buffer = buffer.split(" ", 1)
                        yield f"{word} ".encode()
                        time.sleep(0.08)
        if buffer:
            if json_mode:
                yield (json.dumps({"message": buffer.strip()}) + "\n").encode()
            else:
                yield buffer.encode()

    def process_tool_calls(self, tool_calls, messages):
        """Process tool calls and return results"""
        tool_call_results = []
        user = None
        logger.debug(f"process_tool_calls called with {len(tool_calls)} tool_calls")
        # try request.user if available
        if hasattr(self, 'request') and hasattr(self.request, 'user'):
            user = getattr(self.request, 'user', None)
            logger.debug(f"process_tool_calls: user from request: {user}")

        for tool_call in tool_calls:
            logger.debug(f"Processing tool_call: {tool_call}")
            if hasattr(tool_call, 'id'):
                tool_call_id = tool_call.id
                tool_name = tool_call.function.name
                tool_args_str = tool_call.function.arguments or ""
            else:
                tool_call_id = tool_call.get("id", "unknown_id")
                tool_name = tool_call.get("name", "unknown_name")
                tool_args_str = tool_call.get("arguments", "")
            logger.debug(f"tool_call_id={tool_call_id}, tool_name={tool_name}, tool_args_str={tool_args_str}")

            # Check if this is a user tool
            if user:
                user_tools = UserTool.objects.filter(user=user, name=tool_name)
                logger.info(f"the user tools for process user tools : {user_tools}")
                try:
                    user_tool = user_tools.first()
                except Exception as e:
                    logger.exception(f"[Tool Call] Failed to retrieve user tool '{tool_name}' for user '{user}': {e}")
                    user_tool = None

                if user_tool:
                    logger.debug(f"Executing user tool: {tool_name} for user: {user}")
                    try:
                        args = json.loads(tool_args_str)
                    except Exception as e:
                        logger.error(f"Error parsing arguments for user tool {tool_name}: {e}")
                        args = {}
                    result = execute_user_tool(tool_name, user, args)
                    logger.debug(f"User tool {tool_name} result: {result}")
                    tool_call_results.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps({"result": result})
                    })

                elif tool_name == "refine_query":
                    logger.debug(f"Processing refine_query tool call: {tool_call_id}")
                    try:
                        args = json.loads(tool_args_str)
                        query = args.get("query")
                        logger.debug(f"refine_query args: {args}")
                        if query:
                            refined_query = refine_query(query, messages)
                            logger.debug(f"refined_query result: {refined_query}")
                            tool_call_results.append({
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": json.dumps({"refined_query": refined_query})
                            })
                    except Exception as e:
                        logger.error(f"Error in refine_query tool call {tool_call_id}: {e}")
                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"error": str(e)})
                        })
                # ------------------  get relevant images tool is to be added-------------
                elif tool_name == "get_data_from_excel":
                    logger.debug(f"Processing get_data_from_excel tool call: {tool_call_id}")
                    try:
                        args = json.loads(tool_args_str)
                        file_id = args.get("file_id")
                        logger.debug(f"get_data_from_excel args: {args}")
                        if not file_id:
                            logger.error(f"get_data_from_excel missing file_id in args: {args}")
                            raise ValueError("file_id is required")
                        excel_data = get_data_from_excel(file_id)
                        logger.debug(f"get_data_from_excel result: {excel_data}")
                        if excel_data:
                            tool_call_results.append({
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": json.dumps(excel_data)
                            })
                        else:
                            logger.warning(f"No data found in Excel for file_id: {file_id}")
                            tool_call_results.append({
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": json.dumps({"error": "No data found in Excel."})
                            })
                    except Exception as e:
                        logger.error(f"Error in get_data_from_excel tool call {tool_call_id}: {e}")
                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"error": str(e)})
                        })

                elif tool_name == "order_tracking_with_order_id":
                    logger.debug(f"Processing order_tracking_with_order_id tool_call: {tool_call_id}")
                    try:
                        args = json.loads(tool_args_str)
                        order_number = args.get("order_id")
                        logger.debug(f"order_number: {order_number}")
                        shopify_config = Integrations.objects.filter(user=user, name='shopify', feature_name='order_tracking').first()
                        prefix = shopify_config.details.get("prefix") if shopify_config and shopify_config.details else None
                        suffix = shopify_config.details.get("suffix") if shopify_config and shopify_config.details else None
                        order_id = remove_prefix_and_suffix(order_number=order_number, prefix=prefix, suffix=suffix)
                        logger.debug(f"order_tracking_with_order_id args: {args}, order_id: {order_id}")

                        if not order_id:
                            logger.error(f"order_tracking_with_order_id missing order_id in args: {args}")
                            raise ValueError("order_id is required")

                        shopify = Integrations.objects.get(user=user, name='shopify', feature_name='order_tracking')
                        client_api_key = user.api_key
                        logger.info(f"client_api_key: {client_api_key}")
                        email = user.email if user else None
                        technology = get_integration_details(email, technology='shopify', api_key=client_api_key)

                        shopify_domain = technology.get('api_domain')
                        access_token = technology.get('access_token')
                        logger.debug(f"shopify_domain: {shopify_domain}, access_token: {access_token}")
                        shopify_id = get_order_id_by_name(order_number, shopify_domain, access_token)
                        logger.debug(f"shopify_id: {shopify_id}")
                        order_status = order_tracking_with_order_id(order_id=shopify_id, shopify_domain=shopify_domain, access_token=access_token)
                        logger.debug(f"order_tracking_with_order_id result : {order_status}")
                        if order_status:
                            tool_call_results.append({
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": json.dumps(order_status)
                            })
                            logger.info(f" Order status for order_id {order_id} processed successfully.")
                        else:
                            logger.warning(f"No order status found for order : {order_id}")
                            tool_call_results.append({
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": json.dumps({"error": "No order status found."})
                            })
                    except Exception as e:
                        logger.error(f"Error in order_tracking_with_order_id tool call {tool_call_id}: {e}")
                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"error": str(e)})
                        })

                elif tool_name == "get_shopify_orders":
                    logger.debug(f"Processing shopify_orders_with_customer_email tool_call: {tool_call_id}")
                    shopify_config = Integrations.objects.filter(user=user, name='shopify', feature_name='list_orders').first()
                    logger.info(f"shopify_config for list_orders : {shopify_config}")
                    email = user.email
                    logger.info(f"email: {email}")

                    if not email:
                        raise ValueError("User email is required.")

                    shopify = Integrations.objects.get(user=user, name='shopify', feature_name='list_orders')
                    if not shopify:
                        raise ValueError("Shopify integration not found.")

                    client_api_key = user.api_key
                    technology = get_integration_details(email=email, technology='shopify', api_key=client_api_key)

                    shopify_domain = technology.get("api_domain")
                    access_token = technology.get("access_token")

                    orders = get_shopify_orders(
                        shopify_api_domain=shopify_domain,
                        shopify_access_token=access_token,
                        email=email
                    )
                    logger.info(f"orders associated with email: {orders}")
                    if orders:
                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps(orders)
                        })
                    else:
                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"error": "No orders found."})
                        })

                elif tool_name == "return_processing":
                    logger.info("tool for return called")
                    logger.debug(f"Processing initiate_shopify_return tool_call: {tool_call_id}")

                    shopify_config = Integrations.objects.filter(user=user, name='shopify', feature_name='return_processing').first()

                    if not shopify_config:
                        raise ValueError("Shopify integration for return processing not found.")
                    args = json.loads(tool_args_str)
                    order_name = args.get("order_name")
                    return_reason = args.get("reason") or "OTHER"

                    if not order_name:
                        raise ValueError("Order name is required.")

                    client_api_key = user.api_key
                    email = user.email

                    shopify = Integrations.objects.get(user=user, name='shopify', feature_name='return_processing')
                    technology = get_integration_details(email=email, technology='shopify', api_key=client_api_key)
                    shopify_domain = technology.get("api_domain")
                    access_token = technology.get("access_token")

                    logger.info(f"Initiating return for order: {order_name} | reason: {return_reason}")

                    try:
                        # Step 1: Get Order GID
                        order_gid = get_order_id_by_name(order_name, shopify_domain, access_token, return_gid=True)
                        if not order_gid:
                            raise ValueError(f"Order not found for name {order_name}")

                        # Step 2: Get fulfillment line item(s)
                        fulfillment_line_items = get_fulfillment_line_items_by_order_id(order_gid, shopify_domain, access_token)
                        if not fulfillment_line_items:
                            raise ValueError(f"No fulfillment line items found for order {order_name}")

                        # We'll assume return is for the first fulfilled item
                        fulfillment_line_item = fulfillment_line_items[0]
                        fulfillment_line_item_id = fulfillment_line_item["fulfillmentLineItemId"]

                        # Step 3: Call return processing
                        return_response = return_processing(
                            shop_domain=shopify_domain,
                            access_token=access_token,
                            order_id=order_gid,
                            fulfillment_line_item_id=fulfillment_line_item_id,
                            quantity=1,
                            return_reason=return_reason,
                            notify_customer=True,
                            restock=True
                        )

                        logger.info(f"Return processed successfully: {return_response}")
                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"success": True, "return": return_response})
                        })

                    except Exception as e:
                        logger.exception("Error processing Shopify return")
                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"error": str(e)})
                        })

                elif tool_name == "get_product_recommendations":
                    logger.info("Processing product_recommendation tool call")
                    shopify_config = Integrations.objects.filter(user=user, name='shopify', feature_name='product_recommendation').first()

                    if not shopify_config:
                        raise ValueError("Shopify integration for return product recommendation not found.")
                    args = json.loads(tool_args_str)
                    query = args.get("query")
                    logger.debug(f"get_product_recommendations args: {args}, query: {query}")
                    email = user.email if user else None
                    logger.debug(f" customer_email: {email}")

                    shopify = Integrations.objects.filter(user=user, name='shopify', feature_name='product_recommendation')
                    # logger.info(f"shopify integrations {shopify}")
                    client_api_key = user.api_key
                    logger.info(f"client_api_key: {client_api_key}")
                    technology = get_integration_details(email, technology='shopify', api_key=client_api_key)

                    shopify_domain = technology.get('api_domain')
                    access_token = technology.get('access_token')

                    # Load products data — replace this with actual data fetch logic
                    products_data = fetch_all_products(shopify_domain=shopify_domain, access_token=access_token)
                    logger.debug(f"Fetched products data: {len(products_data)}, type: {type(products_data)}")
                    if not products_data:
                        raise ValueError("No product data available")
                    # history = user_history[-10] if user_history else ""
                    # logger.debug(f"User history for product recommendation: {history}")
                    recommendations = get_product_recommendation(products=products_data, query=query)
                    logger.debug(f"Product recommendations: {recommendations}")
                    if recommendations:
                        logger.info(f"Product recommendations found: {len(recommendations)}")
                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"recommendations": recommendations})
                        })
                    else:
                        logger.error(f"Error in product_recommendation tool call {tool_call_id}: No recommendations found.")
                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"error": "No recommendations found."})
                        })

            else:
                logger.warning(f"Unhandled tool call: id={tool_call_id}, name={tool_name}")
                tool_call_results.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps({"error": f"Tool '{tool_name}' not implemented."})
                })

            logger.debug(f"process_tool_calls returning {len(tool_call_results)} results")
            return tool_call_results

    def make_openai_request(self, messages, config, system_prompt):
        """Make OpenAI API request"""
        stream_flag = bool(config.stream_responses)
        json_mode = bool(config.json_mode)
        tools = get_agent_tools_for_user(self.request.user, agent_uuid=config.assistant_uuid)
        logger.debug(f"make_openai_request | the tools called by openai are: {tools}")

        logger.debug(f"OpenAI API call params: model={config.model_name}, stream={stream_flag}, json_mode={json_mode}")

        completion = client.chat.completions.create(
            model=config.model_name,
            messages=[{
                "role": "system",
                "content": system_prompt
            }] + messages,
            temperature=config.temperature,
            top_p=config.top_p,
            frequency_penalty=config.frequency_penalty,
            max_tokens=config.max_tokens,
            stream=stream_flag,
            tools=tools,
            tool_choice="auto"
        )

        return completion, stream_flag, json_mode

    @method_decorator(csrf_exempt)
    def post(self, request):
        messages = request.data.get("messages", [])
        logger.debug(f"here are messages from FE {messages}")
        model_uuid = request.data.get("model_uuid")
        user = request.user

        logger.info(f"WhatsAppChatView: user={user}, model_uuid={model_uuid}")

        if not model_uuid:
            logger.error("No model_uuid provided in request.")
            return Response({
                "error": "model_uuid is required"
            }, status=400)

        config = AssistantConfiguration.objects.filter(
            user=user,
            assistant_uuid=model_uuid
        ).order_by("-updated_at").first()

        if not config:
            config = AssistantConfiguration.objects.create(user=user, assistant_uuid=model_uuid)
            logger.info(f"Created new AssistantConfiguration for user={user} and model_uuid={model_uuid}")

        logger.info(f"WhatsAppChatView: config found={bool(config)}")

        # RAG context retrieval
        rag_context = ""
        if config.knowledge_base:
            try:
                kb = KnowledgeBase.objects.get(uuid=config.knowledge_base.uuid)
                logger.info(f"WhatsAppChatView: KnowledgeBase found with uuid={kb.uuid}")
                retrieval_method = kb.retrieval_method or 'dense'
                pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
                index = pc.Index(os.getenv("PINECONE_INDEX"))
                user_query = messages[-1]["content"] if messages else ""
                result = retrieve(user_query, str(config.knowledge_base.uuid), index, k=2, retrieval_method=retrieval_method)
                if result and "matches" in result:
                    contexts = [match["metadata"].get("context", "") for match in result["matches"]]
                    rag_context = "\n".join(contexts)
            except Exception as e:
                logger.error(f"RAG retrieval failed: {e}")
                rag_context = ""

        system_prompt = build_final_prompt(config)
        # Prepend RAG context if available
        if rag_context:
            system_prompt = f"""
            Knowledge Base Context of website:\n{rag_context}\n---\n here is the SYSTEM_PORMPT:
            """ + system_prompt

        iteration = 1

        completion, stream_flag, json_mode = self.make_openai_request(messages, config, system_prompt)

        logger.debug(f"About to process OpenAI response with stream_flag={stream_flag}")

        if stream_flag:  # STREAMING MODE
            def token_stream():
                nonlocal messages, iteration

                while True:
                    logger.debug(f"Streaming iteration {iteration}: Making OpenAI API call")

                    # Make fresh API call for each iteration
                    completion, _, _ = self.make_openai_request(messages, config, system_prompt)

                    current_tool_calls = {}
                    finish_reason = None

                    for chunk in completion:
                        if not chunk.choices:
                            logger.warning("Received chunk with no choices.")
                            continue

                        delta = chunk.choices[0].delta
                        finish_reason = chunk.choices[0].finish_reason
                        logger.debug(f"WhtsappChatView | delta with Finish Reason: {finish_reason}")

                        # Handle tool calls in streaming
                        if delta.tool_calls:
                            logger.info("Processing tool call chunks.")
                            for tool_call_chunk in delta.tool_calls:
                                index = tool_call_chunk.index
                                tc_name = tool_call_chunk.function.name if tool_call_chunk.function else 'N/A'
                                logger.debug(f"Processing tool call chunk {index}: id={tool_call_chunk.id}, name={tc_name}")

                                if index not in current_tool_calls:
                                    if tool_call_chunk.id and tool_call_chunk.function and tool_call_chunk.function.name:
                                        logger.debug(f"New tool: id={tool_call_chunk.id}, {tool_call_chunk.function.name}")
                                        current_tool_calls[index] = {
                                            "id": tool_call_chunk.id,
                                            "type": "function",
                                            "name": tool_call_chunk.function.name,
                                            "arguments": tool_call_chunk.function.arguments or ""
                                        }
                                    else:
                                        logger.warning(f"Tool call chunk index {index} missing id/func info.")
                                else:
                                    if tool_call_chunk.function and tool_call_chunk.function.arguments:
                                        tc_id = current_tool_calls[index]['id']
                                        logger.debug(
                                            f"""
                                            Appending args to tool id {tc_id}: {tool_call_chunk.function.arguments}
                                            """
                                        )
                                        current_tool_calls[index]["arguments"] += tool_call_chunk.function.arguments
                                    else:
                                        logger.debug(f"No new args in chunk for tool index {index}.")

                        # Handle tool calls completion
                        if finish_reason == "tool_calls":

                            # Add assistant message with tool calls
                            messages.append({
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": tc["id"],
                                        "type": tc.get("type", "function"),
                                        "function": {
                                            "name": tc["name"],
                                            "arguments": tc["arguments"]
                                        }
                                    }
                                    for tc in current_tool_calls.values()
                                ]
                            })

                            # Process tool calls
                            tool_call_results = self.process_tool_calls(tool_calls=list(current_tool_calls.values()), messages=messages)
                            messages.extend(tool_call_results)
                            logger.debug(f"Tool call results processed, updated messages: {len(messages)} total messages")

                            break  # Exit inner loop to restart with updated messages

                        elif finish_reason == "stop":
                            logger.info("Finish reason 'stop' detected. Completion finished.")
                            return  # Exit the generator completely

                        # Handle content streaming
                        elif delta.content is not None:
                            logger.debug(f"Yielding content token: {delta.content}")
                            # Stream token by token for immediate display
                            if not json_mode:
                                yield delta.content.encode()
                            else:
                                yield (json.dumps({"message": delta.content}) + "\n").encode()

                        elif finish_reason:
                            logger.warning(f"Unhandled finish reason encountered: {finish_reason}")

                    # Handle different finish reasons
                    if finish_reason == "tool_calls":
                        iteration += 1
                        continue  # Continue outer while loop with updated messages
                    else:
                        break  # Exit outer while loop

            return StreamingHttpResponse(token_stream(), content_type="application/json" if json_mode else "text/plain")

        else:
            logger.debug("Non-streaming mode, processing OpenAI response directly")
            while True:
                completion, _, _ = self.make_openai_request(messages, config, system_prompt)

                choice = completion.choices[0]
                message = choice.message
                if hasattr(message, "tool_calls") and message.tool_calls:
                    logger.info(f"Processing {len(message.tool_calls)} tool calls in non-streaming mode")

                    # Add assistant message with tool calls
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": getattr(tc, "type", "function"),
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in message.tool_calls
                        ]
                    })

                    # Process tool calls
                    tool_call_results = self.process_tool_calls(tool_calls=message.tool_calls, messages=messages)
                    logger.debug(f"Tool call results processed, updating messages with {len(tool_call_results)} results")
                    messages.extend(tool_call_results)
                    logger.debug(f"Final messages after tool call processing: {len(messages)} total messages")

                else:
                    # No tool calls, return the final response
                    logger.debug("no tool calls found in message, returning final response")
                    reply = message.content
                    if json_mode:
                        return Response({"message": reply.strip()}, content_type="application/json")
                    else:
                        return Response({"message": reply})


# --- Test Suite API ---
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_test_suite(request):
    """
    Fetch test suite for assistant_uuid and mode.
    """
    assistant_uuid = request.GET.get("assistant_uuid")
    mode = request.GET.get("mode")

    if not assistant_uuid or not mode:
        return Response({"error": "assistant_uuid and mode required"}, status=400)
    config = AssistantConfiguration.objects.filter(assistant_uuid=assistant_uuid).order_by("-updated_at").first()

    if not config:
        return Response({"error": "Assistant configuration not found"}, status=404)

    try:
        suite = TestSuite.objects.get(assistant_config=config, mode=mode)
        return Response(TestSuiteSerializer(suite).data)
    except TestSuite.DoesNotExist:
        return Response({"error": "Not found"}, status=404)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_test_suite(request):
    data = request.data
    assistant_uuid = data.get("assistant_uuid")
    mode = data.get("mode")
    use_ai = data.get("use_ai", False)
    if not assistant_uuid or not mode:
        return Response({"error": "assistant_uuid and mode required"}, status=400)
    config = AssistantConfiguration.objects.filter(assistant_uuid=assistant_uuid).order_by("-updated_at").first()
    if not config:
        return Response({"error": "Assistant configuration not found"}, status=404)
    suite = TestSuite.objects.filter(assistant_config=config, mode=mode).first()

    if not use_ai:
        if suite:
            return Response(TestSuiteSerializer(suite).data)
        else:
            return Response({"test_cases": []})

    if not suite:
        suite = TestSuite.objects.create(assistant_config=config, mode=mode)
    final_prompt = build_final_prompt(config)
    mode_counts = {"quick": 8, "normal": 32, "extensive": 52}
    count = mode_counts.get(mode, 8)
    mode_descriptions = {
        "quick": "Quick: Generate a small set (8) of basic and edge-case questions.",
        "normal": "Normal: Generate a detailed set (32) of questions covering a wide range of scenarios.",
        "extensive": "Extensive: Generate a comprehensive set (52) of questions, including rare and complex cases."
    }
    mode_description = mode_descriptions.get(mode, "")
    test_suite_prompt = GENERATE_TEST_SUITE_PROMPT
    context = {
        "mode_description": mode_description,
        "count": count,
        "final_prompt": final_prompt
    }

    prompt = Template(test_suite_prompt).render(**context).strip()
    try:
        completion = client.chat.completions.create(
            model=TEST_GENERATION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": prompt
                }
            ],
            max_tokens=2048,
            temperature=0.3,
        )
        content = completion.choices[0].message.content.strip()
        try:
            test_cases = json.loads(content)
            if not isinstance(test_cases, list):
                test_cases = []
        except Exception:
            test_cases = []
    except Exception as e:
        logger.error(f"OpenAI test suite generation failed: {e}")
        test_cases = []
    suite.test_cases = test_cases
    suite.save()
    return Response(TestSuiteSerializer(suite).data)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_test_suite(request):
    """
    edit/add/delete questions
    """
    data = request.data
    assistant_uuid = data.get("assistant_uuid")
    mode = data.get("mode")
    test_cases = data.get("test_cases")
    if not assistant_uuid or not mode or not isinstance(test_cases, list):
        return Response(
            {
                "error": "assistant_uuid, mode, and test_cases (list) required"
            },
            status=400
        )
    config = AssistantConfiguration.objects.filter(assistant_uuid=assistant_uuid).order_by("-updated_at").first()
    if not config:
        return Response(
            {
                "error": "Assistant configuration not found"
            },
            status=404
        )
    try:
        suite, created = TestSuite.objects.get_or_create(
            assistant_config=config,
            mode=mode
        )
        logger.debug(f"TestSuite created:: {created}")
        suite.test_cases = test_cases
        suite.save()
        return Response(TestSuiteSerializer(suite).data)
    except TestSuite.DoesNotExist:
        return Response({"error": "Not found"}, status=404)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_test_suite(request):
    """
    all questions for perticular mode
    """
    assistant_uuid = request.GET.get("assistant_uuid")
    mode = request.GET.get("mode")
    if not assistant_uuid or not mode:
        return Response(
            {
                "error": "assistant_uuid and mode required"
            },
            status=400
        )
    config = AssistantConfiguration.objects.filter(assistant_uuid=assistant_uuid).order_by("-updated_at").first()
    if not config:
        return Response(
            {
                "error": "Assistant configuration not found"
            },
            status=404
        )
    try:
        suite = TestSuite.objects.get(
            assistant_config=config,
            mode=mode
        )

        suite.delete()
        return Response({"success": True})
    except TestSuite.DoesNotExist:
        return Response({"error": "Not found"}, status=404)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_final_prompt(request):
    """Return the fully rendered final prompt for a given assistant UUID (with all context and few-shot examples)."""
    uuid = request.GET.get("assistant_uuid")
    user = request.user if hasattr(request, "user") and request.user.is_authenticated else None
    config = None
    if user:
        config = AssistantConfiguration.objects.filter(assistant_uuid=uuid, user=user).order_by("-updated_at").first()
    if not config:
        config = AssistantConfiguration.objects.filter(assistant_uuid=uuid).order_by("-updated_at").first()
    if not config:
        return Response({"error": "Assistant configuration not found"}, status=404)
    system_prompt = build_final_prompt(config)
    return Response({"final_prompt": system_prompt})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_test_suite(request):
    """
    Starts a test suite run. Accepts config, test_suite, model_uuid. Returns a run_id.
    """
    logger.debug("Starting test suite run")
    data = request.data
    logger.debug(f"start_test_suite called with data: {data}")
    config = data.get("config")
    test_suite = data.get("test_suite", [])
    model_uuid = data.get("model_uuid")
    run_id = str(uuid.uuid4())
    task_ids = []
    config = dict(config) if config else {}
    config["_final_prompt"] = build_final_prompt(config)
    for idx, t in enumerate(test_suite):
        task = run_test_task.delay(run_id, idx, config, t, model_uuid)
        task_ids.append(task.id)
    return Response({"test_run_id": run_id, "task_ids": task_ids})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def test_suite_results(request):
    """Get task_ids from frontend query params"""
    task_ids = request.query_params.getlist("task_ids[]")
    run_id = request.query_params.get("run_id")
    logger.debug(f"test_suite_results called with run_id={run_id} and task_ids={task_ids}")

    results = []
    for task_id in task_ids:
        res = AsyncResult(task_id)
        if res.ready():
            results.append(res.result)
        else:
            results.append(None)
    # Only finished if all results are non-None and the count matches
    finished = all(r is not None for r in results) and len(results) == len(task_ids)
    return Response({"results": results, "finished": finished})


class WebsiteLinkListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, assistant_id):
        logger.debug(f"WebsiteLinkListCreateView GET called for assistant_id={assistant_id}")
        links = WebsiteLink.objects.filter(assistant_config__assistant_uuid=assistant_id)
        logger.info(f"Found {links.count()} links for assistant_id={assistant_id}")
        serializer = WebsiteLinkSerializer(links, many=True)
        return Response(serializer.data)

    def post(self, request, assistant_id):
        logger.debug(f"WebsiteLinkListCreateView POST called for assistant_id={assistant_id}, data={request.data}")
        data = request.data.copy()
        try:
            assistant = AssistantConfiguration.objects.get(assistant_uuid=assistant_id)
        except AssistantConfiguration.DoesNotExist:
            logger.error(f"Assistant not found for uuid={assistant_id}")
            return Response({'error': 'Assistant not found'}, status=404)
        data['assistant_config'] = assistant.id
        serializer = WebsiteLinkSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Link created for assistant_id={assistant_id}: {serializer.data}")
            return Response(serializer.data, status=201)
        logger.error(f"Link creation failed: {serializer.errors}")
        return Response(serializer.errors, status=400)


class WebsiteLinkUpdateDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        logger.debug(f"WebsiteLinkUpdateDeleteView PUT called for pk={pk}, data={request.data}")
        link = get_object_or_404(WebsiteLink, pk=pk)
        serializer = WebsiteLinkSerializer(link, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Link updated for pk={pk}: {serializer.data}")
            return Response(serializer.data)
        logger.error(f"Link update failed for pk={pk}: {serializer.errors}")
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        logger.debug(f"WebsiteLinkUpdateDeleteView DELETE called for pk={pk}")
        link = get_object_or_404(WebsiteLink, pk=pk)
        link.delete()
        logger.info(f"Link deleted for pk={pk}")
        return Response(status=204)


class KnowledgeFileListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, assistant_id):
        files = KnowledgeFile.objects.filter(knowledge_base__uuid=assistant_id)
        serializer = KnowledgeFileSerializer(files, many=True)
        return Response(serializer.data)


class KnowledgeFileDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        file = get_object_or_404(KnowledgeFile, pk=pk)
        file.delete()
        return Response(status=204)


class KnowledgeExcelListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, assistant_id):
        files = KnowledgeExcel.objects.filter(knowledge_base__uuid=assistant_id)
        serializer = KnowledgeExcelSerializer(files, many=True)
        return Response(serializer.data)


class KnowledgeExcelDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        file = get_object_or_404(KnowledgeExcel, pk=pk)
        file.delete()
        return Response(status - 204)


class IndexDocumentsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        kb_uuid = request.data.get("kb_id")
        if not kb_uuid:
            return Response({"error": "kb_id is required"}, status=400)
        # Start background indexing task
        task = index_knowledge_base_task.delay(kb_uuid)
        return Response(
            {
                "status": "Indexing started in background",
                "task_id": task.id
            }
        )


class AssistantConfigRetrieveWithToolsView(APIView):
    def get(self, request, uuid):
        try:
            logger.debug(
                f"AssistantConfigRetrieveWithToolsView GET called with data: {request.data}"
            )

            user_email = request.data.get("user_email")
            if not user_email:
                return Response(
                    {"status": "error", "message": "user_email is required"},
                    status=400,
                )

            user = get_object_or_404(User, email=user_email)

            config = get_object_or_404(
                AssistantConfiguration,
                assistant_uuid=uuid,
                user=user,
                is_deleted=False,
            )
            serializer = AssistantConfigurationWithToolsSerializer(config)
            data = serializer.data
            data["agent_name"] = getattr(config, "agent_name", "Agent360")
            data["organisation_name"] = getattr(config, "organisation_name", None)
            data["selected_boards"] = getattr(config, "selected_boards", [])

            return Response(data)

        except Exception as e:
            logger.error(f"Error retrieving assistant config with tools: {e}")
            return Response(
                {
                    "message": "Failed to retrieve configuration",
                    "error": str(e),
                },
                status=400,
            )


class RunUserTool(APIView):
    def post(self, request):
        try:
            logger.info(f"RunUserTool called with data: {request.data}")

            tool_name = request.data.get("tool_name")
            arguments = request.data.get("arguments", {})
            user_email = request.data.get("user_email")

            if not tool_name or not user_email:
                return Response(
                    {
                        "status": "error",
                        "message": "tool_name and user_email are required",
                    },
                    status=400,
                )

            user = get_object_or_404(User, email=user_email)

            result = execute_user_tool(tool_name, user, arguments)

            return Response(
                {
                    "status": "Success",
                    "message": "Tool run successfully",
                    "data": result,
                }
            )

        except Exception as e:
            logger.error(f"Error occurred while running tool: {e}")
            return Response(
                {"status": "error", "message": str(e)},
                status=400,
            )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_task_status(request, task_id):
    """Get the status of a Celery task by its ID.
    Args:
        request (): _http request object containing the task_id in GET parameters.
        task_id (str): ID of the Celery task to check.
    Returns:
        Response: Response object containing the task status and result if available.
    """
    result = AsyncResult(task_id)
    status = result.status
    response = {"task_id": task_id, "status": status}
    if status == "SUCCESS":
        response["result"] = result.result
    elif status == "FAILURE":
        response["error"] = str(result.result)
    return Response(response)

class ExportAllRoomsExcelView(APIView):
    """
    API: Generate Excel for ALL ChatRooms and return S3 URL.
    """
    permission_classes = [IsAuthenticated]  

    def get(self, request, *args, **kwargs):
        try:
            result = export_all_rooms_data_to_excel()
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in ExportAllRoomsExcelView: {e}", exc_info=True)
            return Response(
                {"status": "error", "message": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )