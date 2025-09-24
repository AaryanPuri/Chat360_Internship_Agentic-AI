import json
import os
from openai import OpenAI
from pinecone import Pinecone
from analytics.api import get_agent_tools_for_user
from analytics.functions import execute_user_tool
from analytics.indexing import retrieve
from analytics.integrations import get_integration_details
from analytics.tasks import (
    build_prompt_webhook,
    fetch_all_products,
    get_data_from_excel,
    get_fulfillment_line_items_by_order_id,
    get_order_id_by_name,
    get_product_recommendation,
    get_shopify_orders,
    order_tracking_with_order_id,
    refine_query,
    get_room_data,
    remove_prefix_and_suffix,
    return_processing,
    store_webhook_analytics
)
from backend.settings import logger
from analytics.models import (
    AssistantConfiguration,
    ChatRoom,
    CustomUser,
    Integrations,
    UserTool,
)
# from analytics.tools import IMAGES
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
# from django.core.cache import cache
from analytics.cache_management import (
    get_messages_from_cache,
    save_message_to_cache_and_db
)

from .models import Board
import time

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class WebhooksComponentView(APIView):
    """
    Handle the integration of bot flows with our agents, through webhooks
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # No authentication for webhooks

    def process_tool_calls(self, tool_calls, messages):
        """Process tool calls and return results"""
        tool_call_results = []
        user = None
        logger.debug(f"--------------------------------------------process_tool_calls called with {len(tool_calls)} tool_calls")
        # try request.user if available
        if hasattr(self, 'request') and hasattr(self.request, 'user') and self.request.user.is_authenticated:
            user = getattr(self.request, 'user', None)
            logger.debug(f"process_tool_calls: user from request: {user}")

        else:
            logger.debug("process_tool_calls: no authenticated user found in request")
        if self.request.data.get("email") and not user:
            email = self.request.data.get("email")
            logger.debug(f"process_tool_calls: user email from request: {email}")
            try:
                user = CustomUser.objects.get(email=email)
                logger.debug(f"process_tool_calls: user found by email: {user}")
            except CustomUser.DoesNotExist:
                logger.warning(f"process_tool_calls: no user found with email {email}")

        for tool_call in tool_calls:
            step_start = time.perf_counter()
            logger.debug(f"Processing tool_call: {tool_call}")
            if hasattr(tool_call, 'id'):
                tool_call_id = tool_call.id
                tool_name = tool_call.function.name
                tool_args_str = tool_call.function.arguments or ""
            else:
                tool_call_id = tool_call.get("id", "unknown_id")
                tool_name = tool_call.get("name", "unknown_name")
                tool_args_str = tool_call.get("arguments", "")
            logger.debug(f"--------------------------------------tool_name={tool_name}, tool_args_str={tool_args_str}")
            logger.debug(f"[timing] parsed_tool_metadata took {time.perf_counter() - step_start:0.6f}s")

            # Check if this is a user tool
            if user:
                sub_start = time.perf_counter()
                user_tools = UserTool.objects.filter(user=user, name=tool_name)
                logger.info(f"the user tools for process user tools : {user_tools}")
                try:
                    user_tool = user_tools.first()
                except Exception as e:
                    logger.exception(f"[Tool Call] Failed to retrieve user tool '{tool_name}' for user '{user}': {e}")
                    user_tool = None
                logger.debug(f"[timing] fetch_user_tool took {time.perf_counter() - sub_start:0.6f}s")

                if user_tool:
                    exec_start = time.perf_counter()
                    logger.debug(f"Executing user tool: {tool_name} for user: {user}")
                    try:
                        args = json.loads(tool_args_str)
                    except Exception as e:
                        logger.error(f"Error parsing arguments for user tool {tool_name}: {e}")
                        args = {}
                    parse_args_end = time.perf_counter()
                    result = execute_user_tool(tool_name, user, args)
                    execute_end = time.perf_counter()
                    logger.debug(f"User tool {tool_name} result: {result}")
                    tool_call_results.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps({"result": result})
                    })
                    logger.debug(f"[timing] user_tool.parse_args took {parse_args_end - exec_start:0.6f}s")
                    logger.debug(f"[timing] user_tool.execute took {execute_end - parse_args_end:0.6f}s")
                    logger.debug(f"[timing] user_tool.total took {time.perf_counter() - exec_start:0.6f}s")

                elif tool_name == "refine_query":
                    rq_start = time.perf_counter()
                    logger.debug(f"Processing refine_query tool call: {tool_call_id}")
                    try:
                        args = json.loads(tool_args_str)
                        query = args.get("query")
                        logger.debug(f"refine_query args: {args}")
                        if query:
                            refine_start = time.perf_counter()
                            refined_query = refine_query(query, messages)
                            refine_end = time.perf_counter()
                            logger.debug(f"refined_query result: {refined_query}")
                            tool_call_results.append({
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": json.dumps({"refined_query": refined_query})
                            })
                            logger.debug(f"[timing] refine_query.call took {refine_end - refine_start:0.6f}s")
                    except Exception as e:
                        logger.error(f"Error in refine_query tool call {tool_call_id}: {e}")
                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"error": str(e)})
                        })
                    finally:
                        logger.debug(f"[timing] refine_query.total took {time.perf_counter() - rq_start:0.6f}s")
                elif tool_name == "get_relevant_images":
                    gri_start = time.perf_counter()
                    logger.debug(f"Processing get_relevant_images tool call: {tool_call_id}")
                    try:
                        args = json.loads(tool_args_str)
                        query = args.get("context", "")
                        board_id = args.get("board_id")
                        max_results = int(args.get("max_results", 5))

                        board_lookup_start = time.perf_counter()
                        if board_id:
                            board = Board.objects.filter(id=board_id, user=user).first()
                            logger.info(f"found board {board}")
                        else:
                            board = Board.objects.filter(user=user).first()
                            logger.info("found board without id")
                        board_lookup_end = time.perf_counter()

                        IMAGES = board.images if board and board.images else []
                        prompt = (
                            f"""Given the following context of conversation: '{query}', and the following images with metadata:{IMAGES} +
                            Return a JSON array of up to {max_results} image URLs that should be shown in the bot reply .
                            the response should be in the format:
                            {{
                                "number_of_images": <number_of_images>,
                                "image1": "<image_url_1>",
                                "image2": "<image_url_2>",
                                "image3": "<image_url_3>",
                                "image4": "<image_url_4>",
                                "image5": "<image_url_5>",
                            }}
                            """
                        )
                        openai_start = time.perf_counter()
                        completion = client.chat.completions.create(
                            model="gpt-4.1",
                            messages=[
                                {"role": "system", "content": "You are an assistant that selects relevant images."},
                                {"role": "user", "content": prompt}],
                            temperature=0,
                        )
                        openai_end = time.perf_counter()

                        content = completion.choices[0].message.content

                        logger.debug("get_relevant_images completed")
                        parse_start = time.perf_counter()
                        try:
                            selected_images = json.loads(content)
                        except Exception:
                            logger.info(f"WebhookComponent: no url selected--- {content}")
                            selected_images = []
                        parse_end = time.perf_counter()

                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps(selected_images)
                        })
                        logger.debug(f"[timing] get_relevant_images.board_lookup took {board_lookup_end - board_lookup_start:0.6f}s")
                        logger.debug(f"[timing] get_relevant_images.openai_call took {openai_end - openai_start:0.6f}s")
                        logger.debug(f"[timing] get_relevant_images.parse_output took {parse_end - parse_start:0.6f}s")
                    except Exception as e:
                        logger.error(f"Error in get_relevant_images tool call {tool_call_id}: {e}")
                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"error": str(e)})
                        })
                    finally:
                        logger.debug(f"[timing] get_relevant_images.total took {time.perf_counter() - gri_start:0.6f}s")

                elif tool_name == "get_data_from_excel":
                    gde_start = time.perf_counter()
                    logger.debug(f"Processing get_data_from_excel tool call: {tool_call_id}")
                    try:
                        args = json.loads(tool_args_str)
                        file_id = args.get("file_id")
                        logger.debug(f"get_data_from_excel args: {args}")
                        if not file_id:
                            logger.error("get_data_from_excel missing file_id")
                            raise ValueError("file_id is required")
                        fetch_start = time.perf_counter()
                        excel_data = get_data_from_excel(file_id)
                        fetch_end = time.perf_counter()
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
                        logger.debug(f"[timing] get_data_from_excel.fetch took {fetch_end - fetch_start:0.6f}s")
                    except Exception as e:
                        logger.error(f"Error in get_data_from_excel tool call {tool_call_id}: {e}")
                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"error": str(e)})
                        })
                    finally:
                        logger.debug(f"[timing] get_data_from_excel.total took {time.perf_counter() - gde_start:0.6f}s")
                elif tool_name == "capture_user_data":
                    cud_start = time.perf_counter()
                    logger.debug(f"Processing capture_user_data tool call: {tool_call_id}")
                    try:
                        args = json.loads(tool_args_str)
                        data_to_capture = args.get("data_to_capture", "")
                        if not data_to_capture:
                            logger.error(f"capture_user_data missing data_to_capture in args: {args}")
                            data_to_capture = args
                        # Logic to capture user data and store in ChatRoom.captured_data
                        room_id = args.get("room_id") or args.get("session_id") or args.get("@room_id")
                        logger.debug(f"capture_user_data args: {args}, room_id: {room_id}")
                        if not room_id:
                            # Try to get from messages context if not in args
                            room_extraction_start = time.perf_counter()
                            room_id = None
                            logger.debug("Attempting to extract room_id from messages context")
                            for msg in messages:
                                if isinstance(msg, dict) and msg.get("role") == "user":
                                    room_id = msg.get("room_id")
                                    if room_id:
                                        break
                            room_extraction_end = time.perf_counter()
                            logger.debug(f"[timing] capture_user_data.extract_room_id took {room_extraction_end - room_extraction_start:0.6f}s")
                        if not room_id:
                            logger.error("room_id is required to capture user data")
                            raise ValueError("room_id is required to capture user data")
                        orm_start = time.perf_counter()
                        try:
                            chat_room = ChatRoom.objects.get(session_id=room_id)
                        except ChatRoom.DoesNotExist:
                            raise ValueError(f"ChatRoom with session_id {room_id} does not exist")
                        orm_end = time.perf_counter()
                        merge_start = time.perf_counter()
                        # Merge new data with existing captured_data
                        captured_data = chat_room.captured_data or {}
                        if isinstance(data_to_capture, dict):
                            captured_data.update(data_to_capture)
                        else:
                            # If data_to_capture is not a dict, store as a value
                            captured_data["data"] = data_to_capture
                        chat_room.captured_data = captured_data
                        save_start = time.perf_counter()
                        chat_room.save()
                        save_end = time.perf_counter()
                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"captured_data": captured_data})
                        })
                        logger.debug(f"[timing] capture_user_data.orm_get took {orm_end - orm_start:0.6f}s")
                        logger.debug(f"[timing] capture_user_data.merge_data took {save_start - merge_start:0.6f}s")
                        logger.debug(f"[timing] capture_user_data.orm_save took {save_end - save_start:0.6f}s")
                    except Exception as e:
                        logger.error(f"Error in capture_user_data tool call {tool_call_id}: {e}")
                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"error": str(e)})
                        })
                    finally:
                        logger.debug(f"[timing] capture_user_data.total took {time.perf_counter() - cud_start:0.6f}s")

                elif tool_name == "get_buttons":
                    gb_start = time.perf_counter()
                    logger.debug("webhook | Processing get_relevant_buttons")
                    try:
                        args = json.loads(tool_args_str)
                        query = args.get("context", "")
                        max_results = int(args.get("max_results", 10))
                        prompt = (
                            f"""Given the following context of conversation: '{query}', +
                            Return a JSON array of up to {max_results} buttons content that should be shown in the bot reply .
                            the response should be in the format:
                            {{
                                "number_of_buttons": <number_of_buttons>,
                                "button1": "<button_content_1>",
                                "button2": "<button_content_2>",
                                "button3": "<button_content_3>",
                                "button4": "<button_content_4>",
                                "button5": "<button_content_5>",
                            }}
                            here is an example:
                            """
                        )
                        openai_start = time.perf_counter()
                        completion = client.chat.completions.create(
                            model="gpt-4.1",
                            messages=[
                                {"role": "system", "content": "You are an assistant that selects relevant buttons."},
                                {"role": "user", "content": prompt}],
                            temperature=0,
                        )
                        openai_end = time.perf_counter()
                        content = completion.choices[0].message.content

                        logger.debug(f"get_buttons completion content: {content}")
                        parse_start = time.perf_counter()
                        try:
                            selected_images = json.loads(content)
                        except Exception:
                            logger.info(f"WebhookComponent: no url selected--- {content}")
                            selected_images = []
                        parse_end = time.perf_counter()

                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps(selected_images)
                        })
                        logger.debug(f"[timing] get_buttons.openai_call took {openai_end - openai_start:0.6f}s")
                        logger.debug(f"[timing] get_buttons.parse_output took {parse_end - parse_start:0.6f}s")
                    except Exception as e:
                        logger.error(f"Error in get_relevant_buttons tool call {tool_call_id}: {e}")
                        tool_call_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"error": str(e)})
                        })
                    finally:
                        logger.debug(f"[timing] get_buttons.total took {time.perf_counter() - gb_start:0.6f}s")

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
                        # logger.info(f"shopify integrations {shopify}")
                        client_api_key = user.api_key
                        logger.info(f"client_api_key: {client_api_key}")
                        email = user.email if user else None
                        # logger.debug(f"email for integration details: {email}")
                        technology = get_integration_details(email, technology='shopify', api_key=client_api_key)
                        # logger.debug(f"Technology details for Shopify: {technology}")

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
                    logger.info(f"shopify_config for get_shopify_orders : {shopify_config}")
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
                        raise ValueError("Shopify integration for product recommendation not found.")
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

            # ------------------  shopify integration tools are to be added tools are to be added-------------
            else:
                logger.warning(f"Unhandled tool call: id={tool_call_id}, name={tool_name}")
                tool_call_results.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps({"error": f"Tool '{tool_name}' not implemented."})
                })

            logger.debug(f"[timing] per_tool_call.total took {time.perf_counter() - step_start:0.6f}s")

        logger.debug(f"process_tool_calls returning {len(tool_call_results)} results")
        return tool_call_results

    def make_openai_request(self, messages, config, system_prompt):
        """Make OpenAI API request"""
        start_time = time.time()
        stream_flag = bool(config.stream_responses)
        json_mode = bool(config.json_mode)
        user = self.request.user if hasattr(self.request, "user") and self.request.user.is_authenticated else None
        if self.request.data.get("email") and not user:
            email = self.request.data.get("email")
            logger.debug(f"user email from request: {email}")
            try:
                user = CustomUser.objects.get(email=email)
                logger.debug(f" user found by email: {user}")
            except CustomUser.DoesNotExist:
                logger.warning(f"no user found with email {email}")
        tools = get_agent_tools_for_user(user, webhook=True, agent_uuid=config.assistant_uuid)

        logger.debug(f"OpenAI API call params: model={config.model_name}, stream={stream_flag}, json_mode={json_mode}")

        logger.info(f">>> Here images {messages}")
        
        api_call_start = time.time()
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
        api_call_time = time.time() - api_call_start
        logger.info(f"TIMING: OpenAI API call took {api_call_time:.3f} seconds")

        total_time = time.time() - start_time
        logger.info(f"TIMING: make_openai_request total time: {total_time:.3f} seconds")

        return completion, stream_flag, json_mode

    @method_decorator(csrf_exempt)
    def post(self, request):
        request_start_time = time.time()

        logger.info(f"Processing webhook request: with data:{request.data}")
        
        validation_start = time.time()
        if not request.data.get("agent_uuid"):
            logger.error("No agent_uuid provided in request.")
            return Response({
                "error": "agent_uuid is required"
            }, status=400)
        agent_uuid = request.data.get("agent_uuid")

        config = AssistantConfiguration.objects.filter(
            assistant_uuid=agent_uuid
        ).first()
        logger.info(f"webhookComponent: agent_uuid={request.data.get('agent_uuid')}")

        room_id = request.data.get("room_id")
        # bot_id = request.data.get("bot_id")
        if not room_id:
            logger.error("No room_id provided in request.")
            return Response({
                "error": "room_id is required"
            }, status=400)

        logger.info(f"WebhookComponent: room_id={room_id}")
        validation_time = time.time() - validation_start
        logger.info(f"TIMING: Initial validation took {validation_time:.3f} seconds")

        # Chat room setup
        chat_setup_start = time.time()
        message = request.data.get("query", [])
        chat = ChatRoom.objects.filter(session_id=room_id).first()
        if not chat:
            chat = ChatRoom.objects.create(session_id=room_id, agent=config)
            logger.debug(f"Created new ChatRoom with session_id={room_id} and agent_uuid={agent_uuid}")

        data_to_capture = config.data_to_capture
        room_data = get_room_data(room_id=room_id)

        logger.info(f"WebhookComponent: room_id={chat.session_id}")

        save_message_to_cache_and_db(room_id, "user", message, chat)

        logger.info(f"WebhookComponent: Received message: {message}")
        chat_setup_time = time.time() - chat_setup_start
        logger.info(f"TIMING: Chat room setup took {chat_setup_time:.3f} seconds")

        # Message retrieval
        message_retrieval_start = time.time()
        messages = get_messages_from_cache(room_id)

        logger.info(f">>>> messages: {messages}")

        if not config:
            logger.error(f"config not found for model_uuid={agent_uuid}")

        logger.info(f"WebhookComponent: config found={bool(config)}")
        message_retrieval_time = time.time() - message_retrieval_start
        logger.info(f"TIMING: Message retrieval took {message_retrieval_time:.3f} seconds")

        # RAG context retrieval
        rag_start_time = time.time()
        rag_context = ""
        if config.knowledge_base:
            try:
                pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
                index = pc.Index(os.getenv("PINECONE_INDEX"))
                user_query = messages[-1]["content"] if messages else ""
                if not request.data.get("retrieval_method"):
                    retrieval_method = 'dense'
                else:
                    retrieval_method = request.data.get("retrieval_method")
                result = retrieve(user_query, str(config.knowledge_base.uuid), index, k=2, retrieval_method=retrieval_method)
                if result and "matches" in result:
                    contexts = [match["metadata"].get("context", "") for match in result["matches"]]
                    rag_context = "\n".join(contexts)
            except Exception as e:
                logger.error(f"RAG retrieval failed: {e}")
                rag_context = ""
        rag_time = time.time() - rag_start_time
        logger.info(f"TIMING: RAG context retrieval took {rag_time:.3f} seconds")

        # System prompt building
        prompt_build_start = time.time()
        system_prompt = build_prompt_webhook(config)
        system_prompt = system_prompt + f"""
        here is the data you have to capture during the conversation {data_to_capture} where ever you get this data,
        capture it using capture_user_data tool
        this is the room_id: {room_id}, at some places it is mentioned as session_id, you can use it as session_id and whenever any tool requires(session_id or room_id) please provide room_id.
        here is the data already captured in the conversation: {room_data}
        """

        # Prepend RAG context if available
        if rag_context:
            system_prompt = f"""
            Knowledge Base Context of website:\n{rag_context}\n---\n here is the SYSTEM_PORMPT:
            """ + system_prompt

        logger.warning(f"WebhookComponent: system_prompt created with length {len(system_prompt)}")
        prompt_build_time = time.time() - prompt_build_start
        logger.info(f"TIMING: System prompt building took {prompt_build_time:.3f} seconds")

        # Main processing loop
        main_loop_start = time.time()
        completion, stream_flag, json_mode = self.make_openai_request(messages, config, system_prompt)

        logger.debug(f"About to process OpenAI response with stream_flag={stream_flag}")

        if stream_flag:  # STREAMING MODE
            return Response({"message": "streamin is not available for webhooks"}, status=501)
        else:
            iteration_count = 0
            while True:
                loop_iteration_start = time.time()
                iteration_count += 1
                completion, _, _ = self.make_openai_request(messages, config, system_prompt)
                choice = completion.choices[0]
                message = choice.message

                if hasattr(message, "tool_calls") and message.tool_calls:
                    tool_processing_start = time.time()
                    logger.info(f"Processing {len(message.tool_calls)} tool calls in webhook response")
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
                    tool_call_results = self.process_tool_calls(message.tool_calls, messages)

                    logger.info(f">>> Tool Call Result {tool_call_results}")

                    messages.extend(tool_call_results)

                    tool_save_start = time.time()
                    for tool_call in tool_call_results:
                        tool_call_content_str = tool_call.get("content", "")
                        logger.info(f"Tool call content: {tool_call_content_str[:500]}")  # Log first 500 chars
                        save_message_to_cache_and_db(
                            room_id=room_id,
                            role="tool",
                            message=tool_call_content_str[:500],
                            chat_room=chat,
                            tool_name=message.tool_calls[0].function.name
                        )
                    tool_save_time = time.time() - tool_save_start
                    logger.info(f"TIMING: Tool call saving took {tool_save_time:.3f} seconds")

                    tool_processing_time = time.time() - tool_processing_start
                    logger.info(f"TIMING: Tool processing took {tool_processing_time:.3f} seconds")

                    # After tool calls, make another OpenAI request for final reply
                    final_request_start = time.time()
                    completion, _, _ = self.make_openai_request(messages, config, system_prompt)
                    choice = completion.choices[0]
                    final_request_time = time.time() - final_request_start
                    logger.info(f"TIMING: Final OpenAI request after tool calls took {final_request_time:.3f} seconds")

                    reply = choice.message.content
                elif choice.finish_reason == "stop":
                    reply = message.content

                    logger.info(f"OpenAI response: {reply}")

                    response_save_start = time.time()
                    save_message_to_cache_and_db(room_id, "assistant", reply, chat)
                    response_save_time = time.time() - response_save_start
                    logger.info(f"TIMING: Response saving took {response_save_time:.3f} seconds")

                    # Parse reply as JSON, extract status, and return rest as response body
                    try:
                        parsed = json.loads(reply)
                        status_code = int(parsed.pop("status", 201))
                        
                        loop_iteration_time = time.time() - loop_iteration_start
                        logger.info(f"TIMING: Loop iteration #{iteration_count} took {loop_iteration_time:.3f} seconds")
                        
                        main_loop_time = time.time() - main_loop_start
                        logger.info(f"TIMING: Main processing loop took {main_loop_time:.3f} seconds")
                        
                        total_request_time = time.time() - request_start_time
                        logger.info(f"TIMING: Total request processing time: {total_request_time:.3f} seconds")

                        try:
                            analytics_account_email = self.request.data.get("analytics_account_email")
                            
                            if analytics_account_email:
                                logger.info(f"Queuing analytics for room_id: {room_id}")

                                store_webhook_analytics.delay(
                                    email=analytics_account_email,
                                    query=message,
                                    response_data=parsed.get("message"),
                                    namespace="agentic_knowledge_base",
                                    room_id=room_id
                                )
                                logger.info(f"Analytics queued for room_id: {room_id}")

                        except Exception as analytics_error:
                            logger.error(f"Failed to queue analytics: {analytics_error}")
                        
                        return Response(parsed, status=status_code)
                    except Exception as e:
                        logger.error(f"Failed to parse LLM reply as JSON: {e}")
                        
                        loop_iteration_time = time.time() - loop_iteration_start
                        logger.info(f"TIMING: Loop iteration #{iteration_count} took {loop_iteration_time:.3f} seconds")
                        
                        main_loop_time = time.time() - main_loop_start
                        logger.info(f"TIMING: Main processing loop took {main_loop_time:.3f} seconds")
                        
                        total_request_time = time.time() - request_start_time
                        logger.info(f"TIMING: Total request processing time: {total_request_time:.3f} seconds")
                        
                        return Response({"message": reply}, status=201)

                # For iterations that continue (i.e., had tool calls), log per-iteration timing and summary
                loop_iteration_time = time.time() - loop_iteration_start
                logger.info(f"TIMING: Loop iteration #{iteration_count} took {loop_iteration_time:.3f} seconds")
