import sys
import argparse
from typing import Optional
try:
    # mcp 2.x
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    # mcp 1.x
    from mcp.server.fastmcp import FastMCP
from .connection import connection_manager
from .inspector import list_tables, list_views, list_procedures, list_generators, inspect_table
from .analyzer import explain_plan, execute_query, execute_dml, execute_ddl
from .telemetry import get_database_health

# Inicializa o servidor FastMCP
mcp = FastMCP("firebird-mcp")

# ==========================================
# Ferramentas de Gerenciamento de Bancos
# ==========================================

@mcp.tool()
def fb_create_config(
    database: str,
    alias: str = "principal",
    host: str = "localhost",
    port: int = 3050,
    user: str = "SYSDBA",
    password: str = "masterkey",
    charset: str = "WIN1252",
    description: Optional[str] = None,
    projects: Optional[list] = None,
    tags: Optional[list] = None,
    filepath: Optional[str] = None
) -> dict:
    """
    Cria e salva um novo arquivo de configuração (Catálogo Central Global ~/.firebird-mcp.json por padrão).
    Permite associar o banco a projetos específicos (ex: projects=['web_projects']) e tags.
    """
    return connection_manager.create_config_file(
        alias=alias,
        database=database,
        host=host,
        port=port,
        user=user,
        password=password,
        charset=charset,
        description=description,
        projects=projects,
        tags=tags,
        filepath=filepath
    )

@mcp.tool()
def fb_list_databases(project_filter: Optional[str] = None) -> dict:
    """
    Lista todos os bancos de dados Firebird configurados no Catálogo Central Global (~/.firebird-mcp.json)
    ou arquivo local, identificando os bancos correspondentes ao projeto ativo.
    Informa se há necessidade de confirmação/pergunta ao usuário quando houver múltiplos bancos no projeto.
    """
    return connection_manager.list_databases(project_filter=project_filter)

@mcp.tool()
def fb_use_database(alias: str) -> dict:
    """
    Define o banco de dados ativo da sessão entre os configurados no catálogo.
    Suporta busca inteligente por nome exato, case-insensitive, substring no alias ou tag (ex: 'auditoria' -> 'erp_auditoria').
    Todas as chamadas seguintes que não especificarem 'db_alias' utilizarão este banco ativo.
    """
    return connection_manager.set_default_database(alias)

@mcp.tool()
def fb_configure_database(
    alias: str,
    database: str,
    host: str = "localhost",
    port: int = 3050,
    user: str = "SYSDBA",
    password: str = "masterkey",
    charset: str = "WIN1252",
    description: Optional[str] = None,
    projects: Optional[list] = None,
    tags: Optional[list] = None,
    set_as_default: bool = False,
    save_to_file: bool = True
) -> dict:
    """
    Cadastra ou atualiza um banco de dados dinamicamente no catálogo (global ou local).
    Permite associar o banco a projetos específicos (projects=['web_projects']) e tags para filtragem contextual.
    """
    return connection_manager.configure_database(
        alias=alias,
        database=database,
        host=host,
        port=port,
        user=user,
        password=password,
        charset=charset,
        description=description,
        projects=projects,
        tags=tags,
        set_as_default=set_as_default,
        save_to_file=save_to_file
    )

@mcp.tool()
def fb_reload_config(config_path: Optional[str] = None) -> dict:
    """
    Recarrega a configuração de bancos a partir do Catálogo Central Global (~/.firebird-mcp.json)
    ou arquivo local do projeto.
    """
    connection_manager.reload_config(config_path)
    return connection_manager.list_databases()

# ==========================================
# Ferramentas de Inspeção e Metadados
# ==========================================

@mcp.tool()
def fb_list_tables(db_alias: Optional[str] = None) -> list:
    """
    Lista todas as tabelas de usuário (não de sistema) do banco especificado (ou ativo na sessão).
    Se houver múltiplos bancos no projeto e nenhum estiver ativo na sessão, pergunte antes ao usuário.
    """
    return list_tables(db_alias=db_alias)

@mcp.tool()
def fb_list_views(db_alias: Optional[str] = None) -> list:
    """
    Lista todas as views de usuário do banco especificado (ou ativo na sessão).
    Se houver múltiplos bancos no projeto e nenhum estiver ativo na sessão, pergunte antes ao usuário.
    """
    return list_views(db_alias=db_alias)

@mcp.tool()
def fb_list_procedures(db_alias: Optional[str] = None) -> list:
    """
    Lista todas as Stored Procedures cadastradas no banco especificado (ou ativo na sessão).
    Se houver múltiplos bancos no projeto e nenhum estiver ativo na sessão, pergunte antes ao usuário.
    """
    return list_procedures(db_alias=db_alias)

