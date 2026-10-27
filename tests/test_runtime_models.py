import unittest
from unittest.mock import Mock, patch

import app.infrastructure.ollama.embeddings as embed_server
import app.infrastructure.ollama.models as judge


class RuntimeModelTests(unittest.TestCase):
    def test_off_sends_false_for_qwen(self):
        with patch('app.infrastructure.ollama.models.model_capabilities', return_value={'thinking'}), patch('app.infrastructure.ollama.models.JUDGE_MODEL', 'qwen3.5:9b'):
            for effort in ('off', 'false', '0', 'OFF'):
                self.assertIs(judge.thinking_setting(effort), False)
            self.assertIs(judge.get_judge(effort='off').reasoning, False)

    def test_models_without_thinking_do_not_receive_control(self):
        with patch('app.infrastructure.ollama.models.model_capabilities', return_value=set()):
            self.assertIsNone(judge.thinking_setting('off'))

    def test_health_check_uses_supported_list_api(self):
        client = Mock(spec=['list'])
        with patch('app.infrastructure.ollama.embeddings.ollama.Client', return_value=client):
            self.assertTrue(embed_server._reachable('http://127.0.0.1:11435'))
        client.list.assert_called_once_with()

    def test_health_check_rejects_unavailable_service(self):
        client = Mock(spec=['list'])
        client.list.side_effect = ConnectionError('offline')
        with patch('app.infrastructure.ollama.embeddings.ollama.Client', return_value=client):
            self.assertFalse(embed_server._reachable('http://127.0.0.1:11435'))


if __name__ == '__main__':
    unittest.main()
