# Firebird MCP Server 🔥

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![MCP Standard](https://img.shields.io/badge/MCP-2024--11--05-green.svg)](https://modelcontextprotocol.io)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Firebird 2.5 to 5.0](https://img.shields.io/badge/Firebird-2.5%20%7C%203.0%20%7C%204.0%20%7C%205.0-red.svg)](https://www.firebirdsql.org)

> 🌐 **Language / Idioma:** **English** | [Português (Brasil)](README.pt-BR.md)

Official **Model Context Protocol (MCP)** server for **Firebird Database**, providing native support for all major releases (**Firebird 2.5, 3.0, 4.0, and 5.0**).

Built according to the **open industry standards for MCP servers (stdio / JSON-RPC 2.0)**, ensuring turnkey compatibility with **any AI client or IDE**: **Google Antigravity IDE**, **Cursor**, **Claude Desktop**, **VS Code (with Cline / Roo Code / Copilot extensions)**, **Windsurf**, **Zed**, and CLI tools.

---

## 🎯 Key Highlights

1. **Pure Python Wire Protocol (Zero DLL Dependencies)**:
   - Connects directly over TCP (default port `3050`) using pure Python (`firebirdsql`).
   - Requires no native C/C++ compilation and eliminates the need to install `fbclient.dll` (Windows) or `libfbclient.so` (Linux) on the host running the AI client or IDE.
   - Fully compatible with legacy authentication (`Legacy_Auth` in FB 2.5) as well as modern pluggable SRP authentication in FB 3.0, 4.0, and 5.0.
2. **Multi-Database Support per Project**:
   - Allows a single project workspace to declare and manage multiple databases (e.g., `main`, `audit_logs`, `staging`), switching dynamically via chat prompts or tool arguments.
3. **Workspace Auto-Discovery (`.firebird-mcp.json`)**:
   - Automatically detects database configuration files placed at the root of your project or repository.
4. **Execution Plan & Performance Analysis (`PLAN`)**:
   - Compiles queries to extract the Firebird optimizer's execution plan (`PLAN`) without scanning entire datasets, detecting unindexed full-table scans (`NATURAL SCAN`) and memory/disk sorting bottlenecks (`SORT`).
5. **Strict Query Safety & MVCC Best Practices**:
   - `fb_query` enforces read-only operations (`SELECT`), guarding against accidental data modification.
   - Commits read transactions immediately upon completion, preventing **OAT (*Oldest Active Transaction*)** stalls, garbage collection starvation, and runaway `.fdb` database file growth.
6. **Faithful to Firebird Foundation Standards**:
   - Full introspection of system catalog tables (`RDB$`), supporting modern types: `BOOLEAN` (FB3+), `INT128`, `DECFLOAT(16/34)`, `TIMESTAMP WITH TIME ZONE` (FB4+), `BLOB SUB_TYPE TEXT/BINARY`, and index selectivity (`RDB$STATISTICS`).

---

## 🗄️ Multi-Database & Per-Project Configuration

Real-world production codebases (such as enterprise ERPs in Delphi, Laravel, or Python) frequently require:
- Different databases per project/workspace.
- Multiple databases within the same project (e.g., operational database `ERP_DATA.FDB` and audit trail `AUDIT_LOGS.FDB`).

### Automatic Project Discovery:
The server automatically searches for `.firebird-mcp.json` at the root of the project (or traversing parent directories up to the workspace root).

Place a `.firebird-mcp.json` file in your repository:

```json
{
  "default": "main",
  "databases": {
    "main": {
      "host": "localhost",
      "port": 3050,
      "database": "/var/data/ERP_DATA.FDB",
      "user": "SYSDBA",
      "password": "masterkey",
      "charset": "WIN1252",
      "description": "Primary operational database"
    },
    "audit": {
      "host": "localhost",
      "port": 3050,
      "database": "/var/data/AUDIT_LOGS.FDB",
      "user": "SYSDBA",
      "password": "masterkey",
      "charset": "WIN1252",
      "description": "Secondary database for audit trails and system logs"
    },
    "staging": {
      "host": "192.168.1.50",
      "port": 3050,
      "database": "D:\\data\\STAGING.FDB",
      "user": "SYSDBA",
      "password": "masterkey",
      "charset": "WIN1252",
      "description": "Remote staging/test environment"
    }
  }
}
```

> **Security Tip:** Add `.firebird-mcp.json` to your `.gitignore` when working with sensitive credentials, providing a `.firebird-mcp.example.json` template for team members.

### Interacting with Multiple Databases:
- **Target a specific database:** All tools accept an optional `db_alias` parameter (e.g., `fb_query(sql="SELECT * FROM LOGS", db_alias="audit")`).
- **List available databases:** The `fb_list_databases()` tool lists all configured aliases, connection statuses, and marks the currently active default.
- **Switch the active database:** The `fb_use_database("audit")` tool sets the default database for subsequent commands during the session.
- **Add databases on the fly:** `fb_configure_database(...)` allows registering new database connections dynamically during chat without restarting the IDE.

---

## 🛠️ Available MCP Tools

### Database & Connection Management
| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `fb_list_databases` | *None* | Lists all databases configured for the current project, the active config file, and the current default alias. |
| `fb_use_database` | `alias` | Switches the default database for the active session. |
| `fb_configure_database` | `alias`, `database`, `host`, `port`, `user`, `password`, `charset`, `set_as_default` | Registers or updates a connection dynamically at runtime. |
| `fb_reload_config` | `config_path` *(optional)* | Reloads the project `.firebird-mcp.json` file. |

### Schema & Metadata Introspection
| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `fb_list_tables` | `db_alias` *(optional)* | Lists all user tables (filters out `RDB$` system tables). |
| `fb_list_views` | `db_alias` *(optional)* | Lists all registered user views. |
| `fb_list_procedures` | `db_alias` *(optional)* | Lists all user Stored Procedures. |
| `fb_list_generators` | `db_alias` *(optional)* | Lists all user Generators / Sequences. |
| `fb_inspect_table` | `table_name`, `db_alias` *(optional)* | Returns column definitions, precise data types, PK/FK constraints, and indices with real selectivity (`RDB$STATISTICS`). |

### Performance Analysis & Execution
| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `fb_explain_plan` | `sql`, `db_alias` *(optional)* | Compiles the query in the engine, extracts the `PLAN`, highlights `NATURAL SCAN` warnings, and suggests indexing strategies. |
| `fb_query` | `sql`, `limit` (default 50, max 1000), `db_alias` *(optional)* | Executes read-only `SELECT` queries with safety guards and immediate transaction commits. |
| `fb_execute_dml` | `sql`, `db_alias` *(optional)* | Executes explicit `INSERT`, `UPDATE`, `DELETE`, or `EXECUTE PROCEDURE` statements. |
| `fb_execute_ddl` | `ddl`, `db_alias` *(optional)* | Executes structural DDL statements (`CREATE INDEX`, `ALTER TABLE`, etc.) with explicit commit. |
| `fb_database_health` | `db_alias` *(optional)* | Audits database health via `MON$` tables (ODS version, page size, active attachments, and OAT-to-Next-Transaction gap). |

---

## 💻 Installation

### Clone and Install Locally
```bash
git clone https://github.com/lucasgabriel0802/firebird-mcp.git ~/firebird-mcp
cd ~/firebird-mcp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

---

## ⚙️ Universal Configuration for Any IDE

Because this server strictly follows the standard **MCP stdio protocol**, it connects seamlessly to any client:

### 1. Google Antigravity IDE
Add the entry in `~/.gemini/config/mcp_config.json` or your workspace configuration:

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
Add the entry in `.cursor/mcp.json` at the root of your project or in **Settings > Features > MCP**:

```json
{
  "mcpServers": {
    "firebird": {
      "command": "python",
      "args": ["-m", "firebird_mcp.server"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

---

### 3. VS Code (with Cline / Roo Code / Copilot MCP)
In your `cline_mcp_settings.json` or Roo Code settings:

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

### 4. Claude Desktop
In `claude_desktop_config.json`:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "firebird": {
      "command": "python",
      "args": ["-m", "firebird_mcp.server", "--config", "C:\\my_project\\.firebird-mcp.json"],
      "cwd": "C:\\my_project"
    }
  }
}
```

---

### 5. Windsurf
In `~/.codeium/windsurf/mcp_config.json`:

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
In Zed's `settings.json`:

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

## 🧠 Synergy: `firebird-master` Skill + `firebird-mcp`

This MCP server works hand-in-hand with the [`firebird-master`](https://github.com/lucasgabriel0802/my-agent-skills/tree/main/skills/firebird-master) skill:

```
┌────────────────────────────────────────────────────────┐
│                   AI AGENT / COPILOT                   │
├──────────────────────────┬─────────────────────────────┤
│  SKILL: firebird-master  │     MCP: firebird-mcp       │
│         (Brain)          │          (Muscle)           │
├──────────────────────────┼─────────────────────────────┤
│ • Cross-version syntax   │ • TCP socket wire protocol  │
│   (FB 2.5 vs 3 vs 4 vs 5)│ • Executes & fetches PLAN   │
│ • SQL anti-pattern rules │ • Introspects RDB$ schema   │
│ • Delphi FireDAC best    │ • Gathers MON$ telemetry    │
│   practices & index hints│ • Auto-discovers project DB │
└──────────────────────────┴─────────────────────────────┘
```

---

## 📄 License
Distributed under the [MIT](LICENSE) License.
