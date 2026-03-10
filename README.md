# RAG-PDF-Hybrid-Semantic-Search-and-LLM-Question-Answering
Built an AI system for intelligent PDF retrieval and question answering by combining embedding-based semantic search (FAISS), keyword search (Elasticsearch), and a retrieval-augmented LLM (Gemini) to provide accurate, context-aware answers from large document collections.


## Steps

- Run the docker-compose file to start the API server, ElasticSearch search engine and MinIO object store
```bash
docker compose up --build -d
```
