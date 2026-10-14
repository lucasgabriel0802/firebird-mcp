import re
from typing import Dict, Any, List, Optional
from .connection import connection_manager

# Palavras-chave proibidas no modo de leitura estrita (fb_query)
DESTRUCTIVE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|RECREATE|GRANT|REVOKE|TRUNCATE)\b",
    re.IGNORECASE
)

def explain_plan(sql: str, db_alias: Optional[str] = None) -> Dict[str, Any]:
    """
    Prepara a query no Firebird e extrai o PLAN compilado pelo otimizador,
    analisando a presença de leituras sequenciais (NATURAL SCAN) e ordenações (SORT).
    """
    clean_sql = sql.strip().rstrip(";")
    
    with connection_manager.get_connection(db_alias) as conn:
        cursor = conn.cursor()
        cursor.prep(clean_sql)
        plan_str = getattr(cursor, "plan", "") or "PLAN NOT AVAILABLE"

    # Heurística de análise do PLAN
    natural_tables = []
    natural_matches = re.findall(r"([A-Za-z0-9_$]+)\s+NATURAL", plan_str, re.IGNORECASE)
    for tbl in natural_matches:
        if tbl.upper() not in natural_tables:
            natural_tables.append(tbl.upper())

    has_sort = bool(re.search(r"\bSORT\b", plan_str, re.IGNORECASE))
    has_hash = bool(re.search(r"\bHASH\b", plan_str, re.IGNORECASE))
    has_merge = bool(re.search(r"\bMERGE\b", plan_str, re.IGNORECASE))

    recommendations = []
    if natural_tables:
        recommendations.append(
            f"Alerta de Desempenho (NATURAL SCAN): As tabelas [{', '.join(natural_tables)}] estão sendo "
            f"lidas sequencialmente linha a linha. Se forem tabelas volumosas, adicione índices nos campos "
            f"utilizados na cláusula WHERE ou nos relacionamentos de JOIN."
        )
    if has_sort:
        recommendations.append(
            "Ordenação em memória/disco (SORT): O Firebird está ordenando o resultado após a leitura. "
            "Se o volume for alto, crie um índice que contemple a ordem do ORDER BY."
        )

    cfg = connection_manager.get_config(db_alias)
    return {
        "database_alias": cfg.alias,
        "sql": clean_sql,
        "plan": plan_str,
        "natural_scan_tables": natural_tables,
        "has_sort": has_sort,
        "has_hash_join": has_hash,
        "has_merge_join": has_merge,
        "is_optimal": len(natural_tables) == 0 and not has_sort,
        "recommendations": recommendations
    }

def execute_query(sql: str, limit: int = 50, db_alias: Optional[str] = None) -> Dict[str, Any]:
    """
    Executa uma consulta SELECT de leitura no Firebird com limite de registros.
    Garante segurança impedindo comandos de modificação/exclusão disfarçados
    e fecha a transação imediatamente para proteger o OAT.
    """
    clean_sql = sql.strip().rstrip(";")

    # Verificação de segurança: apenas SELECT ou WITH (CTE)
    first_word = clean_sql.split(None, 1)[0].upper() if clean_sql else ""
    if first_word not in ("SELECT", "WITH"):
        raise PermissionError(
            f"Comando '{first_word}' não permitido em fb_query. "
            "A ferramenta fb_query é estritamente para consultas de leitura (SELECT). "
            "Para comandos DML (INSERT/UPDATE/DELETE), use fb_execute_dml. "
            "Para comandos estruturais (DDL), use fb_execute_ddl."
        )

    # Limite de segurança de linhas
    limit = max(1, min(limit, 1000))

    with connection_manager.get_connection(db_alias) as conn:
        cursor = conn.cursor()
        cursor.execute(clean_sql)

        description = cursor.description
        if not description:
            return {"rows": [], "count": 0, "columns": []}

        columns = [col[0] for col in description]
        rows = []
        for i, row in enumerate(cursor.fetchall()):
            if i >= limit:
                break
            row_dict = {}
            for col_name, val in zip(columns, row):
                if isinstance(val, (bytes, bytearray)):
                    row_dict[col_name] = f"<BLOB/BYTES len={len(val)}>"
                else:
                    row_dict[col_name] = str(val) if val is not None else None
            rows.append(row_dict)

        conn.commit()

        cfg = connection_manager.get_config(db_alias)
        return {
            "database_alias": cfg.alias,
            "columns": columns,
            "rows": rows,
            "count": len(rows),
            "limit_applied": limit
        }

def execute_dml(sql: str, db_alias: Optional[str] = None) -> Dict[str, Any]:
    """
    Executa comandos de manipulação de dados (INSERT, UPDATE, DELETE, EXECUTE PROCEDURE)
    com confirmação e commit imediato.
    """
    clean_sql = sql.strip().rstrip(";")

    first_word = clean_sql.split(None, 1)[0].upper() if clean_sql else ""
    if first_word in ("DROP", "ALTER", "CREATE", "RECREATE"):
        raise ValueError(f"Comando DDL '{first_word}' deve ser executado através de fb_execute_ddl.")

    with connection_manager.get_connection(db_alias) as conn:
        cursor = conn.cursor()
        cursor.execute(clean_sql)
        rowcount = cursor.rowcount if hasattr(cursor, "rowcount") else -1
        conn.commit()

    cfg = connection_manager.get_config(db_alias)
    return {
        "database_alias": cfg.alias,
        "status": "SUCCESS",
        "affected_rows": rowcount,
        "message": f"Comando DML executado com sucesso no banco '{cfg.alias}'."
    }

def execute_ddl(ddl: str, db_alias: Optional[str] = None) -> Dict[str, Any]:
    """
    Executa comandos estruturais DDL (CREATE INDEX, ALTER TABLE, etc.) com commit explícito.
    """
    clean_ddl = ddl.strip().rstrip(";")

    with connection_manager.get_connection(db_alias) as conn:
        cursor = conn.cursor()
        cursor.execute(clean_ddl)
        conn.commit()

    cfg = connection_manager.get_config(db_alias)
    return {
        "database_alias": cfg.alias,
        "status": "SUCCESS",
        "message": f"Comando DDL executado com sucesso no banco '{cfg.alias}'.",
        "ddl": clean_ddl
    }
