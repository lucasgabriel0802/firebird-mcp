from typing import List, Dict, Any, Optional
from .connection import connection_manager

# Mapeamento de tipos internos do Firebird (RDB$FIELDS.RDB$FIELD_TYPE)
# Compatível com as especificações do Firebird 1.5, 2.0, 2.5, 3.0, 4.0 e 5.0
FIREBIRD_TYPE_MAP = {
    7: "SMALLINT",
    8: "INTEGER",
    10: "FLOAT",
    12: "DATE",
    13: "TIME",
    14: "CHAR",
    16: "BIGINT",
    23: "BOOLEAN",                # FB 3.0+
    24: "DECFLOAT(16)",           # FB 4.0+
    25: "DECFLOAT(34)",           # FB 4.0+
    26: "INT128",                 # FB 4.0+
    27: "DOUBLE PRECISION",
    28: "TIME WITH TIME ZONE",     # FB 4.0+
    29: "TIMESTAMP WITH TIME ZONE",# FB 4.0+
    35: "TIMESTAMP",
    37: "VARCHAR",
    40: "CSTRING",
    45: "BLOB_ID",
    261: "BLOB"
}

BLOB_SUBTYPE_MAP = {
    0: "BINARY",
    1: "TEXT",
    2: "BLR",
    3: "ACL",
    4: "RANGES",
    5: "SUMMARY",
    6: "FORMAT",
    7: "TRANSACTION_DESCRIPTION",
    8: "EXTERNAL_FILE_DESCRIPTION"
}

