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
            for response, expected in [('{"allowed":true}', True), ('{"allowed":false}', False)]:
                model.invoke.return_value = SimpleNamespace(text=response)
                self.assertEqual(chat_scope.in_scope('What is OOH?', []), expected)
            for response in ['{"allowed":"true"}', 'invalid', '']:
                model.invoke.return_value = SimpleNamespace(text=response)
                with self.assertRaises(chat_scope.ScopeUnavailable):
                    chat_scope.in_scope('What is OOH?', [])
            model.invoke.side_effect = RuntimeError('offline')
            with self.assertRaises(chat_scope.ScopeUnavailable):
                chat_scope.in_scope('Question', [])

    def test_classifier_receives_follow_up_context_and_bounded_options(self):
        model = Mock()
        model.invoke.return_value = SimpleNamespace(text='{"allowed":true}')
        with patch('app.features.chat.scope.get_judge', return_value=model):
            self.assertTrue(chat_scope.in_scope('What size is allowed?', [{'role':'user','content':'Billboard rules'}]))
        self.assertIn('Billboard rules', model.invoke.call_args.args[0][1].content)
        self.assertEqual(model.invoke.call_args.kwargs['options']['num_predict'],256)

    def test_led_signage_regression_disables_reasoning_and_searches_macea(self):
        message = 'i want to put up a led signage in makati what are the requirements\nsvg'
        model = Mock()
        model.invoke.return_value = SimpleNamespace(text='{"allowed":true}')
        with patch('app.features.chat.scope.get_judge', return_value=model) as judge, patch('app.features.chat.service.retrieve_guidelines', return_value='Source passages') as retrieve, patch('app.features.chat.service.search_loop', return_value=iter([('token', 'Requirements')])):
            events = list(chat.chat_stream(message, []))
        judge.assert_called_once_with(temperature=0, effort='off')
        self.assertEqual([call.args[0] for call in retrieve.call_args_list], ['macea_guidelines'])
        self.assertNotIn(('token', chat_scope.SCOPE_REPLY), events)

    def test_classifier_failure_does_not_mislabel_question_as_off_topic(self):
        with patch('app.features.chat.service.in_scope', side_effect=chat_scope.ScopeUnavailable()), patch('app.features.chat.service.retrieve_guidelines') as retrieve:
            events = list(chat.chat_stream('LED signage requirements', []))
        self.assertIn('does not mean your question is off-topic', events[-1][1])
        retrieve.assert_not_called()


if __name__ == '__main__':
    unittest.main()
