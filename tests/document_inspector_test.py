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
import unittest
from unittest import mock

import document_inspector


class DocumentInspectorTest(unittest.TestCase):
    __INSPECTOR_CLASS = 'document_inspector.DocumentInspector'
    __SYNC_HELPER_CLASS = 'document_inspector.send_receive_sync_helper.SendReceiveSyncHelper'

    def setUp(self):
        self.__document_inspector = document_inspector.DocumentInspector('wss://ws.example.com')

    @mock.patch(f'{__INSPECTOR_CLASS}._DocumentInspector__run_until_complete')
    @mock.patch(f'{__INSPECTOR_CLASS}._DocumentInspector__get_widgets', lambda *args: None)
    def test_get_widgets_should_return_widgets_on_success(self, mock_run_until_complete):
        expected_widgets = [{'id': 1, 'type': 'table'}, {'id': 2, 'type': 'chart'}]
        mock_run_until_complete.return_value = expected_widgets

        actual_widgets = self.__document_inspector.get_widgets('abc')

        self.assertEqual(expected_widgets, actual_widgets)

    @mock.patch(f'{__INSPECTOR_CLASS}._DocumentInspector__run_until_complete')
    @mock.patch(f'{__INSPECTOR_CLASS}._DocumentInspector__get_widgets', lambda *args: None)
    def test_get_widgets_should_return_empty_list_on_failure(self, mock_run_until_complete):
        mock_run_until_complete.side_effect = Exception()

        actual_widgets = self.__document_inspector.get_widgets('abc')

        self.assertEqual([], actual_widgets)

    def test_run_until_complete_should_return_coroutine_result_on_success(self):
        mock_coroutine = mock.AsyncMock()
        mock_coroutine.return_value = 'test'

        result = self.__document_inspector._DocumentInspector__run_until_complete(mock_coroutine())

        self.assertEqual('test', result)

    @mock.patch(f'{__INSPECTOR_CLASS}._DocumentInspector__cancel_all_tasks')
    def test_run_until_complete_should_cancel_all_tasks_on_failure(self, mock_cancel_all_tasks):
        mock_coroutine = mock.AsyncMock()
        mock_coroutine.side_effect = Exception()

        try:
            self.__document_inspector._DocumentInspector__run_until_complete(mock_coroutine())
        except Exception:
            pass

        mock_cancel_all_tasks.assert_called_once()

    @mock.patch(f'{__INSPECTOR_CLASS}._DocumentInspector__cancel_all_tasks', lambda *args: None)
    def test_run_until_complete_should_reraise_exception_on_failure(self):
        mock_coroutine = mock.AsyncMock()
        mock_coroutine.side_effect = Exception()

        self.assertRaises(Exception,
                          self.__document_inspector._DocumentInspector__run_until_complete,
                          mock_coroutine())

    @mock.patch(f'{__INSPECTOR_CLASS}._DocumentInspector__hold_websocket_communication',)
    @mock.patch(f'{__INSPECTOR_CLASS}._DocumentInspector__start_get_widgets_workload')
    @mock.patch(f'{__INSPECTOR_CLASS}._DocumentInspector__send_get_widgets_messages',
                lambda *args: None)
    @mock.patch(f'{__INSPECTOR_CLASS}._DocumentInspector__receive_get_widgets_messages',
                lambda *args: None)
    @mock.patch(f'{__INSPECTOR_CLASS}._DocumentInspector__connect_websocket',
                lambda *args: mock.MagicMock())
    @mock.patch(__SYNC_HELPER_CLASS, lambda *args: mock.MagicMock())
    def test_get_widgets_should_start_get_widgets_workload(self, mock_start_get_widgets_workload,
                                                           mock_hold_websocket_communication):

        mock_hold_websocket_communication.return_value = mock.AsyncMock()

        asyncio.run(self.__document_inspector._DocumentInspector__get_widgets('abc', 1))

        mock_start_get_widgets_workload.assert_called_once()

    @mock.patch('document_inspector.asyncio.wait_for')
    @mock.patch(f'{__INSPECTOR_CLASS}._DocumentInspector__hold_websocket_communication',
                lambda *args: None)
    @mock.patch(f'{__INSPECTOR_CLASS}._DocumentInspector__start_get_widgets_workload')
    @mock.patch(f'{__INSPECTOR_CLASS}._DocumentInspector__send_get_widgets_messages',
                lambda *args: None)
    @mock.patch(f'{__INSPECTOR_CLASS}._DocumentInspector__receive_get_widgets_messages',
                lambda *args: None)
    @mock.patch(f'{__INSPECTOR_CLASS}._DocumentInspector__connect_websocket',
                lambda *args: mock.MagicMock())
    @mock.patch(__SYNC_HELPER_CLASS, lambda *args: mock.MagicMock())
    def test_get_widgets_should_set_websocket_communication_timeout(
            self, mock_start_get_widgets_workload, mock_wait_for):

        mock_start_get_widgets_workload.return_value = mock.AsyncMock()

        asyncio.run(self.__document_inspector._DocumentInspector__get_widgets('abc', 1))

        mock_wait_for.assert_called_once()
