import unittest
from unittest.mock import MagicMock, patch

from firebird_mcp.analyzer import execute_dml, execute_ddl
from firebird_mcp.connection import DatabaseConfig, connection_manager


class TestSafetyRules(unittest.TestCase):
    def setUp(self):
        self.mock_config = DatabaseConfig(
            alias="teste_db",
            database="/dados/TESTE.FDB",
            host="127.0.0.1",
            port=3050,
            user="SYSDBA",
            password="masterkey",
            charset="WIN1252"
        )
        connection_manager.databases = {"teste_db": self.mock_config}
        connection_manager.session_selected_alias = "teste_db"

    def tearDown(self):
        connection_manager.databases = {}
        connection_manager.session_selected_alias = None

    def test_execute_dml_blocked_without_confirmation(self):
        """DML sem confirmed=True deve ser bloqueado com PermissionError e instruções."""
        sql = "DELETE FROM PEDIDOS WHERE ID = 10"
        with self.assertRaises(PermissionError) as ctx:
            execute_dml(sql=sql, db_alias="teste_db", confirmed=False)

        err_msg = str(ctx.exception)
        self.assertIn("BLOQUEIO DE SEGURANÇA", err_msg)
        self.assertIn("DUPLA CONFIRMAÇÃO OBRIGATÓRIA", err_msg)
        self.assertIn("DELETE FROM PEDIDOS WHERE ID = 10", err_msg)
        self.assertIn("O assistente DEVE apresentar ao usuário", err_msg)
        self.assertIn("confirmed=True", err_msg)

    def test_execute_dml_high_risk_alert_without_where(self):
        """DML UPDATE ou DELETE sem cláusula WHERE deve alertar alto risco."""
        sql = "DELETE FROM PEDIDOS"
        with self.assertRaises(PermissionError) as ctx:
            execute_dml(sql=sql, db_alias="teste_db", confirmed=False)

        err_msg = str(ctx.exception)
        self.assertIn("ALERTA DE ALTO RISCO", err_msg)
        self.assertIn("NÃO possui cláusula WHERE", err_msg)

    def test_execute_dml_rejects_ddl(self):
        """DML deve rejeitar comandos DDL e orientar para fb_execute_ddl."""
        with self.assertRaises(ValueError) as ctx:
            execute_dml("DROP TABLE CLIENTES", confirmed=True)
        self.assertIn("fb_execute_ddl", str(ctx.exception))

    def test_execute_dml_rejects_select(self):
        """DML deve rejeitar consultas SELECT e orientar para fb_query."""
        with self.assertRaises(ValueError) as ctx:
            execute_dml("SELECT * FROM CLIENTES", confirmed=True)
        self.assertIn("fb_query", str(ctx.exception))

    @patch("firebird_mcp.analyzer.connection_manager.get_connection")
    def test_execute_dml_success_with_confirmation(self, mock_get_conn):
        """DML com confirmed=True deve executar e efetuar commit com sucesso."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 3
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        res = execute_dml("UPDATE CLIENTES SET ATIVO = 'S' WHERE ID = 1", db_alias="teste_db", confirmed=True)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["affected_rows"], 3)
        self.assertIn("dupla confirmação", res["message"])
        mock_cursor.execute.assert_called_once_with("UPDATE CLIENTES SET ATIVO = 'S' WHERE ID = 1")
        mock_conn.commit.assert_called_once()

    def test_execute_ddl_blocked_without_confirmation(self):
        """DDL sem confirmed=True deve ser bloqueado com PermissionError e instruções."""
        ddl = "ALTER TABLE CLIENTES ADD CPF VARCHAR(14)"
        with self.assertRaises(PermissionError) as ctx:
            execute_ddl(ddl=ddl, db_alias="teste_db", confirmed=False)

        err_msg = str(ctx.exception)
        self.assertIn("BLOQUEIO DE SEGURANÇA", err_msg)
        self.assertIn("DUPLA CONFIRMAÇÃO OBRIGATÓRIA", err_msg)
        self.assertIn("ALTER TABLE CLIENTES ADD CPF VARCHAR(14)", err_msg)
        self.assertIn("confirmed=True", err_msg)

    def test_execute_ddl_high_risk_drop(self):
        """DDL com DROP deve emitir alerta explícito de irreversibilidade."""
        ddl = "DROP TABLE LOGS_SISTEMA"
        with self.assertRaises(PermissionError) as ctx:
            execute_ddl(ddl=ddl, db_alias="teste_db", confirmed=False)

        err_msg = str(ctx.exception)
        self.assertIn("ALERTA DE ALTO RISCO", err_msg)
        self.assertIn("DESTRUTIVO e IRREVERSÍVEL", err_msg)

    def test_execute_ddl_rejects_dml(self):
        """DDL deve rejeitar comandos DML e orientar para fb_execute_dml."""
        with self.assertRaises(ValueError) as ctx:
            execute_ddl("INSERT INTO CLIENTES (NOME) VALUES ('TESTE')", confirmed=True)
        self.assertIn("fb_execute_dml", str(ctx.exception))

    def test_execute_ddl_rejects_select(self):
        """DDL deve rejeitar consultas SELECT e orientar para fb_query."""
        with self.assertRaises(ValueError) as ctx:
            execute_ddl("SELECT * FROM TABELA", confirmed=True)
        self.assertIn("fb_query", str(ctx.exception))

    @patch("firebird_mcp.analyzer.connection_manager.get_connection")
    def test_execute_ddl_success_with_confirmation(self, mock_get_conn):
        """DDL com confirmed=True deve executar e efetuar commit com sucesso."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        ddl = "CREATE INDEX IDX_PEDIDOS_DATA ON PEDIDOS (DATA_EMISSAO)"
        res = execute_ddl(ddl=ddl, db_alias="teste_db", confirmed=True)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("dupla confirmação", res["message"])
        mock_cursor.execute.assert_called_once_with(ddl)
        mock_conn.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
