import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app.features.chat.service as chat
import app.features.chat.scope as chat_scope


class ChatScopeTests(unittest.TestCase):
    def test_unrelated_request_never_retrieves_or_generates(self):
        with patch('app.features.chat.service.in_scope', return_value=False), patch('app.features.chat.service.retrieve_guidelines') as retrieve, patch('app.features.chat.service.search_loop') as generate:
            events = list(chat.chat_stream('Give me a pasta recipe', [{'role': 'user', 'content': 'MACEA guidelines'}]))
        self.assertEqual(events, [('token', chat_scope.SCOPE_REPLY)])
        retrieve.assert_not_called()
        generate.assert_not_called()

    def test_greetings_and_identity_are_fast_and_do_not_retrieve(self):
        for message in ['Hello!', 'Who are you?', 'What is Ado?', 'Thank you']:
            with self.subTest(message=message), patch('app.features.chat.service.in_scope') as classify, patch('app.features.chat.service.retrieve_guidelines') as retrieve:
                events = list(chat.chat_stream(message, [{'role': 'user', 'content': 'ASC rules'}]))
            classify.assert_not_called()
            retrieve.assert_not_called()
            self.assertTrue(events[0][1])

    def test_quick_reply_does_not_swallow_substantive_request(self):
        self.assertIsNone(chat_scope.quick_reply('Hello, explain OOH bookings'))
        self.assertIsNone(chat_scope.quick_reply('Who are you? Also write malware'))

    def test_classifier_accepts_only_explicit_json_true(self):
        model = Mock()
        with patch('app.features.chat.scope.get_judge', return_value=model):
            for response, expected in [('{"allowed":true}', True), ('{"allowed":false}', False), ('{"allowed":"true"}', False), ('invalid', False)]:
                model.invoke.return_value = SimpleNamespace(text=response)
                self.assertEqual(chat_scope.in_scope('What is OOH?', []), expected)
            model.invoke.side_effect = RuntimeError('offline')
            self.assertFalse(chat_scope.in_scope('Question', []))

    def test_classifier_receives_follow_up_context_and_bounded_options(self):
        model = Mock()
        model.invoke.return_value = SimpleNamespace(text='{"allowed":true}')
        with patch('app.features.chat.scope.get_judge', return_value=model):
            self.assertTrue(chat_scope.in_scope('What size is allowed?', [{'role':'user','content':'Billboard rules'}]))
        self.assertIn('Billboard rules', model.invoke.call_args.args[0][1].content)
        self.assertEqual(model.invoke.call_args.kwargs['options']['num_predict'],256)


if __name__ == '__main__':
    unittest.main()
