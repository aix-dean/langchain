import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessageChunk, HumanMessage
from app.features.chat.routing import required_authorities, AuthorityUnavailable
from app.features.chat.service import chat_stream
from app.features.chat.reasoning import search_loop


class QuestionRoutingTests(unittest.TestCase):
    def test_current_question_selects_only_relevant_authorities(self):
        examples = [
            ('I want to put up LED signage in Makati. What are the requirements?', ['macea']),
            ('What dimensions are allowed for LED signage?', ['macea']),
            ('What documents do I need for interior renovation?', ['macea']),
            ('What disclaimer must a beer ad show?', ['asc']),
            ('Can a food supplement ad claim to cure disease?', ['asc']),
            ('Check installation permits and advertising claims for my LED sign', ['macea', 'asc']),
            ('MACEA only, do not include ASC', ['macea']),
            ('ASC only, not MACEA', ['asc']),
            ('Compare MACEA and ASC', ['macea', 'asc']),
        ]
        with patch('app.features.chat.routing.get_judge') as model:
            for question, expected in examples:
                with self.subTest(question=question):
                    self.assertEqual(required_authorities(question, []), expected)
            model.assert_not_called()

    def test_topic_switch_wins_and_follow_up_inherits_user_intent(self):
        history = [{'role': 'user', 'content': 'Put up LED signage in Makati'},
                   {'role': 'assistant', 'content': 'ASC rules apply'}]
        self.assertEqual(required_authorities('What about its size?', history), ['macea'])
        self.assertEqual(required_authorities('What disclaimer must a beer ad show?', history), ['asc'])
        self.assertEqual(required_authorities('What about its location?', [
            {'role': 'user', 'content': 'MACEA signage'}]), ['macea'])

    def test_unclear_wording_uses_semantic_decision_without_asc_fallback(self):
        model = Mock()
        with patch('app.features.chat.routing.get_judge', return_value=model) as create:
            for decision, expected in [('macea', ['macea']), ('asc', ['asc']), ('both', ['macea', 'asc']), ('clarify', [])]:
                model.invoke.return_value = SimpleNamespace(text='{"authority":"' + decision + '"}')
                self.assertEqual(required_authorities('Which rules cover this proposal?', []), expected)
            self.assertEqual(create.call_args.kwargs['effort'], 'off')
            model.invoke.return_value = SimpleNamespace(text='')
            with self.assertRaises(AuthorityUnavailable):
                required_authorities('Which rules cover this proposal?', [])

    def test_macea_chat_has_no_asc_checklist_and_no_asc_search(self):
        with patch('app.features.chat.service.in_scope', return_value=True), patch('app.features.chat.service.retrieve_guidelines', return_value='MACEA source') as retrieve, patch('app.features.chat.service.search_loop', return_value=iter([('token', 'MACEA answer')])) as generate:
            list(chat_stream('What are LED signage installation requirements?', []))
        self.assertEqual([call.args[0] for call in retrieve.call_args_list], ['macea_guidelines'])
        self.assertNotIn('DECENCY CHECKLIST', generate.call_args.args[0][0].content)
        self.assertEqual(generate.call_args.kwargs['allowed_authorities'], ['macea'])

    def test_unclear_question_asks_instead_of_searching_asc(self):
        with patch('app.features.chat.service.in_scope', return_value=True), patch('app.features.chat.service.required_authorities', return_value=[]), patch('app.features.chat.service.retrieve_guidelines') as retrieve:
            events = list(chat_stream('Which rules cover this proposal?', []))
        self.assertIn('Is your question about', events[-1][1])
        retrieve.assert_not_called()

    def test_model_cannot_search_unselected_authority(self):
        model = Mock()
        model.bind_tools.return_value = model
        model.stream.side_effect = [iter([AIMessageChunk(content='', tool_calls=[
            {'name': 'asc_guidelines', 'args': {'query': 'ad rules'}, 'id': 'wrong'},
            {'name': 'macea_guidelines', 'args': {'query': 'sign placement'}, 'id': 'right'},
        ])]), iter([AIMessageChunk(content='MACEA answer')])]
        with patch('app.features.chat.reasoning.get_judge', return_value=model), patch('app.features.chat.reasoning.model_capabilities', return_value={'tools'}), patch('app.features.chat.reasoning.retrieve_guidelines', return_value='MACEA passage') as retrieve:
            events = list(search_loop([HumanMessage('Sign placement')], allowed_authorities=['macea']))
        self.assertEqual([tool.name for tool in model.bind_tools.call_args.args[0]], ['macea_guidelines'])
        retrieve.assert_called_once_with('macea_guidelines', 'sign placement', set())
        self.assertEqual([data['authority'] for kind, data in events if kind == 'search'], ['MACEA'])


if __name__ == '__main__':
    unittest.main()