@mcp.tool()
def fb_list_generators(db_alias: Optional[str] = None) -> list:
    """
    Lista todos os Generators / Sequences de usuário no banco especificado (ou ativo na sessão).
    Se houver múltiplos bancos no projeto e nenhum estiver ativo na sessão, pergunte antes ao usuário.
    """
    return list_generators(db_alias=db_alias)

@mcp.tool()
def fb_inspect_table(table_name: str, db_alias: Optional[str] = None) -> dict:
    """
    Inspeciona detalhadamente a estrutura de uma tabela no Firebird:
    - Colunas, tipos exatos (DECFLOAT, INT128, BOOLEAN, VARCHAR, BLOB SUB_TYPE), domínios e nullability
    - Chaves primárias (PK) e estrangeiras (FK)
    - Índices com ordem (ASC/DESC), colunas participantes e taxa de seletividade real (RDB$STATISTICS).
    Se houver múltiplos bancos no projeto e nenhum estiver ativo na sessão, pergunte antes ao usuário.
    """
    return inspect_table(table_name=table_name, db_alias=db_alias)

# ==========================================
# Ferramentas de Análise, Planos e Execução
# ==========================================

@mcp.tool()
def fb_explain_plan(sql: str, db_alias: Optional[str] = None) -> dict:
    """
    Compila uma consulta SQL no Firebird e extrai o plano de execução compilado (PLAN).
    Analisa leituras sequenciais (NATURAL SCAN) em tabelas, ordenações em memória (SORT)
    e fornece recomendações cirúrgicas de indexação e reescrita.
    Se houver múltiplos bancos no projeto e nenhum estiver ativo na sessão, pergunte antes ao usuário.
    """
    return explain_plan(sql=sql, db_alias=db_alias)

@mcp.tool()
def fb_query(sql: str, limit: int = 50, db_alias: Optional[str] = None) -> dict:
    """
    Executa consulta SELECT de leitura no Firebird com limite seguro de linhas (1 a 1000).
    Seguro: Rejeita comandos de alteração de dados e encerra a transação com commit imediato.
    Se houver múltiplos bancos no projeto e nenhum estiver ativo na sessão, pergunte antes ao usuário.
    """
    return execute_query(sql=sql, limit=limit, db_alias=db_alias)

@mcp.tool()
def fb_execute_dml(sql: str, db_alias: Optional[str] = None) -> dict:
    """
    Executa comandos de manipulação de dados (INSERT, UPDATE, DELETE, EXECUTE PROCEDURE)
    com confirmação e encerramento de transação.
    Se houver múltiplos bancos no projeto e nenhum estiver ativo na sessão, pergunte antes ao usuário.
    """
    return execute_dml(sql=sql, db_alias=db_alias)

@mcp.tool()
def fb_execute_ddl(ddl: str, db_alias: Optional[str] = None) -> dict:
    """
    Executa comandos estruturais DDL no Firebird (como CREATE INDEX, ALTER TABLE, etc.) com commit explícito.
    Se houver múltiplos bancos no projeto e nenhum estiver ativo na sessão, pergunte antes ao usuário.
    """
    return execute_ddl(ddl=ddl, db_alias=db_alias)

@mcp.tool()
def fb_database_health(db_alias: Optional[str] = None) -> dict:
    """
    Diagnostica a integridade e telemetria do banco Firebird através das tabelas MON$:
    - Versão do Engine e ODS
    - Tamanho de página (Page Size) e sweep interval
    - Diagnóstico do gap OAT (Oldest Active Transaction) vs Next Transaction para prevenção de inchaço do .fdb
    - Total de conexões ativas, transações e statements abertos.
    Se houver múltiplos bancos no projeto e nenhum estiver ativo na sessão, pergunte antes ao usuário.
    """
    return get_database_health(db_alias=db_alias)


def main():
    parser = argparse.ArgumentParser(description="Firebird MCP Server")
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Caminho explícito para o arquivo de configuração de bancos (ex: .firebird-mcp.json)"
    )
    parser.add_argument(
        "--transport",
        "-t",
        type=str,
        choices=["stdio", "sse"],
        default=None,
        help="Transporte de comunicação: stdio (padrão para IDEs) ou sse (serviço HTTP/SSE)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host para escuta no modo SSE (padrão: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=None,
        help="Porta para escuta no modo SSE (padrão: 8000)"
    )
    args, unknown = parser.parse_known_args()

    import os
    config_path = args.config or os.getenv("FIREBIRD_CONFIG_PATH")
    if config_path:
        connection_manager.reload_config(explicit_path=config_path)

    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    host = args.host or os.getenv("MCP_HOST", "0.0.0.0")
    port = args.port or int(os.getenv("MCP_PORT", "8000"))

    if transport == "sse":
        mcp.run(transport="sse", host=host, port=port)
    else:
        mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
