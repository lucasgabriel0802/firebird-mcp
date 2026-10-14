import re
from typing import Dict, Any, List
from .connection import connection_manager

def explain_plan(sql: str) -> Dict[str, Any]:
    """
    Prepara a query no Firebird e extrai o PLAN gerado pelo otimizador,
    analisando a presença de leituras sequenciais (NATURAL SCAN) e riscos.
    """
    clean_sql = sql.strip().rstrip(";")
    
    with connection_manager.get_connection() as conn:
        cursor = conn.cursor()
        # firebirdsql expõe o plano de execução compilado via cursor.plan
        cursor.prep(clean_sql)
        plan_str = getattr(cursor, "plan", "") or "PLAN NOT AVAILABLE"

    # Heurística de análise do PLAN
    natural_tables = []
    # Busca padrões como: PLAN (TABELA NATURAL) ou PLAN (TABELA INDEX ...)
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
            f"Alerta de Desempenho: As seguintes tabelas realizam leitura sequencial (NATURAL SCAN): "
            f"{', '.join(natural_tables)}. Se forem tabelas volumosas, verifique filtros no WHERE e crie índices correspondentes."
        )
    if has_sort:
        recommendations.append(
            "Ordenação em memória/disco (SORT) detectada. Verifique se um índice composto cobrindo o filtro e a ordenação (ORDER BY) pode eliminá-la."
        )

    return {
        "sql": clean_sql,
        "plan": plan_str,
        "natural_scan_tables": natural_tables,
        "has_sort": has_sort,
        "has_hash_join": has_hash,
        "has_merge_join": has_merge,
        "is_optimal": len(natural_tables) == 0 and not has_sort,
        "recommendations": recommendations
    }

def execute_query(sql: str, limit: int = 50) -> Dict[str, Any]:
    """
    Executa uma consulta SELECT no Firebird com limite de registros
    e fecha a transação imediatamente para evitar prender o OAT.
    """
    clean_sql = sql.strip().rstrip(";")
    
    with connection_manager.get_connection() as conn:
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
                # Converte bytes ou tipos especiais para string legível
                if isinstance(val, (bytes, bytearray)):
                    row_dict[col_name] = f"<BLOB/BYTES len={len(val)}>"
                else:
                    row_dict[col_name] = str(val) if val is not None else None
            rows.append(row_dict)

        # Commit da transação de leitura para liberar recursos
        conn.commit()

        return {
            "columns": columns,
            "rows": rows,
            "count": len(rows),
            "limit_applied": limit
        }

def execute_ddl(ddl: str) -> Dict[str, Any]:
    """
    Executa um comando DDL (CREATE INDEX, ALTER TABLE, etc.) com commit explícito.
    """
    clean_ddl = ddl.strip().rstrip(";")
    
    with connection_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(clean_ddl)
        conn.commit()

    return {
        "status": "SUCCESS",
        "message": "Comando DDL executado com sucesso e transação commitada.",
        "ddl": clean_ddl
    }
