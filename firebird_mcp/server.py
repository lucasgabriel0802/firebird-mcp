from typing import Optional
from mcp.server.fastmcp import FastMCP
from .connection import connection_manager
from .inspector import list_tables, list_views, inspect_table
from .analyzer import explain_plan, execute_query, execute_ddl
from .telemetry import get_database_health

# Inicializa o servidor FastMCP
mcp = FastMCP("firebird-mcp")

@mcp.tool()
def fb_configure_connection(
    database: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    charset: Optional[str] = None
) -> dict:
    """
    Configura ou atualiza os parâmetros de conexão com o banco de dados Firebird em tempo de execução.
    Suporta bancos Firebird 2.5, 3.0, 4.0 e 5.0 locais ou remotos.
    """
    return connection_manager.configure(
        database=database,
        host=host,
        port=port,
        user=user,
        password=password,
        charset=charset
    )

@mcp.tool()
def fb_connection_status() -> dict:
    """
    Verifica os parâmetros atuais de conexão e testa a comunicação com o banco Firebird.
    """
    summary = connection_manager.get_config_summary()
    try:
        with connection_manager.get_connection() as conn:
            summary["connected"] = True
            summary["status"] = "Conexão estabelecida com sucesso."
    except Exception as e:
        summary["connected"] = False
        summary["error"] = str(e)
    return summary

@mcp.tool()
def fb_list_tables() -> list:
    """
    Lista todas as tabelas de usuário cadastradas no banco de dados Firebird (excluindo tabelas de sistema RDB$).
    """
    return list_tables()

@mcp.tool()
def fb_list_views() -> list:
    """
    Lista todas as views de usuário cadastradas no banco de dados Firebird.
    """
    return list_views()

@mcp.tool()
def fb_inspect_table(table_name: str) -> dict:
    """
    Inspeciona detalhadamente uma tabela no Firebird:
    - Colunas, tipos de dados, domínios e nulidade
    - Chaves primárias (PK) e estrangeiras (FK)
    - Índices existentes com suas respectivas colunas e seletividade (RDB$STATISTICS).
    """
    return inspect_table(table_name)

@mcp.tool()
def fb_explain_plan(sql: str) -> dict:
    """
    Compila uma consulta SQL no Firebird e extrai o plano de execução (PLAN).
    Analisa se há leituras sequenciais (NATURAL SCAN) em tabelas, ordenação (SORT),
    e fornece recomendações cirúrgicas de otimização de índices.
    """
    return explain_plan(sql)

@mcp.tool()
def fb_query(sql: str, limit: int = 50) -> dict:
    """
    Executa uma consulta SELECT de leitura no Firebird com limite seguro de linhas (padrão 50).
    Fecha a transação imediatamente após a leitura para evitar travar o OAT (Oldest Active Transaction).
    """
    return execute_query(sql, limit=limit)

@mcp.tool()
def fb_execute_ddl(ddl: str) -> dict:
    """
    Executa um comando DDL no Firebird (como CREATE INDEX, ALTER TABLE, etc.) com commit explícito.
    """
    return execute_ddl(ddl)

@mcp.tool()
def fb_database_health() -> dict:
    """
    Diagnostica a integridade e telemetria do banco Firebird através das tabelas MON$:
    - Versão do Engine e ODS
    - Tamanho de página (Page Size) e sweep interval
    - Gap entre OAT (Oldest Active Transaction) e Next Transaction (diagnóstico de inchaço do .fdb e GC)
    - Total de conexões ativas, transações e statements abertos.
    """
    return get_database_health()

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
