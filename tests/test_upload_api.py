import sys
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient


class UploadApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch('threading.Thread.start'):
            import server
        from app.features.documents import routes as documents
        cls.server=documents
        cls.client=TestClient(server.app)

    def test_pages_and_validation(self):
        self.assertIn('Upload documents',self.client.get('/').text)
        self.assertIn('Replace existing document',self.client.get('/upload').text)
        self.assertEqual(self.client.post('/api/documents',files={'file':('bad.exe',b'text')}).status_code,400)
        self.assertEqual(self.client.post('/api/documents',files={'file':('empty.txt',b'')}).status_code,400)
        with patch('app.features.documents.service.MAX_DOCUMENT_MB',0):
            self.assertEqual(self.client.post('/api/documents',files={'file':('big.txt',b'text')}).status_code,400)

    def test_stream_and_replace(self):
        def fake(data,name,replace,collection):
            self.assertEqual(collection,"macea_guidelines")
            self.assertEqual(data,b'hello')
            self.assertEqual(name,'rules.txt')
            self.assertTrue(replace)
            yield {'type':'done','filename':name,'passages':1,'replaced':True}
        with patch.object(self.server,'ingest_document',side_effect=fake):
            response=self.client.post('/api/documents',files={'file':('rules.txt',b'hello')},data={'replace':'true'})
        self.assertEqual(response.status_code,200)
        self.assertIn('"type": "done"',response.text)

    def test_service_error(self):
        with patch.object(self.server,'ingest_document',side_effect=RuntimeError('Qdrant unavailable')):
            response=self.client.post('/api/documents',files={'file':('rules.txt',b'hello')})
        self.assertIn('"type": "error"',response.text)
        self.assertIn('Qdrant unavailable',response.text)


if __name__=='__main__':
    unittest.main()
