import asyncio


class SendReceiveSyncHelper:
    """Utility class with common features for handling message/replies synchronization over
    websocket communication sessions.

    Attributes:
        __pending_reply_ids:
            A ``list`` containing the ids of the pending replies, which means the messages
            identified by them were sent but not replied yet.
        __messages_history:
            A ``dict`` containing a full history of the messages known by a given
            ``WebsocketRepliesManager`` instance, represented as ``message-id: method`` items.
            It is automatically fulfilled when pending ids are added to ``__pending_ids``.
        __unhandled_replies:
            A ``list`` containing all reply objects that were received but not handled yet.
        __new_reply_event:
            A signal used by the consumer to notify the producer on the arrival of new replies, so
            the producer can take actions such as sending follow-up messages.
    """

    def __init__(self):
        self.__pending_reply_ids = []
        self.__messages_history = {}
        self.__unhandled_replies = []
        self.__new_reply_event = asyncio.Event()

    def add_pending_reply_id(self, message_id, method):
        self.__pending_reply_ids.append(message_id)
        self.__messages_history[message_id] = method

    def add_pending_reply_ids(self, message_ids, method):
        for message_id in message_ids:
            self.add_pending_reply_id(message_id, method)

    def remove_pending_reply_id(self, message_id):
        self.__pending_reply_ids.remove(message_id)

    def is_pending_reply(self, message_id, method):
        return message_id in self.__pending_reply_ids and self.is_method(
            message_id, method)

    def is_method(self, message_id, method):
        return method == self.__messages_history.get(message_id)

    def add_unhandled_reply(self, reply):
        self.__unhandled_replies.append(reply)

    def remove_unhandled_reply(self, reply):
        self.__unhandled_replies.remove(reply)

    def get_all_unhandled_replies(self):
        return self.__unhandled_replies

    def were_all_replies_precessed(self):
        return not self.__pending_reply_ids and not self.__unhandled_replies

    def notify_new_reply(self):
        self.__new_reply_event.set()

    async def wait_for_replies(self):
        return await self.__new_reply_event.wait()

    def is_there_reply_notification(self):
        return self.__new_reply_event.is_set()

    def clear_reply_notifications(self):
        self.__new_reply_event.clear()
