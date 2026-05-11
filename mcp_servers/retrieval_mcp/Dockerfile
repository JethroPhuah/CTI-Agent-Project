FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY agents /app/agents
COPY databases /app/databases
COPY ingestion /app/ingestion
COPY mcp_servers /app/mcp_servers

EXPOSE 8101
ENV PORT=8101
CMD ["python", "-m", "mcp_servers.retrieval_mcp.server"]
