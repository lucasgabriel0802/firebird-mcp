from typing import List, Dict, Any, Optional
from .connection import connection_manager

# Mapeamento de tipos internos do Firebird (RDB$FIELD_TYPE)
FIREBIRD_TYPE_MAP = {
    7: "SMALLINT",
    8: "INTEGER",
    10: "FLOAT",
    12: "DATE",
    13: "TIME",
    14: "CHAR",
    16: "BIGINT",  # ou INT128 no FB 4+
    27: "DOUBLE PRECISION",
    35: "TIMESTAMP",
    37: "VARCHAR",
    40: "CSTRING",
    45: "BLOB_ID",
    261: "BLOB"
}

def list_tables() -> List[Dict[str, Any]]:
    """Lista todas as tabelas de usuário (não de sistema)."""
    sql = """
        SELECT TRIM(RDB$RELATION_NAME) AS TABLE_NAME,
               RDB$RELATION_TYPE AS TABLE_TYPE
        FROM RDB$RELATIONS
        WHERE (RDB$SYSTEM_FLAG = 0 OR RDB$SYSTEM_FLAG IS NULL)
          AND RDB$VIEW_BLR IS NULL
        ORDER BY RDB$RELATION_NAME
    """
    with connection_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        tables = []
        for row in cursor.fetchall():
            tables.append({
                "table_name": row[0],
                "type": "TABLE"
            })
        return tables

def list_views() -> List[str]:
    """Lista todas as views de usuário."""
    sql = """
        SELECT TRIM(RDB$RELATION_NAME) AS VIEW_NAME
        FROM RDB$RELATIONS
        WHERE (RDB$SYSTEM_FLAG = 0 OR RDB$SYSTEM_FLAG IS NULL)
          AND RDB$VIEW_BLR IS NOT NULL
        ORDER BY RDB$RELATION_NAME
    """
    with connection_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        return [row[0] for row in cursor.fetchall()]

def inspect_table(table_name: str) -> Dict[str, Any]:
    """Inspeciona colunas, tipos, PK, FKs e índices com seletividade de uma tabela."""
    table_upper = table_name.strip().upper()

    # 1. Colunas e tipos
    columns_sql = """
        SELECT TRIM(RF.RDB$FIELD_NAME) AS FIELD_NAME,
               F.RDB$FIELD_TYPE,
               F.RDB$FIELD_LENGTH,
               F.RDB$FIELD_SCALE,
               F.RDB$FIELD_SUB_TYPE,
               RF.RDB$NULL_FLAG,
               TRIM(F.RDB$FIELD_NAME) AS DOMAIN_NAME
        FROM RDB$RELATION_FIELDS RF
        JOIN RDB$FIELDS F ON RF.RDB$FIELD_SOURCE = F.RDB$FIELD_NAME
        WHERE TRIM(RF.RDB$RELATION_NAME) = ?
        ORDER BY RF.RDB$FIELD_POSITION
    """

    # 2. Índices e seletividade
    indices_sql = """
        SELECT TRIM(I.RDB$INDEX_NAME) AS INDEX_NAME,
               I.RDB$UNIQUE_FLAG,
               I.RDB$STATISTICS,
               TRIM(S.RDB$FIELD_NAME) AS FIELD_NAME,
               S.RDB$FIELD_POSITION
        FROM RDB$INDICES I
        JOIN RDB$INDEX_SEGMENTS S ON I.RDB$INDEX_NAME = S.RDB$INDEX_NAME
        WHERE TRIM(I.RDB$RELATION_NAME) = ?
        ORDER BY I.RDB$INDEX_NAME, S.RDB$FIELD_POSITION
    """

    # 3. Constraints (PK, FK, UNIQUE)
    constraints_sql = """
        SELECT TRIM(RC.RDB$CONSTRAINT_NAME) AS CONSTRAINT_NAME,
               TRIM(RC.RDB$CONSTRAINT_TYPE) AS CONSTRAINT_TYPE,
               TRIM(RC.RDB$INDEX_NAME) AS INDEX_NAME,
               TRIM(REF.RDB$CONST_NAME_UQ) AS TARGET_UQ_NAME
        FROM RDB$RELATION_CONSTRAINTS RC
        LEFT JOIN RDB$REF_CONSTRAINTS REF ON RC.RDB$CONSTRAINT_NAME = REF.RDB$CONSTRAINT_NAME
        WHERE TRIM(RC.RDB$RELATION_NAME) = ?
    """

    with connection_manager.get_connection() as conn:
        cursor = conn.cursor()

        # Colunas
        cursor.execute(columns_sql, (table_upper,))
        columns = []
        for row in cursor.fetchall():
            field_type_code = row[1]
            type_name = FIREBIRD_TYPE_MAP.get(field_type_code, f"TYPE_{field_type_code}")
            scale = row[3]
            length = row[2]

            # Ajuste de tipos numéricos / decimais
            if scale < 0 and field_type_code in (7, 8, 16):
                type_desc = f"NUMERIC({length}, {abs(scale)})"
            elif type_name in ("CHAR", "VARCHAR"):
                type_desc = f"{type_name}({length})"
            else:
                type_desc = type_name

            columns.append({
                "field_name": row[0],
                "type": type_desc,
                "nullable": row[5] != 1,
                "domain": row[6]
            })

        # Índices
        cursor.execute(indices_sql, (table_upper,))
        indices_dict = {}
        for row in cursor.fetchall():
            idx_name = row[0]
            if idx_name not in indices_dict:
                indices_dict[idx_name] = {
                    "index_name": idx_name,
                    "unique": row[1] == 1,
                    "selectivity": float(row[2]) if row[2] is not None else None,
                    "fields": []
                }
            indices_dict[idx_name]["fields"].append(row[3])

        # Constraints
        cursor.execute(constraints_sql, (table_upper,))
        constraints = []
        for row in cursor.fetchall():
            constraints.append({
                "constraint_name": row[0],
                "type": row[1],
                "index_name": row[2],
                "target_uq": row[3]
            })

        return {
            "table_name": table_upper,
            "columns": columns,
            "indices": list(indices_dict.values()),
            "constraints": constraints
        }
