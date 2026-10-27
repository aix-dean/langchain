import app.infrastructure.qdrant.store as store_adapter
import unittest
from unittest.mock import Mock, patch
from langchain_core.documents import Document
from langchain_core.messages import AIMessageChunk, HumanMessage
import app.features.guidelines.service as guidelines
import app.features.chat.reasoning as judge


class GuidelineRoutingTests(unittest.TestCase):
    def test_dispatch_and_citations(self):
        for tool, collection, authority in [('asc_guidelines', guidelines.COLLECTION, 'ASC'), ('macea_guidelines', 'macea_guidelines', 'MACEA')]:
            with patch('app.features.guidelines.service.search', return_value=[Document(page_content='Rule text', metadata={'source':'rules.pdf','page':4})]) as search:
                result = guidelines.retrieve_guidelines(tool, 'design rules')
            search.assert_called_once_with('design rules', collection=collection)
            self.assertIn(authority, result)
            self.assertIn('rules.pdf', result)
            self.assertIn('page: 4', result)

    def test_unavailable_and_empty(self):
        with patch('app.features.guidelines.service.search', side_effect=RuntimeError('missing collection')):
            result = guidelines.retrieve_guidelines('macea_guidelines', 'rules')
            self.assertIn('MACEA search unavailable', result)
            self.assertIn('Do not infer', result)
        with patch('app.features.guidelines.service.search', return_value=[]):
            self.assertIn('No passages found in MACEA', guidelines.retrieve_guidelines('macea_guidelines', 'rules'))
            with self.assertRaises(guidelines.GuidelineSourceUnavailable):
                guidelines.retrieve_guidelines('macea_guidelines', 'rules', require_sources=True)
        with patch('app.features.guidelines.service.search', side_effect=RuntimeError('missing collection')):
            with self.assertRaises(guidelines.GuidelineSourceUnavailable):
                guidelines.retrieve_guidelines('macea_guidelines', 'rules', require_sources=True)

    def test_same_text_distinct_authorities(self):
        seen=set()
        doc=Document(page_content='Same words',metadata={})
        self.assertNotIn('already shown', guidelines.format_passages([doc],seen,'ASC'))
        self.assertNotIn('already shown', guidelines.format_passages([doc],seen,'MACEA'))
        self.assertIn('already shown', guidelines.format_passages([doc],seen,'MACEA'))

    def run_loop(self, calls, limit=3):
        model=Mock()
        model.bind_tools.return_value=model
        model.stream.side_effect=[iter([AIMessageChunk(content='', tool_calls=calls)]), iter([AIMessageChunk(content='Final answer')])]
        messages=[HumanMessage('Use MACEA for this design'), HumanMessage('What size is required?')]
        with patch('app.features.chat.reasoning.get_judge',return_value=model), patch('app.features.chat.reasoning.model_capabilities',return_value={'tools'}), patch('app.features.chat.reasoning.retrieve_guidelines',return_value='Passages') as retrieve:
            events=list(judge.search_loop(messages,max_searches=limit))
        return model, retrieve, events

    def test_model_decision_dispatches_both_and_preserves_context(self):
        calls=[{'name':name,'args':{'query':'design requirements'},'id':str(i)} for i,name in enumerate(['macea_guidelines','asc_guidelines'])]
        model,retrieve,events=self.run_loop(calls)
        self.assertEqual([c.args[0] for c in retrieve.call_args_list],['macea_guidelines','asc_guidelines'])
        self.assertEqual([data['authority'] for kind,data in events if kind=='search'],['MACEA','ASC'])
        self.assertEqual([tool.name for tool in model.bind_tools.call_args.args[0]],['asc_guidelines','macea_guidelines'])
        messages=model.stream.call_args_list[0].args[0]
        self.assertIn('GUIDELINE SOURCE DECISION',messages[0].content)
        self.assertIn('Use MACEA',messages[1].content)

    def test_unknown_tools_and_search_limit(self):
        calls=[{'name':name,'args':{'query':'rules'},'id':str(i)} for i,name in enumerate(['unknown','macea_guidelines','asc_guidelines'])]
        _,retrieve,events=self.run_loop(calls,limit=1)
        self.assertEqual(retrieve.call_count,1)
        self.assertEqual(retrieve.call_args.args[0],'macea_guidelines')

    def test_collection_stores_are_separate(self):
        with patch.dict(store_adapter._stores, {}, clear=True), patch('app.infrastructure.qdrant.store.make_client'), patch('app.infrastructure.qdrant.store.make_embeddings'), patch('app.infrastructure.qdrant.store.QdrantVectorStore') as store:
            store.side_effect=[Mock(),Mock()]
            asc=store_adapter.get_store()
            macea=store_adapter.get_store('macea_guidelines')
            self.assertIsNot(asc,macea)
            self.assertIs(asc,store_adapter.get_store())
            self.assertEqual(store.call_args_list[1].kwargs['collection_name'],'macea_guidelines')


if __name__=='__main__':
    unittest.main()