def list_tables(db_alias: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista todas as tabelas de usuário (não de sistema) do banco especificado."""
    sql = """
        SELECT TRIM(RDB$RELATION_NAME) AS TABLE_NAME,
               RDB$RELATION_TYPE AS TABLE_TYPE
        FROM RDB$RELATIONS
        WHERE (RDB$SYSTEM_FLAG = 0 OR RDB$SYSTEM_FLAG IS NULL)
          AND RDB$VIEW_BLR IS NULL
        ORDER BY RDB$RELATION_NAME
    """
    with connection_manager.get_connection(db_alias) as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        tables = []
        for row in cursor.fetchall():
            tables.append({
                "table_name": row[0],
                "type": "TABLE"
            })
        return tables

def list_views(db_alias: Optional[str] = None) -> List[str]:
    """Lista todas as views de usuário do banco especificado."""
    sql = """
        SELECT TRIM(RDB$RELATION_NAME) AS VIEW_NAME
        FROM RDB$RELATIONS
        WHERE (RDB$SYSTEM_FLAG = 0 OR RDB$SYSTEM_FLAG IS NULL)
          AND RDB$VIEW_BLR IS NOT NULL
        ORDER BY RDB$RELATION_NAME
    """
    with connection_manager.get_connection(db_alias) as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        return [row[0] for row in cursor.fetchall()]

def list_procedures(db_alias: Optional[str] = None) -> List[str]:
    """Lista todas as stored procedures cadastradas no banco."""
    sql = """
        SELECT TRIM(RDB$PROCEDURE_NAME) AS PROC_NAME
        FROM RDB$PROCEDURES
        WHERE (RDB$SYSTEM_FLAG = 0 OR RDB$SYSTEM_FLAG IS NULL)
        ORDER BY RDB$PROCEDURE_NAME
    """
    with connection_manager.get_connection(db_alias) as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        return [row[0] for row in cursor.fetchall()]

def list_generators(db_alias: Optional[str] = None) -> List[str]:
    """Lista todos os generators / sequences de usuário."""
    sql = """
        SELECT TRIM(RDB$GENERATOR_NAME) AS GEN_NAME
        FROM RDB$GENERATORS
        WHERE (RDB$SYSTEM_FLAG = 0 OR RDB$SYSTEM_FLAG IS NULL)
        ORDER BY RDB$GENERATOR_NAME
    """
    with connection_manager.get_connection(db_alias) as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        return [row[0] for row in cursor.fetchall()]

def inspect_table(table_name: str, db_alias: Optional[str] = None) -> Dict[str, Any]:
    """
    Inspeciona detalhadamente uma tabela no Firebird:
    - Colunas, tipos exatos (incluindo DECFLOAT, INT128, BOOLEAN), domínios e nulidade
    - Chaves primárias (PK) e estrangeiras (FK)
    - Índices com seletividade real (RDB$STATISTICS).
    """
    table_upper = table_name.strip().upper()

    columns_sql = """
        SELECT TRIM(RF.RDB$FIELD_NAME) AS FIELD_NAME,
               F.RDB$FIELD_TYPE,
               F.RDB$FIELD_LENGTH,
               F.RDB$FIELD_SCALE,
               F.RDB$FIELD_SUB_TYPE,
               RF.RDB$NULL_FLAG,
               TRIM(F.RDB$FIELD_NAME) AS DOMAIN_NAME,
               F.RDB$FIELD_PRECISION
        FROM RDB$RELATION_FIELDS RF
        JOIN RDB$FIELDS F ON RF.RDB$FIELD_SOURCE = F.RDB$FIELD_NAME
        WHERE TRIM(RF.RDB$RELATION_NAME) = ?
        ORDER BY RF.RDB$FIELD_POSITION
    """

    indices_sql = """
        SELECT TRIM(I.RDB$INDEX_NAME) AS INDEX_NAME,
               I.RDB$UNIQUE_FLAG,
               I.RDB$STATISTICS,
               TRIM(S.RDB$FIELD_NAME) AS FIELD_NAME,
               S.RDB$FIELD_POSITION,
               I.RDB$INDEX_TYPE
        FROM RDB$INDICES I
        JOIN RDB$INDEX_SEGMENTS S ON I.RDB$INDEX_NAME = S.RDB$INDEX_NAME
        WHERE TRIM(I.RDB$RELATION_NAME) = ?
        ORDER BY I.RDB$INDEX_NAME, S.RDB$FIELD_POSITION
    """

    constraints_sql = """
        SELECT TRIM(RC.RDB$CONSTRAINT_NAME) AS CONSTRAINT_NAME,
               TRIM(RC.RDB$CONSTRAINT_TYPE) AS CONSTRAINT_TYPE,
               TRIM(RC.RDB$INDEX_NAME) AS INDEX_NAME,
               TRIM(REF.RDB$CONST_NAME_UQ) AS TARGET_UQ_NAME
        FROM RDB$RELATION_CONSTRAINTS RC
        LEFT JOIN RDB$REF_CONSTRAINTS REF ON RC.RDB$CONSTRAINT_NAME = REF.RDB$CONSTRAINT_NAME
        WHERE TRIM(RC.RDB$RELATION_NAME) = ?
    """

    with connection_manager.get_connection(db_alias) as conn:
        cursor = conn.cursor()

        # 1. Colunas
        cursor.execute(columns_sql, (table_upper,))
        columns = []
        for row in cursor.fetchall():
            field_name = row[0]
            type_code = row[1]
            length = row[2]
            scale = row[3]
            sub_type = row[4]
            not_null = (row[5] == 1)
            domain = row[6]
            precision = row[7]

            type_name = FIREBIRD_TYPE_MAP.get(type_code, f"UNKNOWN_{type_code}")

            # Detalhamento de tipos numéricos exatos (NUMERIC / DECIMAL)
            if scale and scale < 0 and type_code in (7, 8, 16, 26):
                num_kind = "DECIMAL" if sub_type == 2 else "NUMERIC"
                prec = precision if precision else length
                type_desc = f"{num_kind}({prec}, {abs(scale)})"
            elif type_code in (14, 37):  # CHAR, VARCHAR
                type_desc = f"{type_name}({length})"
            elif type_code == 261:  # BLOB
                blob_kind = BLOB_SUBTYPE_MAP.get(sub_type, f"SUB_TYPE_{sub_type}")
                type_desc = f"BLOB SUB_TYPE {blob_kind}"
            else:
                type_desc = type_name

            columns.append({
                "field_name": field_name,
                "type": type_desc,
                "nullable": not not_null,
                "domain": domain
            })

        # 2. Índices
        cursor.execute(indices_sql, (table_upper,))
        indices_dict = {}
        for row in cursor.fetchall():
            idx_name = row[0]
            if idx_name not in indices_dict:
                indices_dict[idx_name] = {
                    "index_name": idx_name,
                    "unique": (row[1] == 1),
                    "selectivity": float(row[2]) if row[2] is not None else None,
                    "order": "DESCENDING" if row[5] == 1 else "ASCENDING",
                    "fields": []
                }
            indices_dict[idx_name]["fields"].append(row[3])

        # 3. Constraints
        cursor.execute(constraints_sql, (table_upper,))
        constraints = []
        for row in cursor.fetchall():
            constraints.append({
                "constraint_name": row[0],
                "type": row[1],
                "index_name": row[2],
                "target_uq": row[3]
            })

        cfg = connection_manager.get_config(db_alias)
        return {
            "database_alias": cfg.alias,
            "database_file": cfg.database,
            "table_name": table_upper,
            "columns": columns,
            "indices": list(indices_dict.values()),
            "constraints": constraints
        }
