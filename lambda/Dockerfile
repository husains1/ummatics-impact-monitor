# Dockerfile for Lambda container with transformer model

FROM public.ecr.aws/lambda/python:3.11

# Set cache to /tmp before any downloads
ENV TRANSFORMERS_CACHE=/tmp/transformers_cache
ENV HF_HOME=/tmp/hf_home

# Install transformers and torch (CPU-only for cost savings)
COPY requirements-transformer.txt .
# Use pre-built wheels to avoid compilation - numpy binary wheel available
RUN pip install --no-cache-dir --only-binary :all: -r requirements-transformer.txt

# Pre-download the model into the container image (faster cold starts, no runtime download)
RUN mkdir -p /opt/ml/model && \
    python -c "from transformers import pipeline; \
    p = pipeline('sentiment-analysis', model='distilbert-base-uncased-finetuned-sst-2-english', model_kwargs={'cache_dir': '/opt/ml/model'})"

# Copy function code
COPY sentiment_function.py ${LAMBDA_TASK_ROOT}/

# Set handler
CMD [ "sentiment_function.lambda_handler" ]
