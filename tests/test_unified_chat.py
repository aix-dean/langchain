import unittest
from unittest.mock import patch
from app.features.chat.unified import unified_stream
from app.features.macea.schemas import CaseContext

class UnifiedChatTests(unittest.TestCase):
    def test_main_chat_starts_letter_intake_without_separate_mode(self):
        with patch('app.features.chat.unified.assistance_stream', return_value=iter([('token', 'Which building?')])) as assist:
            self.assertEqual(list(unified_stream('Draft a request letter for MACEA', [])), [('token', 'Which building?')])
            self.assertEqual(assist.call_args.args[0].context.task, 'draft_letter')

    def test_switch_to_asc_preserves_saved_case(self):
        case = CaseContext(task='draft_letter', facts={'applicant': 'Example Co'})
        with patch('app.features.chat.unified.chat_stream', return_value=iter([('token', 'ASC answer')])) as chat, patch('app.features.chat.unified.assistance_stream') as assist:
            list(unified_stream('What are ASC alcohol disclaimers?', [], case))
            chat.assert_called_once()
            assist.assert_not_called()
        self.assertEqual(case.facts.applicant, 'Example Co')

    def test_short_followup_continues_intake_in_same_chat(self):
        with patch('app.features.chat.unified.assistance_stream', return_value=iter([])) as assist:
            list(unified_stream('Example Co', [], CaseContext(task='draft_letter')))
            self.assertEqual(assist.call_args.args[0].message, 'Example Co')
