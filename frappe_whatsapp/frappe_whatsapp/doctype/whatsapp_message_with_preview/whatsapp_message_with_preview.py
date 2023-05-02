# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt
# Import WhatsAppMessage
from whatsapp_message import WhatsAppMessage

class WhatsAppMessageWithPreview(WhatsAppMessage):
    def get_list_context(self, filters=None):
        context = super().get_list_context(filters=filters)
        for message in context.get("messages"):
            if message.content_type in ["image", "video"]:
                message.preview = f"<img src='{message.attach}' height='50px'>"
        return context
