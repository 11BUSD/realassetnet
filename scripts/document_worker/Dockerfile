FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils && rm -rf /var/lib/apt/lists/*
COPY worker.py /worker.py
USER 65534:65534
ENTRYPOINT ["python","-I","/worker.py"]
