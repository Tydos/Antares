FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

# Install dependencies and pre-download the sentence transformer model weights 
RUN pip install --no-cache-dir -r requirements.txt \
 && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]