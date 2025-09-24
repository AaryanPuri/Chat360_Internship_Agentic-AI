from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.cache import cache
from analytics.models import (
    ChatMessage,
    ChatRoom
)
from backend.settings import logger
from rest_framework.permissions import AllowAny


def get_cache_key(room_id):
    return f"agentic_chat_messages:{room_id}"


def get_messages_from_cache(room_id):
    cache_key = get_cache_key(room_id)
    cached_messages = cache.get(cache_key)

    if cached_messages:
        return cached_messages

    return []


def save_message_to_cache_and_db(
    room_id,
    role,
    message,
    chat_room,
    tool_name=None
):
    """Saves a message to both the cache and the database.
    Args:
        room_id (str): The ID of the chat room.
        role (str): The role of the message sender (e.g., "user", "assistant", "tool").
        message (str): The content of the message.
        chat_room (ChatRoom): The chat room object.
        tool_id (str, optional): The ID of the tool if the message is from a tool.
    """
    logger.debug(f"Saving message to cache and DB: {message} for room {room_id}")
    ChatMessage.objects.create(message=message, room=chat_room, role=role)

    cache_key = get_cache_key(room_id)
    cached_messages = cache.get(cache_key, [])
    if role == "tool":
        new_message = {"role": "assistant", "content": f"results from {tool_name} tool: " + message}
    else:
        new_message = {"role": role, "content": message}

    cached_messages.append(new_message)

    if len(cached_messages) > 50:
        cached_messages = cached_messages[-50:]

    cache.set(cache_key, cached_messages, timeout=3600)


def clear_cache_for_room(room_id):
    cache_key = get_cache_key(room_id)
    logger.debug(f"Clearing cache for room {room_id}")
    cache.delete(cache_key)
    logger.debug(f"Cache cleared for room {room_id}")


class CacheManagement(APIView):
    """
    API View for managing cache operations related to chat messages.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, room_id):
        messages = get_messages_from_cache(room_id)
        return Response(messages)

    def post(self, request, room_id):
        role = request.data.get("role")
        message = request.data.get("message")
        chat_room = request.data.get("chat_room")  # Assuming chat_room is passed in the request

        if not role or not message or not chat_room:
            return Response({"error": "Missing required fields"}, status=400)

        save_message_to_cache_and_db(room_id, role, message, chat_room)
        return Response({"status": "Message saved successfully"})

    def delete(self, request):
        room_id = request.data.get("room_id")
        clear_cache_for_room(room_id)
        chat_room = ChatRoom.objects.filter(session_id=room_id).first()
        if chat_room:
            logger.debug(f"Clearing captured data for room {room_id}")
            chat_room.captured_data = {}
            chat_room.save()
        logger.debug(f"Cache cleared for room {room_id}")
        return Response({"status": 200, "message": "Cache cleared successfully"})
