# Firebird MCP Server 🔥

Servidor **Model Context Protocol (MCP)** para banco de dados **Firebird**, com suporte completo a todas as versões (**Firebird 2.5, 3.0, 4.0 e 5.0**).

Projetado especialmente para integração com o **Google Antigravity IDE**, Claude Desktop e outros agentes de IA, atuando em conjunto com a skill [`firebird-master`](https://github.com/lucasgabriel0802/my-agent-skills).

---

## 🚀 Recursos Principais

- **Compatibilidade Ampla (FB 2.5 a 5.0)**: Comunicação via protocolo de rede nativo em Python puro (`firebirdsql`), sem necessidade de compilar DLLs C/C++ ou instalar `fbclient.dll` no ambiente do agente.
- **Análise Inteligente de Planos (`PLAN`)**: Compila a query no engine do Firebird e extrai o plano de execução oficial, detectando automaticamente leituras sequenciais (`NATURAL SCAN`), ordenações desnecessárias (`SORT`) e recomendando índices.
- **Introspecção de Metadados (`RDB$`)**: Inspeciona colunas, tipos de dados, chaves primárias (PK), chaves estrangeiras (FK) e índices com suas respectivas taxas de seletividade (`RDB$STATISTICS`).
- **Telemetria e Diagnóstico de Inchaço (`MON$`)**: Monitora o gap entre **OAT** (*Oldest Active Transaction*) e *Next Transaction*, prevenindo a degradação de Garbage Collection e o inchaço do arquivo `.fdb`.
- **Execução Segura**: Executa consultas `SELECT` com limite configurável de linhas e commit imediato de transações de leitura, evitando bloqueios fantasmas no banco.

---

## 🛠️ Ferramentas (MCP Tools) Disponíveis

| Ferramenta | Descrição |
| :--- | :--- |
| `fb_explain_plan` | Compila um comando SQL, extrai o `PLAN` real, detecta `NATURAL SCAN` e sugere melhorias de indexação. |
| `fb_inspect_table` | Inspeciona colunas, domínios, constraints (PK/FK) e índices com seletividade (`RDB$STATISTICS`). |
| `fb_list_tables` | Lista todas as tabelas de usuário (ignora tabelas de sistema `RDB$`). |
| `fb_list_views` | Lista todas as views de usuário cadastradas no banco. |
| `fb_query` | Executa consultas SELECT de leitura com limite de linhas e encerramento imediato de transação. |
| `fb_execute_ddl` | Executa comandos DDL (`CREATE INDEX`, `ALTER TABLE`, etc.) com transação e commit explícito. |
| `fb_database_health` | Diagnostica a saúde do banco via tabelas `MON$` (versão, ODS, page size e gap OAT/OIT). |
| `fb_configure_connection` | Altera os parâmetros de conexão em tempo de execução (host, porta, banco, usuário, senha, charset). |
| `fb_connection_status` | Testa e exibe o status da conexão ativa com o Firebird. |

---

## 📦 Instalação

### 1. Clonar o repositório
```bash
git clone https://github.com/lucasgabriel0802/firebird-mcp.git ~/firebird-mcp
cd ~/firebird-mcp
```

### 2. Criar ambiente virtual e instalar dependências
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

---

## ⚙️ Configuração no Antigravity IDE

Adicione o servidor no seu arquivo de configuração MCP (`~/.gemini/config/mcp_config.json` ou nas configurações do seu workspace):

```json
{
  "mcpServers": {
    "firebird": {
      "command": "/home/lucas/firebird-mcp/venv/bin/python",
      "args": ["-m", "firebird_mcp.server"],
      "env": {
        "FIREBIRD_HOST": "localhost",
        "FIREBIRD_PORT": "3050",
        "FIREBIRD_DATABASE": "/caminho/para/seu/banco.fdb",
        "FIREBIRD_USER": "SYSDBA",
        "FIREBIRD_PASSWORD": "masterkey",
        "FIREBIRD_CHARSET": "WIN1252"
      }
    }
  }
}
```

### No Windows:
```json
{
  "mcpServers": {
    "firebird": {
      "command": "python",
      "args": ["-m", "firebird_mcp.server"],
      "cwd": "C:\\Users\\lucas\\firebird-mcp",
      "env": {
        "FIREBIRD_HOST": "localhost",
        "FIREBIRD_PORT": "3050",
        "FIREBIRD_DATABASE": "C:\\sistemas\\dados\\BANCO.FDB",
        "FIREBIRD_USER": "SYSDBA",
        "FIREBIRD_PASSWORD": "masterkey",
        "FIREBIRD_CHARSET": "WIN1252"
      }
    }
  }
}
```

---

## 🧠 Sinergia com a Skill `firebird-master`

Este MCP atua como os **braços** da IA, enquanto a skill [`firebird-master`](file:///home/lucas/my-agent-skills/skills/firebird-master/SKILL.md) atua como o **cérebro**:
1. A **Skill** sabe identificar anti-padrões conceituais, diferenças de versão (FB 2.5 vs 3.0 vs 4.0 vs 5.0) e boas práticas em código Delphi (FireDAC).
2. O **MCP** conecta no banco ativo para extrair a prova real: planos de execução com dados estatísticos e metadados dinâmicos.

---

## 📄 Licença
MIT
