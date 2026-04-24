1. Migrated from Minio to Vercel blob storage for deploying, added code for creating a secure upload token that the frontend can use for directly uploading to blob store

2. ElasticSearch server coudn't be setup/run on a serverless setup and hence migrated to PostgreSQL ts-vector based searching (alternative for traditional keyword search - less accurate/fast compared to ES but deployment was a priority for me)

3. Generators experimented were Gemini, Claude and HuggingFace Llama3.2-7B. I decided to go with HF because Gemini Free tier is unreliable, Claude would rack up on costs long term.

4. Chat persistence was added using a new messages table for the LLM to have persistent context (last 6 messages).

5. Split up requirements into prod/dev requirements for a cleaner codebase. pyproject.toml was reuqired for configuring test paths and build setups on vercel.

6. Added LLM assisted gold-generation set for evaluating the RAG system. I chose haiku over Llama for better gold generation. RAGAS addition would be the next steps

7. PDF parser class was updated to only upload clean text chunks to DB for improving RAG system. Tiktoken offers better performance for splitting tokens 