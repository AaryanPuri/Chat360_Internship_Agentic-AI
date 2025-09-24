from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import UserTool
from .serializers import UserToolSerializer
from django.shortcuts import get_object_or_404
import requests
from backend.settings import logger
import ast
import time


class UserToolListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tools = UserTool.objects.filter(user=request.user).order_by('-created_at')
        serializer = UserToolSerializer(tools, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = request.data.copy()
        # Convert stringified JSON fields to dict if needed
        json_fields = [
            'headers', 'auth_credentials', 'body_schema', 'query_parameters_json'
        ]
        for field in json_fields:
            if field in data and isinstance(data[field], str):
                import json
                try:
                    data[field] = json.loads(data[field])
                except Exception:
                    pass
        serializer = UserToolSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class UserToolDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        tool = get_object_or_404(UserTool, pk=pk, user=request.user)
        serializer = UserToolSerializer(tool)
        return Response(serializer.data)

    def put(self, request, pk):
        tool = get_object_or_404(UserTool, pk=pk, user=request.user)
        data = request.data.copy()
        # Convert stringified JSON fields to dict if needed
        json_fields = [
            'headers', 'auth_credentials', 'body_schema', 'query_parameters_json'
        ]
        for field in json_fields:
            if field in data and isinstance(data[field], str):
                import json
                try:
                    data[field] = json.loads(data[field])
                except Exception:
                    pass
        serializer = UserToolSerializer(tool, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        tool = get_object_or_404(UserTool, pk=pk, user=request.user)
        tool.delete()
        return Response(status=204)


class UserToolExecuteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        tool = get_object_or_404(UserTool, pk=pk, user=request.user)
        input_data = request.data.get('input', {})
        headers = tool.headers or {}
        if tool.auth_required:
            if tool.auth_type and tool.auth_credentials:
                if tool.auth_type.lower() == 'bearer':
                    headers['Authorization'] = f"Bearer {tool.auth_credentials.get('token', '')}"
                elif tool.auth_type.lower() == 'basic':
                    headers['Authorization'] = f"Basic {tool.auth_credentials.get('token', '')}"
                # Add more auth types as needed
        method = tool.http_method.upper()
        try:
            if method == 'GET':
                resp = requests.get(tool.endpoint_url, headers=headers, params=input_data, timeout=30)
            elif method == 'POST':
                if tool.send_body:
                    resp = requests.post(tool.endpoint_url, headers=headers, json=input_data, timeout=30)
                else:
                    resp = requests.post(tool.endpoint_url, headers=headers, data=input_data, timeout=30)
            elif method == 'PUT':
                resp = requests.put(tool.endpoint_url, headers=headers, json=input_data, timeout=30)
            elif method == 'DELETE':
                resp = requests.delete(tool.endpoint_url, headers=headers, json=input_data, timeout=30)
            else:
                return Response({'error': 'Unsupported HTTP method'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        try:
            response_data = resp.json()
            logger.info(f"UserTool {tool.name} executed successfully with response: {response_data}")
        except Exception:
            response_data = resp.text
            logger.error(f"UserTool {tool.name} failed to parse response as JSON: {response_data}")
        logger.info(f"UserTool {tool.name} executed with method {method} and response: {response_data}")

        # Optimize response if needed
        if tool.optimize_response:
            if tool.optimize_type == 'JSON':
                if tool.json_response_mode == 'fixed' and tool.json_fixed_example:
                    return Response({'result': tool.json_fixed_example})
                elif tool.json_response_mode == 'expression' and tool.json_expression_key:
                    def get_nested_value(data, keys):
                        """Recursively get value from nested dict using list of keys."""
                        if not isinstance(keys, list):
                            keys = [keys]
                        val = data
                        result = {}
                        for key in keys:
                            if isinstance(val, dict) and key in val:
                                result[key] = val[key]
                                val = val[key]
                            else:
                                result[key] = None
                                val = None
                        return result

                    keys = tool.json_expression_key
                    if not isinstance(keys, list):
                        keys = [keys]
                    value = get_nested_value(response_data, keys) if isinstance(response_data, dict) else None
                    logger.info(f"Extracted value from response using expression key {keys}: {value}")
                    return Response({'result': value})
            # HTML and Text optimization to be handled later as per your instructions
        logger.info(f"finally UserTool {tool.name} executed with response: {response_data}")
        return Response({'result': response_data})


def user_tool_to_openai_tool(tool: UserTool):
    """Convert a UserTool instance to an OpenAI-compatible tool dict."""
    logger.info(f"Converting UserTool '{tool.name}' (id={tool.id}) to OpenAI tool format")

    tool_name = tool.name.replace(" ", "_").lower()
    logger.debug(f"Normalized tool name: {tool_name}")

    function_dict = {
        "name": tool_name,
        "description": tool.description,
    }
    logger.debug(f"Function dict initialized: {function_dict}")

    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False
    }

    if tool.body_schema and isinstance(tool.body_schema, dict) and tool.body_schema:
        logger.info(f"Tool '{tool.name}' has a body_schema: {tool.body_schema}")
        # Check if it's already in JSON Schema format (has 'properties' key)
        if "properties" in tool.body_schema:
            logger.debug("body_schema appears to be in JSON Schema format")
            parameters = tool.body_schema.copy()
            parameters.setdefault("required", [])
            parameters.setdefault("additionalProperties", False)
            parameters.setdefault("type", "object")
            logger.debug(f"Parameters set from JSON Schema: {parameters}")
        else:
            logger.debug("body_schema is a simple key-value dict, converting to JSON Schema")
            properties = {}
            required_fields = []

            for key, value in tool.body_schema.items():
                logger.debug(f"Adding property '{key}' with description '{value}'")
                properties[key] = {
                    "type": "string",
                    "description": value if isinstance(value, str) else str(value)
                }
                required_fields.append(key)

            parameters = {
                "type": "object",
                "properties": properties,
                "required": required_fields,
                "additionalProperties": False
            }
            logger.debug(f"Parameters constructed from simple dict: {parameters}")

    elif hasattr(tool, 'query_parameters_json') and tool.query_parameters_json and isinstance(tool.query_parameters_json, dict):
        logger.info(f"Tool '{tool.name}' has query_parameters_json: {tool.query_parameters_json}")
        properties = {}
        required_fields = []

        for key, value in tool.query_parameters_json.items():
            logger.debug(f"Adding query parameter '{key}' with description '{value}'")
            properties[key] = {
                "type": "string",
                "description": value if isinstance(value, str) else f"Parameter: {key}"
            }
            required_fields.append(key)

        parameters = {
            "type": "object",
            "properties": properties,
            "required": required_fields,
            "additionalProperties": False
        }
        logger.debug(f"Parameters constructed from query_parameters_json: {parameters}")

    function_dict["parameters"] = parameters
    logger.info(f"Final OpenAI tool function dict for '{tool.name}': {function_dict}")

    result = {
        "type": "function",
        "function": function_dict
    }
    logger.info(f"Returning OpenAI tool dict for '{tool.name}': {result}")
    return result


def execute_user_tool(tool_name, user, arguments):
    """Find and execute a user tool by name for the given user and arguments dict, supporting all advanced features."""
    try:
        logger.info(f">>> Here called execute_user_tool with tool_name={tool_name}, user={user}, arguments={arguments}")

        # Find the tool
        tool = UserTool.objects.filter(user=user, name=tool_name).first()
        if not tool:
            logger.error(f"User tool '{tool_name}' not found for user {user}")
            return {"error": f"User tool '{tool_name}' not found."}

        logger.info(f"Found tool: {tool_name} with endpoint: {tool.endpoint_url}")

        # Prepare headers
        headers = tool.headers.copy() if tool.headers else {}
        logger.debug(f"Initial headers: {headers}")

        # Add custom headers from arguments if specified
        if hasattr(tool, 'specify_headers') and tool.specify_headers:
            try:
                custom_headers = arguments.get('headers') or {}
                headers.update(custom_headers)
                logger.debug(f"Added custom headers: {custom_headers}")
            except Exception as e:
                logger.warning(f"Failed to add custom headers: {e}")

        # Handle authentication
        if tool.auth_required:
            logger.debug(f"Authentication required. Auth type: {tool.auth_type}")
            if tool.auth_type and tool.auth_credentials:
                if tool.auth_type.lower() == 'bearer':
                    headers['Authorization'] = f"Bearer {tool.auth_credentials.get('token', '')}"
                    logger.debug("Added Bearer token authentication")
                elif tool.auth_type.lower() == 'basic':
                    headers['Authorization'] = f"Basic {tool.auth_credentials.get('token', '')}"
                    logger.debug("Added Basic authentication")
            else:
                logger.warning("Authentication required but no credentials found")

        method = tool.http_method.upper()
        url = tool.endpoint_url
        logger.info(f"Preparing {method} request to {url}")

        # Handle query parameters with proper mapping from arguments
        params = None
        if hasattr(tool, 'query_parameters_json') and tool.query_parameters_json:
            params = {}
            for key in tool.query_parameters_json.keys():
                logger.debug(f"Processing query parameter '{key}'")
                if key in arguments:
                    # Use the actual argument value
                    params[key] = arguments[key]
                    logger.debug(f"Mapped argument '{key}': '{arguments[key]}'")
                else:
                    # Use default value from tool definition
                    params[key] = tool.query_parameters_json[key]
                    logger.debug(f"Using default for '{key}': '{tool.query_parameters_json[key]}'")
            logger.debug(f"Using mapped query parameters: {params}")
        elif 'query' in arguments:
            params = arguments['query']
            logger.debug(f"Using explicit query parameters: {params}")
        elif method == 'GET':
            params = arguments
            logger.debug(f"Using all arguments as query parameters: {params}")

        # Body
        body = arguments.get('body') if 'body' in arguments else arguments
        if hasattr(tool, 'body_schema') and tool.body_schema:
            body = arguments
            logger.debug(f"Using body schema, body: {body}")

        def parse_nested_strings(obj):
            """Recursively parse string representations of dictionaries/lists"""
            import json
            if isinstance(obj, dict):
                result = {}
                for key, value in obj.items():
                    result[key] = parse_nested_strings(value)
                return result
            elif isinstance(obj, list):
                return [parse_nested_strings(item) for item in obj]
            elif isinstance(obj, str):
                if obj.strip().startswith(('{', '[')):
                    try:
                        return json.loads(obj)
                    except json.JSONDecodeError:
                        try:
                            return ast.literal_eval(obj)
                        except (ValueError, SyntaxError):
                            return obj
                return obj
            else:
                return obj

        body = parse_nested_strings(body)
        logger.debug(f"Processed body after string parsing: {body}")

        if hasattr(tool, 'body_content_type') and tool.body_content_type:
            content_type = tool.body_content_type.strip()

            # Map common values to proper MIME types
            content_type_mapping = {
                'JSON': 'application/json',
                'json': 'application/json',
                'XML': 'application/xml',
                'xml': 'application/xml',
                'FORM': 'application/x-www-form-urlencoded',
                'form': 'application/x-www-form-urlencoded',
                'TEXT': 'text/plain',
                'text': 'text/plain'
            }

            final_content_type = content_type_mapping.get(content_type, content_type)
            headers['Content-Type'] = final_content_type
            logger.debug(f"Set Content-Type to: {final_content_type} (mapped from: {content_type})")

        # Retry logic setup
        max_tries = tool.max_tries if hasattr(tool, 'max_tries') and tool.max_tries else 1
        wait_between_tries = tool.wait_between_tries if hasattr(tool, 'wait_between_tries') and tool.wait_between_tries else 0
        logger.info(f"Retry configuration: max_tries={max_tries}, wait_between_tries={wait_between_tries}")

        tries = 0
        last_error = None

        while tries < max_tries:
            tries += 1
            logger.info(f"Attempt {tries}/{max_tries}")

            try:
                # Make HTTP request based on method
                if method == 'GET':
                    logger.debug(f"Making GET request with params: {params}")
                    resp = requests.get(url, headers=headers, params=params, timeout=30)
                elif method == 'POST':
                    if tool.send_body:
                        if headers.get('Content-Type') == 'application/x-www-form-urlencoded':
                            logger.debug(f"Making POST request with form data headers are {headers} and body is {body}")

                            resp = requests.post(url, headers=headers, data=body, timeout=30)
                        else:
                            logger.debug(f"Making POST request with JSON body {body} headers are {headers}")

                            resp = requests.post(url, headers=headers, json=body, timeout=30)
                    else:
                        logger.debug("Making POST request with data (no JSON)")
                        resp = requests.post(url, headers=headers, data=body, timeout=30)

                elif method == 'PUT':
                    logger.debug("Making PUT request with JSON body")
                    resp = requests.put(url, headers=headers, json=body, timeout=30)

                elif method == 'DELETE':
                    logger.debug("Making DELETE request with JSON body")
                    resp = requests.delete(url, headers=headers, json=body, timeout=30)
                else:
                    logger.error(f"Unsupported HTTP method: {method}")
                    return {"error": "Unsupported HTTP method"}

                logger.info(f"HTTP request completed. Status code: {resp.status_code}")
                logger.debug(f"Response headers: {dict(resp.headers)}")

                # Check if request was successful
                if resp.status_code >= 400:
                    logger.warning(f"HTTP request returned error status: {resp.status_code}")
                    # Still try to parse the response for error details

                # Parse response
                try:
                    response_data = resp.json()
                    logger.debug("Successfully parsed JSON response")
                except Exception as parse_error:
                    response_data = resp.text
                    logger.debug(f"Failed to parse JSON, using text response: {parse_error}")

                logger.debug(f"Response data length: {len(str(response_data))}")

                # Truncate response if needed
                if getattr(tool, 'should_truncate_response', False) and hasattr(tool, 'truncate_limit') and tool.truncate_limit:
                    logger.info(f"Truncating response to {tool.truncate_limit} characters")
                    if isinstance(response_data, str):
                        response_data = response_data[:tool.truncate_limit]
                    elif isinstance(response_data, dict):
                        import json
                        response_str = json.dumps(response_data)
                        response_data = response_str[:tool.truncate_limit]

                # Optimize response
                if tool.optimize_response:
                    logger.info(f"Optimizing response with type: {tool.optimize_type}")
                    if tool.optimize_type == 'JSON':
                        if tool.json_response_mode == 'fixed' and tool.json_fixed_example:
                            logger.debug("Using fixed JSON response example")
                            return tool.json_fixed_example
                        elif tool.json_response_mode == 'expression' and tool.json_expression_key:
                            logger.debug(f"Extracting field: {tool.json_expression_key}")
                            if isinstance(response_data, dict):
                                extracted_data = response_data.get(tool.json_expression_key)
                                logger.debug(f"Extracted data: {extracted_data}")
                                return extracted_data
                            logger.warning("Cannot extract field from non-dict response")
                            return None
                    # Add HTML/TEXT optimization as needed

                # Only output data field if always_output_data is set
                if getattr(tool, 'always_output_data', False):
                    logger.debug(f"Extracting data field: {tool.field_containing_data}")
                    if isinstance(response_data, dict) and tool.field_containing_data:
                        extracted_data = response_data.get(tool.field_containing_data, response_data)
                        logger.debug("Successfully extracted data field")
                        return extracted_data

                # Include only specified fields if set
                if getattr(tool, 'include_fields', None):
                    fields = [f.strip() for f in tool.include_fields.split(',') if f.strip()]
                    logger.debug(f"Filtering response to include only fields: {fields}")
                    if isinstance(response_data, dict):
                        response_data = {k: v for k, v in response_data.items() if k in fields}
                        logger.debug(f"Filtered response contains {len(response_data)} fields")

                logger.info("Successfully processed tool execution")
                return response_data

            except Exception as e:
                last_error = str(e)
                logger.error(f"Request failed on attempt {tries}: {last_error}")

                if not getattr(tool, 'retry_on_fail', False):
                    logger.info("Retry on fail is disabled, breaking")
                    break

                if tries < max_tries:
                    logger.info(f"Waiting {wait_between_tries} seconds before retry")
                    time.sleep(wait_between_tries)
                else:
                    logger.error(f"All {max_tries} attempts exhausted")

        # Handle error cases
        if hasattr(tool, 'on_error') and tool.on_error:
            logger.info(f"Using custom error message: {tool.on_error}")
            return {"error": tool.on_error}

        logger.error(f"Returning final error: {last_error}")
        return {"error": last_error or "Unknown error"}

    except Exception as e:
        logger.error(f"Unexpected error in execute_user_tool: {str(e)}", exc_info=True)
        return {"error": str(e)}
