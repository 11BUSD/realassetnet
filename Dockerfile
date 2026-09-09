# LOCAL SYNTHETIC DEMO ONLY. This stdlib HTTP server is not a production ingress.
FROM python:3.12-slim
WORKDIR /opt/realassetnet
COPY app ./app
COPY web ./web
COPY migrations ./migrations
COPY fixtures ./fixtures
COPY server.py ./server.py
RUN groupadd --gid 10001 ran && useradd --uid 10001 --gid ran --no-create-home ran && mkdir runtime && chown ran:ran runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RAN_MODE=simulation RAN_DB=runtime/app.sqlite
USER ran
EXPOSE 8080
CMD ["python", "server.py", "--seed-demo", "--bind", "0.0.0.0", "--port", "8080"]
