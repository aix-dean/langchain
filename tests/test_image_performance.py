import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessageChunk
import app.features.ad_review.judgment as judge
import app.features.ad_review.service as pipeline
import app.infrastructure.ollama.vision as vision


DESCRIPTION = '''1. ALL TEXT: ACME beer. DRINK RESPONSIBLY
2. PRODUCT: ACME alcoholic beer
3. CLAIMS: NONE
4. WARNINGS AND FINE PRINT: DRINK RESPONSIBLY, bottom
5. PEOPLE: NONE
6. OTHER VISUALS: NONE
7. UNREADABLE: NONE'''


class ImagePerformanceTests(unittest.TestCase):
    def test_one_judgment_after_retrieval_and_full_checklist_retained(self):
        model = Mock()
        model.stream.return_value = iter([AIMessageChunk(content='{"verdict":"COMPLIANT"}')])
        with patch('app.features.ad_review.judgment.get_judge', return_value=model) as get_model:
            with patch('app.features.ad_review.judgment.retrieve_guidelines', return_value='ASC source passages') as retrieve:
                events = list(judge.judge_stream(DESCRIPTION))
        self.assertEqual(retrieve.call_count, 2)
        self.assertTrue(all(call.kwargs['require_sources'] for call in retrieve.call_args_list))
        model.stream.assert_called_once()
        model.bind_tools.assert_not_called()
        self.assertEqual(get_model.call_args.kwargs['effort'], judge.IMAGE_JUDGE_REASONING)
        args = model.stream.call_args
        self.assertEqual(args.kwargs['options']['num_predict'], judge.IMAGE_JUDGE_MAX_TOKENS)
        self.assertEqual(args.kwargs['format'], 'json')
        self.assertIn('DECENCY CHECKLIST', args.args[0][1].content)
        self.assertIn('STRICT RULES', args.args[0][1].content)
        self.assertNotIn('You MUST call "asc_guidelines"', args.args[0][1].content)
        self.assertEqual(events[-1][0], 'answer')

    def test_truncated_judgment_never_becomes_verdict(self):
        model = Mock()
        model.stream.return_value = iter([AIMessageChunk(content='{"verdict":"COMPLIANT"}', response_metadata={'done_reason':'length'})])
        with patch('app.features.ad_review.judgment.get_judge', return_value=model), patch('app.features.ad_review.judgment.retrieve_guidelines', return_value='Passages'):
            with self.assertRaisesRegex(RuntimeError, 'no verdict was issued'):
                list(judge.judge_stream(DESCRIPTION))

    def test_vision_disables_supported_thinking_and_bounds_output(self):
        client = Mock()
        client.show.return_value.capabilities = ['vision', 'thinking']
        client.chat.return_value = [SimpleNamespace(done_reason=None, message=SimpleNamespace(content=DESCRIPTION))]
        with patch('app.infrastructure.ollama.vision.ollama.Client', return_value=client), patch.dict(vision._thinking_models, {}, clear=True):
            self.assertEqual(''.join(vision.describe_image(b'image')), DESCRIPTION)
        self.assertFalse(client.chat.call_args.kwargs['think'])
        self.assertEqual(client.chat.call_args.kwargs['options']['num_predict'], vision.VISION_MAX_TOKENS)

    def test_vision_without_thinking_and_truncation(self):
        client = Mock()
        client.show.return_value.capabilities = ['vision']
        client.chat.return_value = [SimpleNamespace(done_reason='length', message=SimpleNamespace(content='partial'))]
        with patch('app.infrastructure.ollama.vision.ollama.Client', return_value=client), patch.dict(vision._thinking_models, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'no verdict was issued'):
                list(vision.describe_image(b'image'))
        self.assertNotIn('think', client.chat.call_args.kwargs)

    def test_pipeline_keeps_verification_and_stage_timings(self):
        with patch('app.features.ad_review.service.describe_image', return_value=iter([DESCRIPTION])), patch('app.features.ad_review.service.judge_stream', return_value=iter([('answer','raw')])):
            with patch('app.features.ad_review.service.finalize', return_value={'result':'NON-COMPLIANT'}) as finalize, patch('app.features.ad_review.service.audit_judgment', return_value=[]):
                result = list(pipeline.check_image(b'image'))[-1][1]
        finalize.assert_called_once_with('raw', DESCRIPTION)
        self.assertEqual(set(result['timings']), {'describe','judge','verify'})


if __name__ == '__main__':
    unittest.main()
