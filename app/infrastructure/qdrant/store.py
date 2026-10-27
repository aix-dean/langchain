from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from app.core.config import COLLECTION, EMBEDDING_MODEL, QDRANT_API_KEY, QDRANT_URL, TOP_K
from app.infrastructure.ollama.embeddings import embedding_url

_stores = {}

def make_client():  # Connection to the Qdrant server (the same one n8n uses)
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)  # e.g. http://localhost:6333


def make_embeddings():  # The model that turns text into vectors
    return OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=embedding_url(), keep_alive=-1)  # Plain nomic-embed-text, exactly as n8n stored the passages; on the processor-only Ollama copy so it never unloads the judge


def get_store(collection=COLLECTION):
    if collection not in _stores:
        _stores[collection] = QdrantVectorStore(  # Connect to the collection
            client=make_client(),  # The Qdrant server
            collection_name=collection,
            embedding=make_embeddings(),  # How search text becomes vectors
            content_payload_key="content",  # n8n saves each passage's text under "content"
            metadata_payload_key="metadata",  # ...and its details under "metadata"
        )  # End of connection
    return _stores[collection]


def search(query, k=TOP_K, collection=COLLECTION):
    return get_store(collection).similarity_search(query, k=k)


def passage_count():  # How many passages the collection holds (shown in the status panel)
    store = get_store()  # The collection
    return store.client.count(COLLECTION).count  # Number of stored passages
