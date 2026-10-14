from typing import Dict, Any, Optional
from .connection import connection_manager

def get_database_health(db_alias: Optional[str] = None) -> Dict[str, Any]:
    """
    Coleta métricas de telemetria e integridade através das tabelas MON$
    (disponíveis a partir do Firebird 2.1+), com foco no gap OAT/OIT.
    """
    mon_db_sql = """
        SELECT MON$PAGE_SIZE,
               MON$ODS_MAJOR,
               MON$ODS_MINOR,
               MON$OLDEST_TRANSACTION,
               MON$OLDEST_ACTIVE,
               MON$OLDEST_SNAPSHOT,
               MON$NEXT_TRANSACTION,
               MON$SWEEP_INTERVAL
        FROM MON$DATABASE
    """

    mon_counts_sql = """
        SELECT (SELECT COUNT(*) FROM MON$ATTACHMENTS WHERE MON$SYSTEM_FLAG = 0) AS ATTACHMENTS,
               (SELECT COUNT(*) FROM MON$TRANSACTIONS) AS TRANSACTIONS,
               (SELECT COUNT(*) FROM MON$STATEMENTS) AS STATEMENTS
        FROM RDB$DATABASE
    """

    engine_version_sql = """
        SELECT rdb$get_context('SYSTEM', 'ENGINE_VERSION') FROM rdb$database
    """

    cfg = connection_manager.get_config(db_alias)

    with connection_manager.get_connection(db_alias) as conn:
        cursor = conn.cursor()

        # Engine Version (FB 2.5+)
        engine_version = "Unknown"
        try:
            cursor.execute(engine_version_sql)
            row = cursor.fetchone()
            if row and row[0]:
                engine_version = row[0]
        except Exception:
            engine_version = "Firebird 2.1 / 2.5 (context not available)"

        # MON$DATABASE
        cursor.execute(mon_db_sql)
        db_row = cursor.fetchone()

        page_size = db_row[0]
        ods_major = db_row[1]
        ods_minor = db_row[2]
        oldest_trans = db_row[3]
        oldest_active = db_row[4]
        oldest_snapshot = db_row[5]
        next_trans = db_row[6]
        sweep_interval = db_row[7]

        # MON counts
        cursor.execute(mon_counts_sql)
        counts_row = cursor.fetchone()
        attachments = counts_row[0]
        transactions = counts_row[1]
        statements = counts_row[2]

        conn.commit()

    # Cálculo do gap de transações
    oat_gap = (next_trans - oldest_active) if (next_trans is not None and oldest_active is not None) else 0

    warnings = []
    if oat_gap > 20000:
        warnings.append(
            f"ALERTA CRÍTICO: Gap OAT/Next Transaction muito alto ({oat_gap} transações)! "
            "Há transações antigas abertas impedindo o Garbage Collection. O banco corre sério risco de inchaço do .fdb."
        )
    elif oat_gap > 5000:
        warnings.append(
            f"Aviso de Atenção: Gap OAT em {oat_gap} transações. Monitore aplicações com telas ou relatórios abertos."
        )

    return {
        "database_alias": cfg.alias,
        "database_file": cfg.database,
        "engine_version": engine_version,
        "ods_version": f"{ods_major}.{ods_minor}",
        "page_size_bytes": page_size,
        "sweep_interval": sweep_interval,
        "transactions": {
            "oldest_interesting_transaction (OIT)": oldest_trans,
            "oldest_active_transaction (OAT)": oldest_active,
            "oldest_snapshot": oldest_snapshot,
            "next_transaction": next_trans,
            "oat_gap": oat_gap
        },
        "active_metrics": {
            "user_connections": attachments,
            "active_transactions": transactions,
            "active_statements": statements
        },
        "warnings": warnings,
        "is_healthy": len(warnings) == 0
    }
