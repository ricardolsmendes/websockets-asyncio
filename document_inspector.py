# Copyright 2021 Ricardo Mendes
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import json
import logging
import threading

import websockets

import send_receive_sync_helper


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
        """Gets information from all graphical components that belong to a given document.

        This method provides users a synchronized entry point, hiding the asynchronous processing
        complexity from them.

        Args:
            doc_id: The document identifier.
            timeout: Max seconds to wait.

        Returns:
            A ``list`` with the document's graphical components information.
        """
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
        except Exception:
            logging.info('Something wrong happened while the workload was running.')
            cls.__cancel_all_tasks(event_loop)
            raise
        finally:
            event_loop.close()

    async def __get_widgets(self, doc_id, timeout):
        async with self.__connect_websocket() as websocket:
            sync_helper = send_receive_sync_helper.SendReceiveSyncHelper()

            await self.__start_get_widgets_workload(websocket, doc_id, sync_helper)

            msg_sender = self.__send_get_widgets_messages
            msg_receiver = self.__receive_get_widgets_messages
            return await asyncio.wait_for(
                self.__hold_websocket_communication(msg_sender(websocket, sync_helper),
                                                    msg_receiver(websocket, sync_helper)),
                timeout)

    def __connect_websocket(self):
        """Opens a websocket connection.

        Returns:
            An awaiting function that yields a :class:`WebSocketClientProtocol` which can then be
            used to send and receive messages.
        """
        return websockets.connect(uri=self.__server_uri)

    async def __start_get_widgets_workload(self, websocket, doc_id, sync_helper):
        message_id = await self.__send_get_document_message(websocket, doc_id)
        sync_helper.add_pending_reply_id(message_id, self.__GET_DOCUMENT)

    @classmethod
    async def __hold_websocket_communication(cls, msg_sender, msg_receiver):
        """Holds a websocket communication session until the awaitable message sender and receiver
        are done.

        Args:
            msg_sender: A coroutine or future that sends messages.
            msg_receiver: A coroutine or future that receives messages.

        Returns:
            The result of the receiver.
        """
        results = await asyncio.gather(*[msg_sender, msg_receiver])
        # The ``results`` list is expected to have two elements. The first one stores the result of
        # the message sender and can be ignored. The second one stores the result of the receiver,
        # which means the object to be returned on successful execution.
        return results[1]

    @classmethod
    async def __receive_get_widgets_messages(cls, websocket, sync_helper):
        results = []
        async for message in websocket:
            reply = json.loads(message)
            message_id = reply.get('id')
            if not message_id:
                logging.info('Unhandled API message: %s', message)
                continue

            logging.debug('Reply received: %d', message_id)
            if sync_helper.is_pending_reply(message_id, cls.__GET_WIDGET_PROPERTIES):
                results.append(reply['result'])
            else:
                sync_helper.add_unhandled_reply(reply)

            sync_helper.remove_pending_reply_id(message_id)
            sync_helper.notify_new_reply()

        return results

    async def __send_get_widgets_messages(self, websocket, sync_helper):
        while not sync_helper.were_all_replies_precessed():
            if not sync_helper.is_there_reply_notification():
                await sync_helper.wait_for_replies()
                sync_helper.clear_reply_notifications()
            for reply in sync_helper.get_all_unhandled_replies():
                await self.__send_follow_up_msg_get_widgets(websocket, sync_helper, reply)

        # Closes the websocket when there is no further reply to process.
        await websocket.close()

    async def __send_follow_up_msg_get_widgets(self, websocket, sync_helper, reply):
        message_id = reply.get('id')
        if sync_helper.is_method(message_id, self.__GET_DOCUMENT):
            await self.__handle_get_document_reply(websocket, sync_helper, reply)
            sync_helper.remove_unhandled_reply(reply)
        elif sync_helper.is_method(message_id, self.__GET_WIDGET_CONTAINER):
            await self.__handle_get_widget_container_reply(websocket, sync_helper, reply)
            sync_helper.remove_unhandled_reply(reply)

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

    async def __handle_get_document_reply(self, websocket, sync_helper, reply):
        result = reply['result']
        if not result['type'] in self.__GUI_DOC_TYPES:
            return

        container_ids = result['widgetContainerIds']
        get_widget_container_msg_ids = await asyncio.gather(*[
            self.__send_get_widget_container_message(websocket, container_id)
            for container_id in container_ids
        ])
        sync_helper.add_pending_reply_ids(
            get_widget_container_msg_ids, self.__GET_WIDGET_CONTAINER)

    async def __handle_get_widget_container_reply(self, websocket, sync_helper, reply):
        widget_id = reply['result']['id']
        get_widget_properties_msg_id = \
            await self.__send_get_widget_properties_message(websocket, widget_id)
        sync_helper.add_pending_reply_id(
            get_widget_properties_msg_id, self.__GET_WIDGET_PROPERTIES)

    @classmethod
    def __cancel_all_tasks(cls, event_loop):
        logging.info('All tasks will be canceled...')
        for task in asyncio.Task.all_tasks(loop=event_loop):
            task.cancel()

    def __generate_message_id(self):
        with self.__messages_counter_thread_lock:
            self.__messages_counter += 1
            return self.__messages_counter
