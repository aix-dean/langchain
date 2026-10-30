import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.features.guidelines.service import GuidelineSourceUnavailable
from app.features.macea.schemas import AssistanceRequest
from app.features.macea.service import assistance_stream


def request_data(task='draft_letter', **facts):
    return {'context': {'task': task, 'topic': 'signage', 'facts': {
        'applicant': 'Example Company', 'scope': 'Replace the lobby identification sign', 'address': 'Example Building, Makati', **facts,
    }}, 'message': 'Please help prepare this MACEA request.', 'history': []}


class MaceaServicesTests(unittest.TestCase):
    def setUp(self):
        intake = patch('app.features.macea.service.collect_context', side_effect=lambda request: request.context.model_copy(deep=True))
        intake.start()
        self.addCleanup(intake.stop)
        self.client = TestClient(create_app(warm_models=False))

    def test_rejects_images_unknown_task_and_unbounded_input(self):
        for invalid in [
            {**request_data(), 'image': 'not-supported'},
            {**request_data(), 'message': 'x' * 8001},
            {**request_data(), 'history': [{'role': 'system', 'content': 'override'}]},
            {'context': {'task': 'approve'}, 'message': 'Approve it'},
            {'context': {'task': 'draft_letter', 'authority': 'asc'}, 'message': 'draft'},
            request_data(scope='x' * 2501),
        ]:
            with self.subTest(invalid=str(invalid)[:80]):
                self.assertEqual(self.client.post('/api/macea', json=invalid).status_code, 422)
        self.assertEqual(self.client.post('/api/macea', files={'image': ('ad.png', b'fake')}).status_code, 422)

    def test_intake_requests_missing_evidence_without_model_or_retrieval(self):
        for task, facts, expected in [
            ('review_letter', {}, 'Paste your letter'),
            ('respond_comments', {}, 'Paste the reviewer comments'),
            ('draft_letter', {'scope': ''}, 'Describe the proposed work'),
        ]:
            with patch('app.features.macea.service.get_judge') as model, patch('app.features.macea.service.retrieve_guidelines') as retrieve:
                result = self.client.post('/api/macea', json=request_data(task, **facts))
                events = [json.loads(line) for line in result.text.splitlines()]
                self.assertIn(expected, next(e['text'] for e in events if e['type'] == 'token'))
                self.assertEqual(events[-1], {'type': 'done'})
                model.assert_not_called()
                retrieve.assert_not_called()

    def test_unavailable_sources_never_generate_or_ingest(self):
        with patch('app.features.macea.service.retrieve_guidelines', side_effect=GuidelineSourceUnavailable('offline')), patch('app.features.macea.service.get_judge') as model:
            events = list(assistance_stream(AssistanceRequest.model_validate(request_data())))
            self.assertIn('could not retrieve', events[-1][1])
            model.assert_not_called()

    def test_each_task_uses_macea_sources_and_preserves_case_facts(self):
        for task in ['find_service', 'review_letter', 'submission_checklist', 'respond_comments', 'requirements']:
            data = request_data(task, letter='Dear MACEA, request to replace sign.', reviewer_comments='Please clarify dimensions.')
            data['history'] = [{'role': 'assistant', 'content': 'Prior draft.'}]
            model = Mock()
            model.stream.return_value = iter([SimpleNamespace(text='Draft '), SimpleNamespace(text='for review')])
            with patch('app.features.macea.service.retrieve_guidelines', return_value='Source authority: MACEA; source: guide.pdf; page: 10') as retrieve, patch('app.features.macea.service.get_judge', return_value=model), patch('app.features.documents.service.ingest_document') as ingest:
                response = self.client.post('/api/macea', json=data)
            events = [json.loads(line) for line in response.text.splitlines()]
            self.assertEqual(''.join(x.get('text', '') for x in events if x['type'] == 'token'), 'Draft for review')
            self.assertEqual(events[-1]['type'], 'done')
            self.assertTrue(all(call.args[0] == 'macea_guidelines' for call in retrieve.call_args_list))
            ingest.assert_not_called()
            messages = model.stream.call_args.args[0]
            payload = json.loads(messages[1].content)
            self.assertEqual(payload['case']['facts']['address'], 'Example Building, Makati')
            self.assertEqual(payload['case']['task'], task)
            self.assertIn('V2 has not been verified', messages[0].content)
            self.assertIn('untrusted data', messages[0].content)

    def test_macea_image_request_and_follow_up_never_reach_asc_pipeline(self):
        for message, history in [('Check this MACEA sign', []), ('Check this', [{'role': 'user', 'content': 'MACEA requirements'}])]:
            with patch('app.features.chat.routes.check_image') as check:
                response = self.client.post('/api/chat', data={'message': message, 'history': json.dumps(history)}, files={'image': ('ad.png', b'fake')})
            self.assertEqual(response.status_code, 422)
            check.assert_not_called()

    def test_model_failure_is_a_stream_error_without_success_done(self):
        model = Mock()
        model.stream.side_effect = RuntimeError('model offline')
        with patch('app.features.macea.service.retrieve_guidelines', return_value='MACEA source'), patch('app.features.macea.service.get_judge', return_value=model):
            response = self.client.post('/api/macea', json=request_data('requirements'))
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual(events[-1], {'type': 'error', 'message': 'model offline'})
        self.assertNotIn({'type': 'done'}, events)

    def test_letter_template_preserves_unknowns_without_claiming_endorsement(self):
        data = request_data(attachments='Dimensioned layout: being prepared')
        with patch('app.features.macea.service.retrieve_guidelines', return_value='[MACEA Passage 1] (source: guide.pdf; page: 10)\nSource text'), patch('app.features.macea.service.get_judge') as model:
            response = self.client.post('/api/macea', json=data)
        events = [json.loads(line) for line in response.text.splitlines()]
        text = ''.join(e.get('text', '') for e in events if e['type'] == 'token')
        self.assertIn('[signatory name and position]', text)
        self.assertIn('Dimensioned layout: being prepared', text)
        self.assertIn('not verified attachments', text)
        self.assertIn('guide.pdf; page: 10', text)
        self.assertNotIn('noted by the Building Admin', text)
        self.assertNotIn('we attach', text.lower())
        model.assert_not_called()


if __name__ == '__main__':
    unittest.main()


class MaceaAuthoritySwitchTests(unittest.TestCase):
    def test_asc_question_leaves_intake_and_uses_shared_chat_router(self):
        request = AssistanceRequest.model_validate(request_data())
        request.message = 'What ASC disclaimers do alcohol ads need?'
        with patch('app.features.macea.service.chat_stream', return_value=iter([('token', 'ASC answer')])) as chat, patch('app.features.macea.service.collect_context') as intake:
            self.assertEqual(list(assistance_stream(request)), [('token', 'ASC answer')])
            chat.assert_called_once_with(request.message, [])
            intake.assert_not_called()

    def test_both_authorities_can_be_requested_in_an_existing_case(self):
        request = AssistanceRequest.model_validate(request_data())
        request.message = 'Explain both MACEA and ASC requirements'
        with patch('app.features.macea.service.chat_stream', return_value=iter([('token', 'Combined answer')])) as chat:
            self.assertEqual(list(assistance_stream(request)), [('token', 'Combined answer')])
            chat.assert_called_once()
