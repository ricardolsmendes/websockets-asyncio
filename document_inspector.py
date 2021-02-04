import asyncio
import json
import logging
import threading

import websockets

import websocket_replies_manager


class DocumentInspector:
    # Types of the documents to be inspected.
    __GUI_DOC_TYPES = ['biDashboard', 'slide']

    # Methods used in the sent messages.
    __GET_DOCUMENT = 'GetDocument'
    __GET_WIDGET_CONTAINER = 'GetWidgetContainer'
    __GET_WIDGET_PROPERTIES = 'GetWidgetProperties'

    def __init__(self, server_uri):
        self.__server_uri = server_uri
        self.__messages_counter = 0
        self.__messages_counter_thread_lock = threading.Lock()

    def get_widgets(self, doc_id, timeout=60):
        try:
            return self.__run_until_complete(self.__get_widgets(doc_id, timeout))
        except Exception:
            logging.warning("error on get_widgets:", exc_info=True)
            return []

    @classmethod
    def __run_until_complete(cls, future):
        event_loop = asyncio.new_event_loop()
        try:
            return event_loop.run_until_complete(future)
        except asyncio.TimeoutError:
            cls.__handle_event_loop_exec_timeout(event_loop)
            raise

    async def __get_widgets(self, doc_id, timeout):
        async with self.__connect_websocket() as websocket:
            replies_manager = websocket_replies_manager.WebsocketRepliesManager()

            await self.__start_get_widgets_workload(websocket, doc_id, replies_manager)

            consumer = self.__consume_get_widgets_messages
            producer = self.__produce_get_widgets_messages
            return await asyncio.wait_for(
                self.__handle_websocket_communication(
                    consumer(websocket, replies_manager),
                    producer(websocket, replies_manager)),
                timeout)

    def __connect_websocket(self):
        """Opens a websocket connection.

        Returns:
            An awaiting function that yields a :class:`WebSocketClientProtocol` which can then be
            used to send and receive messages.
        """
        return websockets.connect(uri=self.__server_uri)

    async def __start_get_widgets_workload(self, websocket, doc_id, replies_manager):
        message_id = await self.__send_get_document_message(websocket, doc_id)
        replies_manager.add_pending_id(message_id, self.__GET_DOCUMENT)

    @classmethod
    async def __handle_websocket_communication(cls, consumer_future, producer_future):
        # The 'results' array is expected to have two elements. The first one stores the result of
        # the consumer, which means the object to be returned on a successful execution. The second
        # one stores the result of the producer and can be ignored.
        results = await asyncio.gather(*[consumer_future, producer_future])
        return results[0]

    @classmethod
    async def __consume_get_widgets_messages(cls, websocket, replies_manager):
        results = []
        async for message in websocket:
            reply = json.loads(message)
            message_id = reply.get('id')
            if not message_id:
                logging.warning('Unknown API message: %s', message)
                continue

            logging.debug('Reply received: %d', message_id)
            if replies_manager.is_pending(message_id, cls.__GET_WIDGET_PROPERTIES):
                results.append(reply['result'])
            else:
                replies_manager.add_unhandled(reply)

            replies_manager.remove_pending_id(message_id)
            replies_manager.notify_new_reply()

        return results

    async def __produce_get_widgets_messages(self, websocket, replies_manager):
        while not replies_manager.were_all_precessed():
            if not replies_manager.is_there_reply_notification():
                await replies_manager.wait_for_replies()
                replies_manager.clear_reply_notifications()
            for reply in replies_manager.get_all_unhandled():
                await self.__send_follow_up_msg_get_widgets(websocket, replies_manager, reply)

        # Closes the websocket when there is no further reply to process.
        await websocket.close()

    async def __send_follow_up_msg_get_widgets(self, websocket, replies_manager, reply):
        message_id = reply.get('id')
        if replies_manager.is_method(message_id, self.__GET_DOCUMENT):
            await self.__handle_get_document_reply(websocket, replies_manager, reply)
            replies_manager.remove_unhandled(reply)
        elif replies_manager.is_method(message_id, self.__GET_WIDGET_CONTAINER):
            await self.__handle_get_widget_container_reply(websocket, replies_manager, reply)
            replies_manager.remove_unhandled(reply)

    async def __send_get_document_message(self, websocket, doc_id):
        """Sends a Get Document message.

        Returns:
            The message id.
        """
        message_id = self.__generate_message_id()
        await websocket.send(
            json.dumps({
                'method': self.__GET_DOCUMENT,
                'params': {
                    'id': doc_id
                },
                'id': message_id
            }))

        logging.debug('Get Document message sent: %d', message_id)
        return message_id

    async def __send_get_widget_container_message(self, websocket, container_id):
        """Sends a Get Widget Container message.

        Returns:
            The message id.
        """
        message_id = self.__generate_message_id()
        await websocket.send(
            json.dumps({
                'method': self.__GET_WIDGET_CONTAINER,
                'params': {
                    'id': container_id,
                },
                'id': message_id,
            }))

        logging.debug('Get Widget Container message sent: %d', message_id)
        return message_id

    async def __send_get_widget_properties_message(self, websocket, widget_id):
        """Sends a Get Widget Properties message.

        Returns:
            The message id.
        """
        message_id = self.__generate_message_id()
        await websocket.send(
            json.dumps({
                'method': self.__GET_WIDGET_PROPERTIES,
                'params': {
                    'id': widget_id,
                },
                'id': message_id,
            }))

        logging.debug('Get Widget Properties message sent: %d', message_id)
        return message_id

    async def __handle_get_document_reply(self, websocket, replies_manager, reply):
        result = reply['result']
        if not result['type'] in self.__GUI_DOC_TYPES:
            return

        container_ids = result['guiContainers']
        follow_up_msg_ids = await asyncio.gather(*[
            self.__send_get_widget_container_message(websocket, container_id)
            for container_id in container_ids
        ])
        replies_manager.add_pending_ids(follow_up_msg_ids, self.__GET_WIDGET_CONTAINER)

    async def __handle_get_widget_container_reply(self, websocket, replies_manager, reply):
        widget_id = reply['result']['id']
        follow_up_msg_id = await self.__send_get_widget_properties_message(websocket, widget_id)
        replies_manager.add_pending_id(follow_up_msg_id, self.__GET_WIDGET_PROPERTIES)

    @classmethod
    def __handle_event_loop_exec_timeout(cls, event_loop):
        logging.warning('Timeout reached during the websocket communication session.')
        for task in asyncio.Task.all_tasks(loop=event_loop):
            task.cancel()
        event_loop.stop()

    def __generate_message_id(self):
        with self.__messages_counter_thread_lock:
            self.__messages_counter += 1
            return self.__messages_counter
