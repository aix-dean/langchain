"""Boundary and HTTP-contract checks for the feature-oriented backend."""
import ast
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import create_app
from app.core.config import ROOT


class ArchitectureTests(unittest.TestCase):
    def test_infrastructure_and_core_do_not_depend_on_features_or_http(self):
        for package in ('core', 'infrastructure'):
            for path in (ROOT / 'app' / package).rglob('*.py'):
                for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                    modules = [node.module or ''] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names] if isinstance(node, ast.Import) else []
                    for module in modules:
                        self.assertFalse(module.startswith(('app.features', 'app.api', 'app.main', 'fastapi')), f'{path}: {module}')

    def test_feature_logic_has_no_http_dependency(self):
        for path in (ROOT / 'app' / 'features').rglob('*.py'):
            if path.name in ('routes.py', 'uploads.py'):
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or '').startswith(('fastapi', 'app.api')), str(path))

    def test_models_only_warm_during_enabled_lifespan(self):
        ready = threading.Event()
        with patch('app.bootstrap.get_ready', side_effect=ready.set) as warm:
            application = create_app(warm_models=False)
            warm.assert_not_called()
            with TestClient(application) as client:
                self.assertEqual(client.get('/').status_code, 200)
            warm.assert_not_called()
            with TestClient(create_app()) as client:
                self.assertTrue(ready.wait(2))
            warm.assert_called_once_with()

    def test_api_routes_keep_existing_stream_and_report_contracts(self):
        with TestClient(create_app(warm_models=False)) as client:
            response = client.post('/api/chat', data={'message': 'Hello', 'history': '[]'})
            events = [json.loads(line) for line in response.text.splitlines()]
            self.assertEqual(response.status_code, 200)
            self.assertEqual(events[-1], {'type': 'done'})
            self.assertEqual(events[0]['type'], 'token')
            self.assertEqual(client.post('/api/chat', data={'message': ''}).status_code, 400)
            with patch('app.features.ad_review.routes.check_image', return_value=iter([('stage', 'describe'), ('result', {'result': 'NEEDS_REVIEW'})])):
                response = client.post('/api/check', files={'image': ('ad.png', b'fake')})
                self.assertIn('application/x-ndjson', response.headers['content-type'])
                events = [json.loads(line) for line in response.text.splitlines()]
                self.assertEqual(events[-2]['result'], 'NEEDS_REVIEW')
                self.assertEqual(events[-1]['type'], 'done')
            with patch('app.features.reports.routes.build_report', return_value=b'%PDF-test'):
                response = client.post('/api/report', files={'image': ('ad.png', b'fake')}, data={'data': '{"result":{},"decision":"Revise"}'})
                self.assertEqual(response.content, b'%PDF-test')
                self.assertEqual(response.headers['content-type'], 'application/pdf')
                self.assertIn('attachment;', response.headers['content-disposition'])

    def test_resource_paths_remain_at_project_root(self):
        self.assertTrue((ROOT / '.env.example').exists())
        self.assertTrue((ROOT / 'prompts' / 'judge.md').is_file())
        self.assertTrue((ROOT / 'static' / 'index.html').is_file())


if __name__ == '__main__':
    unittest.main()
