import asyncio
import json
import logging

import websockets

import websocket_responses_manager


class DocumentScanner:
    # Methods to be used in the requests.
    __GET_DOCUMENT = 'GetDocument'
    __GET_FIELDS_SUMMARY = 'GetFieldsSummary'
    __GET_WIDGET_CONTAINER = 'GetWidgetContainer'
    __GET_WIDGET_PROPERTIES = 'GetWidgetProperties'

    def __init__(self, server_uri):
        self.__server_uri = server_uri
        self.__requests_counter = 0

    def scan_widgets(self, doc_id, timeout=60):
        try:
            return self.__run_until_complete(self.__scan_widgets(doc_id, timeout))
        except Exception:
            logging.warning("error on scan_widgets:", exc_info=True)
            return []

    @classmethod
    def __run_until_complete(cls, future):
        event_loop = asyncio.new_event_loop()
        try:
            return event_loop.run_until_complete(future)
        except asyncio.TimeoutError:
            cls.__handle_event_loop_exec_timeout(event_loop)
            raise

    async def __scan_widgets(self, doc_id, timeout):
        async with self.__connect_websocket() as websocket:
            responses_manager = websocket_responses_manager.WebsocketResponsesManager()

            await self.__start_scan_widgets_workload(websocket, doc_id, responses_manager)

            consumer = self.__consume_scan_widgets_messages
            producer = self.__produce_scan_widgets_messages
            return await asyncio.wait_for(
                self.__handle_websocket_communication(
                    consumer(websocket, responses_manager),
                    producer(websocket, responses_manager)),
                timeout)

    def __connect_websocket(self):
        """Opens a websocket connection.

        Returns:
            An awaiting function that yields a :class:`WebSocketClientProtocol` which can then be
            used to send and receive messages.
        """
        return websockets.connect(uri=self.__server_uri)

    async def __start_scan_widgets_workload(self, websocket, doc_id, responses_manager):
        request_id = await self.__send_get_document_request(websocket, doc_id)
        responses_manager.add_pending_id(request_id, self.__GET_DOCUMENT)

    @classmethod
    async def __handle_websocket_communication(cls, consumer_future, producer_future):
        # The 'results' array is expected to have two elements. The first one stores the result of
        # the consumer, which means the object to be returned on a successful execution. The second
        # one stores the result of the producer and can be ignored.
        results = await asyncio.gather(*[consumer_future, producer_future])
        return results[0]

    @classmethod
    async def __consume_scan_widgets_messages(cls, websocket, responses_manager):
        results = []
        async for message in websocket:
            response = json.loads(message)
            response_id = response.get('id')
            if not response_id:
                logging.warning('Unknown API message: %s', message)
                continue

            logging.debug('Response received: %d', response_id)
            if responses_manager.is_pending(response_id, cls.__GET_WIDGET_PROPERTIES):
                results.append(response['result']['properties'])
            else:
                responses_manager.add_unhandled(response)

            responses_manager.remove_pending_id(response_id)
            responses_manager.notify_new_response()

        return results

    async def __produce_scan_widgets_messages(self, websocket, responses_manager):
        while not responses_manager.were_all_precessed():
            if not responses_manager.is_there_response_notification():
                await responses_manager.wait_for_responses()
                responses_manager.clear_response_notifications()
            for response in responses_manager.get_all_unhandled():
                await self.__send_follow_up_msg_scan_widgets(
                    websocket, responses_manager, response)

        # Closes the websocket when there is no further response to process.
        await websocket.close()

    async def __send_follow_up_msg_scan_widgets(self, websocket, responses_manager, response):
        response_id = response.get('id')
        if responses_manager.is_method(response_id, self.__GET_DOCUMENT):
            await self.__handle_get_document_response(websocket, responses_manager, response)
            responses_manager.remove_unhandled(response)
        elif responses_manager.is_method(response_id, self.__GET_FIELDS_SUMMARY):
            await self.__handle_get_fields_summary_response(websocket, responses_manager, response)
            responses_manager.remove_unhandled(response)
        elif responses_manager.is_method(response_id, self.__GET_WIDGET_CONTAINER):
            await self.__handle_get_widget_container_response(
                websocket, responses_manager, response)
            responses_manager.remove_unhandled(response)

    async def __send_get_document_request(self, websocket, doc_id):
        """Sends a Get Document request.

        Returns:
            The request id.
        """
        request_id = self.__generate_request_id()
        await websocket.send(
            json.dumps({
                'method': self.__GET_DOCUMENT,
                'params': {
                    'id': doc_id
                },
                'id': request_id
            }))

        logging.debug('Get Document request sent: %d', request_id)
        return request_id

    async def __send_get_fields_summary_request(self, websocket, doc_id):
        """Sends a Get Fields Summary request.

        Returns:
            The request id.
        """
        request_id = self.__generate_request_id()
        await websocket.send(
            json.dumps({
                'method': self.__GET_FIELDS_SUMMARY,
                'params': {
                    'documentId': doc_id,
                    'fieldType': 'widget'
                },
                'id': request_id,
            }))

        logging.debug('Get Fields Summary request sent: %d', request_id)
        return request_id

    async def __send_get_widget_container_request(self, websocket, container_id):
        """Sends a Get Widget Container request.

        Returns:
            The request id.
        """
        request_id = self.__generate_request_id()
        await websocket.send(
            json.dumps({
                'method': self.__GET_WIDGET_CONTAINER,
                'params': {
                    'id': container_id,
                },
                'id': request_id,
            }))

        logging.debug('Get Widget Container request sent: %d', request_id)
        return request_id

    async def __send_get_widget_properties_request(self, websocket, widget_id):
        """Sends a Get Widget Properties request.

        Returns:
            The request id.
        """
        request_id = self.__generate_request_id()
        await websocket.send(
            json.dumps({
                'method': self.__GET_WIDGET_PROPERTIES,
                'params': {
                    'id': widget_id,
                },
                'id': request_id,
            }))

        logging.debug('Get Widget Properties request sent: %d', request_id)
        return request_id

    async def __handle_get_document_response(self, websocket, responses_manager, response):
        result = response['result']
        if result['hasWidgets']:
            doc_id = result['id']
            follow_up_req_id = await self.__send_get_fields_summary_request(websocket, doc_id)
            responses_manager.add_pending_id(follow_up_req_id, self.__GET_FIELDS_SUMMARY)

    async def __handle_get_fields_summary_response(self, websocket, responses_manager, response):
        containers_summary = response['result']['fields']
        container_ids = [container['id'] for container in containers_summary]
        follow_up_req_ids = await asyncio.gather(*[
            self.__send_get_widget_container_request(websocket, container_id)
            for container_id in container_ids
        ])
        responses_manager.add_pending_ids(follow_up_req_ids, self.__GET_WIDGET_CONTAINER)

    async def __handle_get_widget_container_response(self, websocket, responses_manager, response):
        widget_id = response['result']['id']
        follow_up_req_id = await self.__send_get_widget_properties_request(websocket, widget_id)
        responses_manager.add_pending_id(follow_up_req_id, self.__GET_WIDGET_PROPERTIES)

    @classmethod
    def __handle_event_loop_exec_timeout(cls, event_loop):
        logging.warning('Timeout reached during the websocket communication session.')
        for task in asyncio.Task.all_tasks(loop=event_loop):
            task.cancel()
        event_loop.stop()

    def __generate_request_id(self):
        self.__requests_counter += 1
        return self.__requests_counter
