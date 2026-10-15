import os
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from firebird_mcp.connection import FirebirdConnectionManager, DatabaseConfig


class TestFirebirdConnectionRules(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fb_test_")
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self.manager = FirebirdConnectionManager()

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_missing_config_file_behavior(self):
        """Regra 1: Quando não existir arquivo de configuração local, deve solicitar dados para criação."""
        self.assertIsNone(self.manager.config_file_loaded)
        
        # list_databases deve indicar que a configuração está ausente
        db_info = self.manager.list_databases()
        self.assertEqual(db_info["status"], "config_missing")
        self.assertIn("Nenhum arquivo de configuração local", db_info["message"])
        self.assertEqual(db_info["total_configured"], 0)

        # get_config sem arquivo deve lançar FileNotFoundError instruindo o agente a perguntar ao usuário
        with self.assertRaises(FileNotFoundError) as ctx:
            self.manager.get_config()
        self.assertIn("Nenhum arquivo de configuração local (.firebird-mcp.json) foi encontrado", str(ctx.exception))
        self.assertIn("Solicite ao usuário os dados de conexão do Firebird", str(ctx.exception))

    def test_create_config_file_success(self):
        """Criação do arquivo de configuração e operação com banco único."""
        result = self.manager.create_config_file(
            alias="meu_banco",
            database="/caminho/para/BANCO.FDB",
            host="127.0.0.1",
            port=3050,
            user="SYSDBA",
            password="masterkey",
            charset="WIN1252"
        )
        self.assertTrue(Path(result["config_file"]).is_file())
        self.assertEqual(result["active_database"], "meu_banco")
        self.assertEqual(self.manager.session_selected_alias, "meu_banco")

        # Com 1 único banco, get_config() deve funcionar direto
        cfg = self.manager.get_config()
        self.assertEqual(cfg.alias, "meu_banco")
        self.assertEqual(cfg.database, "/caminho/para/BANCO.FDB")

        # list_databases deve indicar 1 banco ativo sem necessidade de seleção
        info = self.manager.list_databases()
        self.assertEqual(info["status"], "ok")
        self.assertEqual(info["total_configured"], 1)
        self.assertFalse(info["requires_selection"])
        self.assertEqual(info["active_database"], "meu_banco")

    def test_multiple_databases_requires_user_prompt(self):
        """Regra 2: Quando no arquivo existir mais de um banco, sempre perguntar em qual banco trabalhar."""
        config_data = {
            "default": "principal",
            "databases": {
                "principal": {
                    "host": "localhost",
                    "port": 3050,
                    "database": "/dados/ERP_DADOS.FDB",
                    "user": "SYSDBA",
                    "password": "masterkey",
                    "charset": "WIN1252"
                },
                "auditoria": {
                    "host": "localhost",
                    "port": 3050,
                    "database": "/dados/ERP_AUDITORIA.FDB",
                    "user": "SYSDBA",
                    "password": "masterkey",
                    "charset": "WIN1252"
                }
            }
        }
        config_path = Path(self.test_dir) / ".firebird-mcp.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        # Recarrega a configuração a partir do arquivo criado
        self.manager.reload_config(str(config_path))
        self.assertEqual(self.manager.config_file_loaded, str(config_path.resolve()))
        self.assertEqual(len(self.manager.databases), 2)

        # session_selected_alias DEVE ser None inicialmente mesmo havendo 'default' no JSON
        self.assertIsNone(self.manager.session_selected_alias)

        # list_databases deve alertar que requer seleção do usuário
        info = self.manager.list_databases()
        self.assertTrue(info["requires_selection"])
        self.assertIn("Existem múltiplos bancos", info["message"])
        self.assertIn("É OBRIGATÓRIO perguntar ao usuário", info["message"])

        # Chamada sem db_alias deve lançar ValueError exigindo a pergunta ao usuário
        with self.assertRaises(ValueError) as ctx:
            self.manager.get_config()
        self.assertIn("Existem múltiplos bancos de dados configurados no arquivo", str(ctx.exception))
        self.assertIn("É OBRIGATÓRIO perguntar ao usuário", str(ctx.exception))

        # Chamada com db_alias explícito deve funcionar normalmente
        cfg_audit = self.manager.get_config(db_alias="auditoria")
        self.assertEqual(cfg_audit.database, "/dados/ERP_AUDITORIA.FDB")

        # Selecionando via set_default_database (após perguntar ao usuário)
        set_result = self.manager.set_default_database("auditoria")
        self.assertEqual(set_result["active_database"]["alias"], "auditoria")
        self.assertEqual(self.manager.session_selected_alias, "auditoria")

        # Agora get_config() sem db_alias deve retornar 'auditoria'
        cfg_now = self.manager.get_config()
        self.assertEqual(cfg_now.alias, "auditoria")

        # E list_databases não deve mais requerer seleção
        info_after = self.manager.list_databases()
        self.assertFalse(info_after["requires_selection"])
        self.assertEqual(info_after["active_database"], "auditoria")

    def test_configure_database_adds_second_db_and_persists(self):
        """Testa adição de um segundo banco via configure_database com persistência."""
        self.manager.create_config_file(
            alias="banco1",
            database="/dados/BANCO1.FDB"
        )
        self.assertEqual(len(self.manager.databases), 1)
        self.assertEqual(self.manager.session_selected_alias, "banco1")

        # Adiciona segundo banco sem set_as_default
        self.manager.configure_database(
            alias="banco2",
            database="/dados/BANCO2.FDB",
            save_to_file=True
        )
        self.assertEqual(len(self.manager.databases), 2)
        
        # Verifica se o arquivo salvo no disco contém ambos os bancos
        config_path = Path(self.manager.config_file_loaded)
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("banco1", data["databases"])
        self.assertIn("banco2", data["databases"])

    def test_server_tools_wrapper(self):
        """Testa as funções de alto nível expostas pelo servidor MCP."""
        from firebird_mcp.server import fb_create_config, fb_list_databases, fb_use_database, fb_configure_database, fb_reload_config

        # 1. Criação via fb_create_config
        res = fb_create_config(database="/dados/SISTEMA.FDB", alias="sistema")
        self.assertEqual(res["active_database"], "sistema")
        
        # 2. Listagem via fb_list_databases
        list_res = fb_list_databases()
        self.assertEqual(list_res["status"], "ok")
        self.assertEqual(list_res["total_configured"], 1)

        # 3. Adiciona segundo banco via fb_configure_database
        conf_res = fb_configure_database(alias="logs", database="/dados/LOGS.FDB")
        self.assertEqual(conf_res["database"]["alias"], "logs")

        # 4. Recarrega via fb_reload_config
        reload_res = fb_reload_config()
        self.assertEqual(reload_res["total_configured"], 2)
        self.assertTrue(reload_res["requires_selection"])

        # 5. Define ativo via fb_use_database
        use_res = fb_use_database("logs")
        self.assertEqual(use_res["active_database"]["alias"], "logs")


if __name__ == "__main__":
    unittest.main()

