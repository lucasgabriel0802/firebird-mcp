# Firebird MCP Server 🔥

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![MCP Standard](https://img.shields.io/badge/MCP-2024--11--05-green.svg)](https://modelcontextprotocol.io)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Firebird 2.5 to 5.0](https://img.shields.io/badge/Firebird-2.5%20%7C%203.0%20%7C%204.0%20%7C%205.0-red.svg)](https://www.firebirdsql.org)

> 🌐 **Language / Idioma:** **English** | [Português (Brasil)](README.pt-BR.md)

Open-source **Model Context Protocol (MCP)** server for **Firebird Database**, developed for free and independent community use with support for all major releases (**Firebird 2.5, 3.0, 4.0, and 5.0**).

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
6. **Broad System Catalog Mapping**:
   - Comprehensive introspection of Firebird system catalog tables (`RDB$`), supporting types across versions: `BOOLEAN` (FB3+), `INT128`, `DECFLOAT(16/34)`, `TIMESTAMP WITH TIME ZONE` (FB4+), `BLOB SUB_TYPE TEXT/BINARY`, and index selectivity (`RDB$STATISTICS`).

---

## 🗄️ Multi-Database & Per-Project Configuration

Real-world production codebases (such as enterprise ERPs in Delphi, Laravel, or Python) frequently require:
- Different databases per project/workspace.
- Multiple databases within the same project (e.g., operational database `ERP_DATA.FDB` and audit trail `AUDIT_LOGS.FDB`).

### Where and How to Configure Databases:

Firebird MCP provides two flexible organization patterns:

#### Option A (Recommended Default): Central Global Catalog (`~/.firebird-mcp.json`)
Instead of scattering `.firebird-mcp.json` files across every repository, maintain a **single central catalog** in your user home directory (`~/.firebird-mcp.json` on Linux/macOS or `C:\Users\YourUser\.firebird-mcp.json` on Windows).

In this catalog, you register all databases on your machine and use the `"projects"` property to specify which projects/repositories use each database:

```json
{
  "default": "erp_main",
  "databases": {
    "erp_main": {
      "host": "localhost",
      "port": 3050,
      "database": "/var/data/ERP_DATA.FDB",
      "user": "SYSDBA",
      "password": "masterkey",
      "charset": "WIN1252",
      "description": "Primary ERP operational database",
      "projects": ["web_projects", "erp-desktop"],
      "tags": ["erp", "financial", "sales"]
    },
    "erp_audit": {
      "host": "localhost",
      "port": 3050,
      "database": "/var/data/AUDIT_LOGS.FDB",
      "user": "SYSDBA",
      "password": "masterkey",
      "charset": "WIN1252",
      "description": "Secondary database for audit trails and logs",
      "projects": ["web_projects", "erp-desktop"],
      "tags": ["audit", "logs", "security"]
    },
    "pos_store": {
      "host": "192.168.1.10",
      "port": 3050,
      "database": "C:\\POS\\STORE.FDB",
      "user": "SYSDBA",
      "password": "masterkey",
      "charset": "WIN1252",
      "description": "Store front checkout database",
      "projects": ["pos-vcl"],
      "tags": ["pos", "cashier"]
    },
    "shared_staging": {
      "host": "localhost",
      "port": 3050,
      "database": "/data/STAGING.FDB",
      "user": "SYSDBA",
      "password": "masterkey",
      "charset": "WIN1252",
      "description": "Shared staging/test database accessible across all projects",
      "projects": []
    }
  }
}
```

> **Tip on Shared Databases:** Databases with an empty `"projects": []` array or `"*"` are treated as global shared databases and remain visible across all workspaces.

#### Option B: Local Project Configuration (`.firebird-mcp.json`)
If you prefer a repository to isolate its own credentials, place a `.firebird-mcp.json` file in the project root. The MCP checks for a local project file first; if present, it has **absolute precedence** over the global catalog.

---

### How the Agent Interacts with Databases:
1. **Automatic Workspace Context (CWD):**
   - When you open a workspace (e.g., `/home/lucas/web_projects`), the MCP automatically resolves the active project and filters databases matching that project.
   - **Single Database in Project:** The MCP auto-selects the database without asking unnecessary questions.
   - **Multiple Databases in Project (e.g., main and audit):** For generic commands (e.g., *"run a select on orders"*), the MCP halts and asks which database to use.
2. **Direct Investigation Targeting (Zero Friction):**
   - If you mention the database in your prompt (e.g., *"investigate bug on audit database"* or *"check table X on pos"*), the agent/MCP resolves the alias immediately and connects **without asking confirmation questions**.
3. **Smart Approximate Search:**
   - Switch databases using `fb_use_database("audit")` — the MCP matches exact names, substrings (e.g., `erp_audit`), and associated tags.


---

## 🛠️ Available MCP Tools

### Database & Connection Management
| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `fb_create_config` | `database`, `alias`, `host`, `port`, `user`, `password`, `charset`, `description`, `projects`, `tags`, `filepath` | Creates and saves Central Global Catalog (`~/.firebird-mcp.json`) or local file with project tags. |
| `fb_list_databases` | `project_filter` *(optional)* | Lists all databases in catalog, highlighting matches for the active project. |
| `fb_use_database` | `alias` | Switches the active database for the current session (with smart match by name, substring, or tag). |
| `fb_configure_database` | `alias`, `database`, `host`, `port`, `user`, `password`, `charset`, `description`, `projects`, `tags`, `set_as_default`, `save_to_file` | Registers or updates a connection with projects/tags dynamically and persists to file. |
| `fb_reload_config` | `config_path` *(optional)* | Reloads the catalog from global or local file. |

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

## 💻 Installation & Execution

### 🐳 Option 1: Docker (Gold Standard — Recommended for Windows, macOS & Linux)
Running via Docker eliminates all local Python runtime and dependency requirements:

```bash
# Clone and build the image locally:
git clone https://github.com/lucasgabriel0802/firebird-mcp.git
cd firebird-mcp
docker build -t firebird-mcp:latest .
```

#### Universal IDE Configuration via Docker (Stdio Mode):
Configure your IDE to launch the container on-demand. This configuration works seamlessly on **Windows, macOS, and Linux**:

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

> **Why this is the Gold Standard:**
> - `-i`: Keeps stdin/stdout open for JSON-RPC without allocating a pseudo-TTY (no `-t` to avoid byte corruption).
> - `--rm`: Cleans up the container automatically when the IDE closes.
> - `-v "${workspaceFolder}:/workspace"`: Mounts your current project for automatic `.firebird-mcp.json` discovery.
> - `--add-host host.docker.internal:host-gateway`: Resolves your host machine's IP (e.g. Firebird running on port 3050 in Windows, macOS, or Linux) using `host.docker.internal`.

---

### 🚀 Option 2: Docker Compose (Background Service & Batteried Testing DB)

#### A. Run as an HTTP/SSE Background Service
If you prefer running the MCP server as a permanent background service on port `8000`:

```bash
docker compose up -d firebird-mcp
```
Connect via SSE endpoint: `http://localhost:8000/sse`.

#### B. Full Local Testing Environment (with Firebird 5.0 Database)
Spin up both the MCP server and a ready-to-test Firebird 5.0 database container:

```bash
docker compose --profile test-db up -d
```
This starts:
- Firebird 5.0 on `localhost:3050` (password: `masterkey`, database: `TESTE.FDB`).
- Firebird MCP Server on `http://localhost:8000/sse`.

---

### 🐍 Option 3: Local Python Virtual Environment

```bash
git clone https://github.com/lucasgabriel0802/firebird-mcp.git ~/firebird-mcp
cd ~/firebird-mcp
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

---

## ⚙️ Universal Configuration for Any IDE

### 1. Google Antigravity IDE
In `~/.gemini/config/mcp_config.json` (or workspace configuration):

**Using Docker (Recommended):**
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

**Or using Python Virtual Environment:**
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
In `.cursor/mcp.json` at your project root or in **Settings > Features > MCP**:

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

### 3. VS Code (Cline / Roo Code / Copilot MCP)
In `cline_mcp_settings.json` or Roo Code settings:

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

## ⚖️ Disclaimer & Trademarks

This is an independent open-source community project licensed under the MIT License. It is not affiliated with, funded by, endorsed by, or officially associated with the Firebird Project or the Firebird Foundation. "Firebird" is a registered trademark of the Firebird Foundation.

---

## 📄 License
Distributed under the [MIT](LICENSE) License.
