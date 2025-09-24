from analytics.models import (
    ChatRoom
)
from backend.settings import logger


def get_auth_token(session_id):
    chat_room = ChatRoom.objects.get(session_id=session_id)
    captured_data = chat_room.captured_data if chat_room else None
    logger.debug(f"Captured Data: {captured_data}")
    if captured_data:
        return captured_data.get('@auth_code')
    logger.warning(f"No captured data found for session_id: {session_id}")
    return None

def get_order_amount(session_id):
   chat_room = ChatRoom.objects.get(session_id=session_id)
   captured_data = chat_room.captured_data if chat_room else None
   logger.debug(f"Captured Data: {captured_data}")
   if captured_data:
       return captured_data.get('@net_amount')
   logger.warning(f"No captured data found for session_id: {session_id}")
   return None


def get_order_id(session_id):
   chat_room = ChatRoom.objects.get(session_id=session_id)
   captured_data = chat_room.captured_data if chat_room else None
   logger.debug(f"Captured Data: {captured_data}")
   if captured_data:
       return captured_data.get('@order_id')
   logger.warning(f"No captured data found for session_id: {session_id}")
   return None