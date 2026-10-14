# Firebird MCP Server 🔥

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![MCP Standard](https://img.shields.io/badge/MCP-2024--11--05-green.svg)](https://modelcontextprotocol.io)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Firebird 2.5 to 5.0](https://img.shields.io/badge/Firebird-2.5%20%7C%203.0%20%7C%204.0%20%7C%205.0-red.svg)](https://www.firebirdsql.org)

> 🌐 **Language / Idioma:** [English](README.md) | **Português (Brasil)**

Servidor open-source de **Model Context Protocol (MCP)** para banco de dados **Firebird**, desenvolvido para uso livre pela comunidade e com suporte a todas as versões principais (**Firebird 2.5, 3.0, 4.0 e 5.0**).

Projetado de acordo com os **padrões abertos da indústria de servidores MCP (stdio / JSON-RPC 2.0)**, garantindo compatibilidade imediata com **qualquer IDE ou cliente de IA**: **Google Antigravity IDE**, **Cursor**, **Claude Desktop**, **VS Code (com extensões Cline / Roo Code)**, **Windsurf**, **Zed** e ferramentas CLI.

---

## 🎯 Por que este MCP é Único?

1. **Protocolo Nativo Wire (Zero Dependência de DLLs)**:
   - Comunica diretamente pela porta TCP (padrão 3050) usando Python puro (`firebirdsql`).
   - Não depende da compilação de binários em C/C++, dispensando a instalação de `fbclient.dll` (Windows) ou `libfbclient.so` (Linux) na máquina do agente ou da IDE.
   - Suporta desde a autenticação clássica do FB 2.5 (`Legacy_Auth`) até a autenticação moderna plugável SRP do FB 3.0, 4.0 e 5.0.
2. **Suporte a Múltiplos Bancos por Projeto**:
   - Permite que um mesmo projeto utilize múltiplos bancos de dados (ex: `principal`, `auditoria`, `homologacao`), com alternância fluida via chat ou por comando.
3. **Auto-Discovery por Projeto (`.firebird-mcp.json`)**:
   - Detecta automaticamente o arquivo de configuração do banco na raiz do projeto onde você está trabalhando.
4. **Análise de Performance e Planos (`PLAN`)**:
   - Compila consultas sem precisar trafegar datasets inteiros, identificando leituras sequenciais (`NATURAL SCAN`) e ordenações pesadas (`SORT`).
5. **Segurança Estrita de Leitura e MVCC**:
   - `fb_query` é restrito a leitura (`SELECT`), prevenindo alterações destrutivas acidentais.
   - Encerra transações imediatamente após a leitura, eliminando o risco de prender o **OAT (*Oldest Active Transaction*)** e inchar o arquivo `.fdb`.
6. **Mapeamento Abrangente de Catálogo do Sistema**:
   - Suporte completo aos metadados do catálogo de sistema `RDB$`, incluindo tipos modernos: `BOOLEAN` (FB3+), `INT128`, `DECFLOAT(16/34)`, `TIMESTAMP WITH TIME ZONE` (FB4+), `BLOB SUB_TYPE TEXT/BINARY` e seletividade de índices (`RDB$STATISTICS`).

---

## 🗄️ Configuração por Projeto e Múltiplos Bancos

Em projetos reais (como ERPs e sistemas corporativos em Delphi, Laravel ou Python), é comum ter:
- Bancos diferentes por projeto (cada workspace tem sua base).
- Múltiplos bancos dentro do mesmo projeto (ex: base de dados operacional `ERP.FDB` e base de auditoria `LOGS.FDB`).

### Como Funciona o Auto-Discovery:
O servidor MCP procura automaticamente pelo arquivo `.firebird-mcp.json` na raiz do seu projeto (ou subindo a árvore de diretórios até a raiz do workspace).

Crie um arquivo `.firebird-mcp.json` na raiz do seu repositório:

```json
{
  "default": "principal",
  "databases": {
    "principal": {
      "host": "localhost",
      "port": 3050,
      "database": "/var/dados/ERP_DADOS.FDB",
      "user": "SYSDBA",
      "password": "masterkey",
      "charset": "WIN1252",
      "description": "Banco de dados operacional principal"
    },
    "auditoria": {
      "host": "localhost",
      "port": 3050,
      "database": "/var/dados/ERP_AUDITORIA.FDB",
      "user": "SYSDBA",
      "password": "masterkey",
      "charset": "WIN1252",
      "description": "Banco de dados de logs e auditoria"
    },
    "homolog": {
      "host": "192.168.1.50",
      "port": 3050,
      "database": "D:\\dados\\HOMOLOG.FDB",
      "user": "SYSDBA",
      "password": "masterkey",
      "charset": "WIN1252",
      "description": "Base de testes/homologação"
    }
  }
}
```

> **Dica de Segurança:** Adicione `.firebird-mcp.json` ao seu `.gitignore` caso utilize senhas reais de ambientes sensíveis, disponibilizando um `.firebird-mcp.example.json` no repositório.

### Como o Agente Interage com Múltiplos Bancos:
- **Consultar banco específico:** Todas as ferramentas aceitam o parâmetro `db_alias` (ex: `fb_query(sql="SELECT * FROM LOGS", db_alias="auditoria")`).
- **Listar bancos disponíveis:** A ferramenta `fb_list_databases()` lista todos os apelidos configurados e qual é o ativo.
- **Alternar o banco ativo:** A ferramenta `fb_use_database("auditoria")` define o banco padrão para todas as chamadas seguintes.
- **Adicionar banco dinamicamente:** `fb_configure_database(...)` permite cadastrar um banco via chat sem reiniciar a IDE.

---

## 🛠️ Ferramentas (MCP Tools) Disponíveis

### Gerenciamento de Conexões e Bancos
| Ferramenta | Parâmetros | Descrição |
| :--- | :--- | :--- |
| `fb_list_databases` | *Nenhum* | Lista todos os bancos configurados no projeto, o arquivo `.firebird-mcp.json` ativo e o banco default. |
| `fb_use_database` | `alias` | Alterna o banco padrão da sessão para o apelido informado. |
| `fb_configure_database` | `alias`, `database`, `host`, `port`, `user`, `password`, `charset`, `set_as_default` | Cadastra ou altera uma conexão em tempo de execução. |
| `fb_reload_config` | `config_path` *(opcional)* | Recarrega o arquivo `.firebird-mcp.json` do projeto. |

### Inspeção e Metadados
| Ferramenta | Parâmetros | Descrição |
| :--- | :--- | :--- |
| `fb_list_tables` | `db_alias` *(opcional)* | Lista todas as tabelas de usuário (ignora tabelas de sistema `RDB$`). |
| `fb_list_views` | `db_alias` *(opcional)* | Lista todas as views de usuário cadastradas. |
| `fb_list_procedures` | `db_alias` *(opcional)* | Lista todas as Stored Procedures cadastradas no banco. |
| `fb_list_generators` | `db_alias` *(opcional)* | Lista todos os Generators / Sequences de usuário. |
| `fb_inspect_table` | `table_name`, `db_alias` *(opcional)* | Retorna colunas, tipos precisos, PK, FKs e índices com taxa de seletividade real (`RDB$STATISTICS`). |

### Análise de Performance e Execução
| Ferramenta | Parâmetros | Descrição |
| :--- | :--- | :--- |
| `fb_explain_plan` | `sql`, `db_alias` *(opcional)* | Compila a query no Firebird, extrai o `PLAN`, detecta `NATURAL SCAN` em tabelas e orienta sobre índices. |
| `fb_query` | `sql`, `limit` (padrão 50, máx 1000), `db_alias` *(opcional)* | Executa consulta `SELECT` com leitura segura e commit imediato. |
| `fb_execute_dml` | `sql`, `db_alias` *(opcional)* | Executa comandos `INSERT`, `UPDATE`, `DELETE` ou `EXECUTE PROCEDURE` com encerramento de transação. |
| `fb_execute_ddl` | `ddl`, `db_alias` *(opcional)* | Executa comandos de definição estrutural (`CREATE INDEX`, `ALTER TABLE`, etc.) com commit explícito. |
| `fb_database_health` | `db_alias` *(opcional)* | Diagnostica a saúde do banco via tabelas `MON$` (ODS, page size e gap entre OAT e Next Transaction). |

---

## 💻 Instalação e Execução

### 🐳 Opção 1: Docker (Padrão Ouro — Recomendado para Windows, macOS e Linux)
Rodar via Docker elimina a necessidade de instalar Python, pip ou dependências na máquina:

```bash
# Clone e faça o build da imagem localmente:
git clone https://github.com/lucasgabriel0802/firebird-mcp.git
cd firebird-mcp
docker build -t firebird-mcp:latest .
```

#### Configuração Universal na IDE via Docker (Modo Stdio):
Configure sua IDE para iniciar o container sob demanda. Esta configuração funciona de forma idêntica e sem ajustes no **Windows, macOS e Linux**:

```json
{
  "mcpServers": {
    "firebird": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v", "${workspaceFolder}:/workspace",
        "-w", "/workspace",
        "--add-host", "host.docker.internal:host-gateway",
        "firebird-mcp:latest"
      ]
    }
  }
}
```

> **Por que este é o Padrão Ouro?**
> - `-i`: Mantém o fluxo stdin/stdout aberto para o JSON-RPC sem alocar pseudo-TTY (sem `-t` para não corromper mensagens).
> - `--rm`: Destrói o container automaticamente quando a IDE fecha o chat.
> - `-v "${workspaceFolder}:/workspace"`: Monta a pasta do seu projeto para leitura automática do `.firebird-mcp.json`.
> - `--add-host host.docker.internal:host-gateway`: Permite que o container acerte o IP do seu host (ex: Firebird rodando na porta 3050 no Windows, Linux ou Mac) usando `host.docker.internal`.

---

### 🚀 Opção 2: Docker Compose (Serviço em Segundo Plano e Banco de Teste)

#### A. Rodar como Serviço HTTP/SSE Contínuo
Se preferir deixar o servidor MCP rodando em segundo plano na porta `8000`:

```bash
docker compose up -d firebird-mcp
```
Conecte sua IDE apontando para a URL SSE: `http://localhost:8000/sse`.

#### B. Ambiente de Testes Completo (com Banco Firebird 5.0 incluso)
Suba simultaneamente o servidor MCP e um container com o Firebird 5.0 pronto para testes:

```bash
docker compose --profile test-db up -d
```
Isso inicializa:
- Banco Firebird 5.0 em `localhost:3050` (senha: `masterkey`, banco: `TESTE.FDB`).
- Servidor MCP Firebird em `http://localhost:8000/sse`.

---

### 🐍 Opção 3: Ambiente Virtual Python Local

```bash
git clone https://github.com/lucasgabriel0802/firebird-mcp.git ~/firebird-mcp
cd ~/firebird-mcp
python3 -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

---

## ⚙️ Configuração Universal em Qualquer IDE

### 1. Google Antigravity IDE
No arquivo global `~/.gemini/config/mcp_config.json` (ou no workspace):

**Via Docker (Recomendado):**
```json
{
  "mcpServers": {
    "firebird": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v", "${workspaceFolder}:/workspace",
        "-w", "/workspace",
        "--add-host", "host.docker.internal:host-gateway",
        "firebird-mcp:latest"
      ]
    }
  }
}
```

**Ou via Python Local:**
```json
{
  "mcpServers": {
    "firebird": {
      "command": "/home/lucas/firebird-mcp/venv/bin/python",
      "args": ["-m", "firebird_mcp.server"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

---

### 2. Cursor
No arquivo `.cursor/mcp.json` na raiz do seu projeto ou em **Settings > Features > MCP**:

```json
{
  "mcpServers": {
    "firebird": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v", "${workspaceFolder}:/workspace",
        "-w", "/workspace",
        "--add-host", "host.docker.internal:host-gateway",
        "firebird-mcp:latest"
      ]
    }
  }
}
```

---

### 3. VS Code (com Cline / Roo Code / Copilot MCP)
No `cline_mcp_settings.json` ou nas configurações do Roo Code:

```json
{
  "mcpServers": {
    "firebird": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v", "${workspaceFolder}:/workspace",
        "-w", "/workspace",
        "--add-host", "host.docker.internal:host-gateway",
        "firebird-mcp:latest"
      ]
    }
  }
}
```

---

### 4. Claude Desktop
No arquivo `claude_desktop_config.json`:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "firebird": {
      "command": "python",
      "args": ["-m", "firebird_mcp.server", "--config", "C:\\meu_projeto\\.firebird-mcp.json"],
      "cwd": "C:\\meu_projeto"
    }
  }
}
```

---

### 5. Windsurf
No arquivo `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "firebird": {
      "command": "python3",
      "args": ["-m", "firebird_mcp.server"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

---

### 6. Zed Editor
No `settings.json` do Zed:

```json
{
  "context_servers": {
    "firebird": {
      "command": {
        "path": "python3",
        "args": ["-m", "firebird_mcp.server"]
      }
    }
  }
}
```

---

## 🧠 Sinergia: Skill `firebird-master` + `firebird-mcp`

Este servidor MCP forma uma **dupla imbatível** com a skill [`firebird-master`](https://github.com/lucasgabriel0802/my-agent-skills/tree/main/skills/firebird-master):

```
┌────────────────────────────────────────────────────────┐
│            AGENTE DE IA / COPILOT                      │
├──────────────────────────┬─────────────────────────────┤
│   SKILL firebird-master  │     MCP firebird-mcp        │
│        (Cérebro)         │         (Músculo)           │
├──────────────────────────┼─────────────────────────────┤
│ • Regras de versão       │ • Conecta via TCP (wire)    │
│   (FB 2.5 vs 3 vs 4 vs 5)│ • Executa e obtém PLAN real │
│ • Diagnóstico de queries │ • Inspeciona tabelas RDB$   │
│ • Heurísticas de índice  │ • Coleta OAT/OIT de MON$    │
│ • Padrões Delphi FireDAC │ • Auto-discovery do projeto │
└──────────────────────────┴─────────────────────────────┘
```

---

## ⚖️ Isenção de Responsabilidade (Disclaimer) e Marcas

Este é um projeto independente de código aberto e uso livre pela comunidade, distribuído sob a licença MIT. Não possui vínculo, afiliação, patrocínio, homologação ou endosso oficial com o Projeto Firebird ou com a Firebird Foundation. "Firebird" é uma marca registrada da Firebird Foundation.

---

## 📄 Licença
Distribuído sob a licença [MIT](LICENSE).
