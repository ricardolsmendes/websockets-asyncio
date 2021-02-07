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

import unittest
from unittest import mock

import document_inspector


class DocumentInspectorTest(unittest.TestCase):
    __INSPECTOR_CLASS = 'document_inspector.DocumentInspector'

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
