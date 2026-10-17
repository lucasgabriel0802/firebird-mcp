# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Metadados
LABEL maintainer="Lucas Gabriel dos Santos"
LABEL description="Open-source Model Context Protocol (MCP) Server for Firebird Database"
LABEL io.modelcontextprotocol.server.name="io.github.lucasgabriel0802/firebird-mcp"

# Variáveis essenciais para execução Python e MCP
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MCP_TRANSPORT=stdio \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

# Diretório de trabalho da aplicação
WORKDIR /app

# Instala dependências em camada cacheável
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código fonte do servidor MCP
COPY firebird_mcp/ ./firebird_mcp/
COPY README.md LICENSE ./

# Instala o pacote em modo de produção
RUN pip install --no-cache-dir .

# Cria diretório padrão para montagem de workspaces
RUN mkdir -p /workspace && chmod 777 /workspace
WORKDIR /workspace

# Porta padrão para o modo SSE / HTTP (opcional)
EXPOSE 8000

# Entrypoint executável padrão do MCP
ENTRYPOINT ["python", "-m", "firebird_mcp.server"]

# Por padrão roda em modo stdio (ideal para IDEs via docker run -i --rm)
CMD ["--transport", "stdio"]
