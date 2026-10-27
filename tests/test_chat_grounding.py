import unittest
from unittest.mock import patch

import app.features.chat.service as chat
from app.features.guidelines.service import GuidelineSourceUnavailable


class ChatGroundingTests(unittest.TestCase):
    def setUp(self):
        scope = patch('app.features.chat.service.in_scope', return_value=True)
        scope.start()
        self.addCleanup(scope.stop)

    def test_explicit_authority_overrides_history(self):
        self.assertEqual(chat.required_authorities('What is MACEA?', []), ['macea'])
        self.assertEqual(chat.required_authorities('What is ASC?', [{'role': 'user', 'content': 'MACEA'}]), ['asc'])
        self.assertEqual(chat.required_authorities('Compare MACEA and ASC', []), ['macea', 'asc'])

    def test_follow_up_uses_user_context_not_hallucinated_assistant(self):
        history = [{'role': 'user', 'content': 'What is MACEA?'},
                   {'role': 'assistant', 'content': 'ASC is the answer'}]
        self.assertEqual(chat.required_authorities('What does it cover?', history), ['macea'])

    def test_macea_retrieval_precedes_answer(self):
        def generate(messages, **kwargs):
            self.assertFalse(kwargs['show_references'])
            self.assertIn('Source authority: MACEA', messages[-1].content)
            self.assertNotIn('DECENCY CHECKLIST', messages[0].content)
            yield 'token', 'Grounded answer'
        with patch('app.features.chat.service.retrieve_guidelines', return_value='Source authority: MACEA; source: manual.pdf; page: 1') as retrieve:
            with patch('app.features.chat.service.search_loop', side_effect=generate):
                events = list(chat.chat_stream('What is MACEA?', []))
        retrieve.assert_called_once_with('macea_guidelines', 'What is MACEA?', require_sources=True)
        self.assertEqual(events[0][0], 'search')
        self.assertEqual(events[0][1]['authority'], 'MACEA')
        self.assertEqual(events[1], ('token', 'Grounded answer'))

    def test_failed_retrieval_cannot_generate_definition(self):
        with patch('app.features.chat.service.retrieve_guidelines', side_effect=GuidelineSourceUnavailable('No passages found')):
            with patch('app.features.chat.service.search_loop') as generate:
                events = list(chat.chat_stream('What is MACEA?', []))
        generate.assert_not_called()
        self.assertIn('could not verify', events[-1][1])

    def test_both_required_sources_are_queried(self):
        with patch('app.features.chat.service.retrieve_guidelines', return_value='Source passages') as retrieve:
            with patch('app.features.chat.service.search_loop', return_value=iter([])):
                list(chat.chat_stream('Compare ASC and MACEA', []))
        self.assertEqual([call.args[0] for call in retrieve.call_args_list], ['macea_guidelines', 'asc_guidelines'])


if __name__ == '__main__':
    unittest.main()
