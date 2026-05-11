FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY agents /app/agents
COPY mcp_servers /app/mcp_servers

EXPOSE 8102
ENV PORT=8102
CMD ["python", "-m", "mcp_servers.search_mcp.server"]
