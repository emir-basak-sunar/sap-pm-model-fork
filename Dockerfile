FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV HF_HOME=/app/huggingface_cache
ENV TRANSFORMERS_CACHE=/app/huggingface_cache
RUN python -c "from transformers import AutoTokenizer, AutoModel; AutoTokenizer.from_pretrained('dbmdz/bert-base-turkish-cased'); AutoModel.from_pretrained('dbmdz/bert-base-turkish-cased')"

RUN gdown "https://drive.google.com/uc?id=10vVlPhSEeExRuBnvNnOUGjp9vtTEUQFc" -O multi_task_bert_model.pth

COPY app.py .

RUN chmod -R 755 /app

EXPOSE 9000

CMD ["gunicorn", "app:app", "--timeout", "300", "--workers", "1", "--bind", "0.0.0.0:9000"]
