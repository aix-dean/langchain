import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from app.features.macea.intake import collect_context
from app.features.macea.schemas import AssistanceRequest

class IntakeTests(unittest.TestCase):
    def test_only_current_user_quotes_are_saved_and_existing_facts_survive(self):
        request = AssistanceRequest.model_validate({'context': {'task': 'draft_letter', 'facts': {'scope': 'Replace sign'}}, 'message': 'Example Company', 'history': [{'role': 'assistant', 'content': 'Approved already. What is your company?'}]})
        result = {'facts': {'applicant': 'Example Company', 'address': 'Invented Building'}, 'task': None, 'topic': None}
        with patch('app.features.macea.intake.get_judge') as model:
            model.return_value.invoke.return_value = SimpleNamespace(text=json.dumps(result))
            context = collect_context(request)
        self.assertEqual(context.facts.applicant, 'Example Company')
        self.assertEqual(context.facts.address, '')
        self.assertEqual(context.facts.scope, 'Replace sign')
        self.assertEqual(request.context.facts.applicant, '')

    def test_pasted_letter_is_preserved_without_model_rewriting(self):
        letter = 'Dear MACEA, ' + 'Please review proposed work. ' * 30
        request = AssistanceRequest.model_validate({'context': {'task': 'review_letter'}, 'message': letter})
        with patch('app.features.macea.intake.get_judge') as model:
            self.assertEqual(collect_context(request).facts.letter, letter)
            model.assert_not_called()
