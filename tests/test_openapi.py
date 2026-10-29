"""Documentation must describe actual multipart, streaming and PDF contracts."""
import json
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app


class OpenApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app(warm_models=False))
        cls.schema = cls.client.get('/openapi.json').json()

    def test_swagger_uses_local_assets_and_disables_external_validator(self):
        response = self.client.get('/docs')
        self.assertEqual(response.status_code, 200)
        self.assertIn('/docs-assets/swagger-ui-bundle.js', response.text)
        self.assertIn('/docs-assets/swagger-ui.css', response.text)
        self.assertNotIn('cdn.jsdelivr.net', response.text)
        self.assertIn('"validatorUrl": null', response.text)
        self.assertEqual(self.client.get('/docs-assets/swagger-ui.css').status_code, 200)
        self.assertEqual(self.client.get('/docs-assets/swagger-ui-bundle.js').status_code, 200)

    def test_paths_are_documented_with_summaries_and_stable_ids(self):
        expected = {'/api/chat', '/api/check', '/api/documents', '/api/report', '/api/status', '/api/macea'}
        self.assertEqual(set(self.schema['paths']), expected)
        identifiers = []
        for path in self.schema['paths'].values():
            operation = next(iter(path.values()))
            self.assertTrue(operation['summary'])
            self.assertTrue(operation['description'])
            identifiers.append(operation['operationId'])
        self.assertEqual(len(set(identifiers)), len(expected))

    def test_stream_examples_are_valid_ndjson_and_not_documented_as_json(self):
        for path in ('/api/chat', '/api/check', '/api/documents'):
            response = self.schema['paths'][path]['post']['responses']['200']
            self.assertEqual(set(response['content']), {'application/x-ndjson'})
            media = response['content']['application/x-ndjson']
            self.assertEqual(media['schema']['type'], 'string')
            events = [json.loads(line) for line in media['example'].splitlines()]
            self.assertEqual(events[-1]['type'], 'done')
            self.assertIn('400', self.schema['paths'][path]['post']['responses'])
        self.assertIn('409', self.schema['paths']['/api/chat']['post']['responses'])

    def test_upload_fields_are_documented_as_multipart(self):
        for path in ('/api/chat', '/api/check', '/api/documents', '/api/report'):
            body = self.schema['paths'][path]['post']['requestBody']['content']
            ref = body['multipart/form-data']['schema']['$ref'].split('/')[-1]
            properties = self.schema['components']['schemas'][ref]['properties']
            for field in properties.values():
                self.assertTrue(field.get('description'))
        report = self.schema['paths']['/api/report']['post']['responses']['200']
        self.assertEqual(set(report['content']), {'application/pdf'})
        self.assertEqual(report['content']['application/pdf']['schema']['format'], 'binary')
        self.assertIn('Content-Disposition', report['headers'])

    def test_status_response_model_preserves_existing_fields(self):
        sample = dict(vision_model='qwen3.5:9b', judge_model='qwen3.5:9b', embedding_model='nomic-embed-text', collection='asc_guidelines', ollama=True, missing_models=[], qdrant=True, passages=438, judge_tools=True, device='GPU', busy=False, active_jobs=0, queued_jobs=0, max_concurrent_jobs=2, context_limit_chars=17094, context_limit_tokens=4884)
        # The route retains the original function object; patch its adapters instead.
        with patch('app.features.status.service.ollama.Client') as client, patch('app.features.status.service.passage_count', return_value=438), patch('app.features.status.service.model_capabilities', return_value={'tools'}):
            client.return_value.list.return_value.models = []
            client.return_value.ps.return_value.models = []
            response = self.client.get('/api/status')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), set(sample))
        ref = self.schema['paths']['/api/status']['get']['responses']['200']['content']['application/json']['schema']['$ref']
        model = self.schema['components']['schemas'][ref.split('/')[-1]]
        self.assertEqual(set(model['properties']), set(sample))


if __name__ == '__main__':
    unittest.main()
