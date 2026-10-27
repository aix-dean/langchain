import json
import unittest
from unittest.mock import Mock, patch
from langchain_core.messages import HumanMessage, SystemMessage, AIMessageChunk

from app.core.context_compression import compact_instructions, audit_payload, compact_json
import app.features.chat.service as chat
import app.features.chat.reasoning as judge


class ContextCompressionTests(unittest.TestCase):
    def test_every_instruction_line_is_preserved(self):
        text = 'Title\n\n=====\nRule: NEVER infer missing warnings.\n\nQuote: "DRINK RESPONSIBLY"\n'
        self.assertEqual(compact_instructions(text), 'Title\nRule: NEVER infer missing warnings.\nQuote: "DRINK RESPONSIBLY"')
        original = chat.read_prompt('judge.md')
        meaningful = [line.rstrip() for line in original.splitlines() if line.strip() and set(line.strip()) != {'='}]
        self.assertEqual(compact_instructions(original).splitlines(), meaningful)

    def test_audit_preserves_observations_rules_and_distinct_authorities(self):
        description = '1. ALL TEXT: "NOT medicine"\n\n7. UNREADABLE: bottom line'
        result = {'result': 'NEEDS_REVIEW', 'description': description, 'reasons': [{'evidence': 'NOT medicine'}]}
        sources = ['ASC; page: 1; Exact text', 'ASC; page: 1; Exact text', 'MACEA; page: 1; Exact text', 'ASC; page: 2; Exact text']
        rules = {'G-01': {'summary': 'Exact rule'}}
        payload = audit_payload(result, description, sources, rules)
        self.assertEqual(payload['observations'], description)
        self.assertEqual(payload['retrieved_passages'], [sources[0], sources[2], sources[3]])
        self.assertEqual(payload['applicable_rule_summaries'], rules)
        self.assertEqual(payload['proposed_result']['reasons'], result['reasons'])
        self.assertNotIn('description', payload['proposed_result'])
        self.assertIn('description', result)
        self.assertEqual(json.loads(compact_json(payload)), payload)

    def test_different_translation_is_not_discarded(self):
        payload = audit_payload({'description_en': 'Translated evidence'}, 'Original evidence', [], {})
        self.assertEqual(payload['proposed_result']['description_en'], 'Translated evidence')

    def test_macea_instructions_are_only_included_once(self):
        model = Mock()
        model.stream.return_value = iter([AIMessageChunk(content='Answer')])
        instructions = compact_instructions(chat.read_prompt('macea.md'))
        with patch('app.features.chat.reasoning.get_judge', return_value=model), patch('app.features.chat.reasoning.model_capabilities', return_value=set()):
            list(judge.search_loop([SystemMessage(instructions), HumanMessage('What is MACEA?')], max_searches=0))
        messages = model.stream.call_args.args[0]
        self.assertEqual(sum(str(message.content).count(instructions) for message in messages), 1)


if __name__ == '__main__':
    unittest.main()
