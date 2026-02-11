FROM python:3.11-slim
RUN apt-get update && apt-get install -y \
    mecab libmecab-dev mecab-ipadic-utf8 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /etc/mecabrc /usr/local/etc/mecabrc
RUN pip install --no-cache-dir fastapi uvicorn mecab-python3
WORKDIR /app
COPY . /app/
EXPOSE 8080
CMD ["sh", "-c", "python build_index.py && uvicorn main:app --host 0.0.0.0 --port 8080"]
