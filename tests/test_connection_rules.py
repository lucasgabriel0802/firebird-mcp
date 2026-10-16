import os
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from firebird_mcp.connection import FirebirdConnectionManager, DatabaseConfig


class TestFirebirdConnectionRules(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fb_test_")
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self.fake_home = Path(self.test_dir) / "fake_home"
        self.fake_home.mkdir(parents=True, exist_ok=True)
        self.home_patcher = patch("pathlib.Path.home", return_value=self.fake_home)
        self.home_patcher.start()
        self.manager = FirebirdConnectionManager()

    def tearDown(self):
        self.home_patcher.stop()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_missing_config_file_behavior(self):
        """Regra 1: Quando não existir arquivo local nem catálogo global, deve solicitar dados para criação."""
        self.assertIsNone(self.manager.config_file_loaded)
        
        # list_databases deve indicar que a configuração está ausente
        db_info = self.manager.list_databases()
        self.assertEqual(db_info["status"], "config_missing")
        self.assertIn("Nenhum arquivo de configuração local", db_info["message"])
        self.assertEqual(db_info["total_configured"], 0)

        # get_config sem arquivo deve lançar FileNotFoundError instruindo o agente a perguntar ao usuário
        with self.assertRaises(FileNotFoundError) as ctx:
            self.manager.get_config()
        self.assertIn("Nenhum arquivo de configuração local", str(ctx.exception))
        self.assertIn("Solicite ao usuário os dados de conexão", str(ctx.exception))

    def test_create_config_file_success(self):
        """Criação do arquivo de configuração e operação com banco único."""
        target_file = Path(self.test_dir) / ".firebird-mcp.json"
        result = self.manager.create_config_file(
            alias="meu_banco",
            database="/caminho/para/BANCO.FDB",
            host="127.0.0.1",
            port=3050,
            user="SYSDBA",
            password="masterkey",
            charset="WIN1252",
            filepath=str(target_file)
        )
        self.assertTrue(target_file.is_file())
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

    def test_global_catalog_loading_and_fallback(self):
        """Testa o carregamento do Catálogo Central Global (~/.firebird-mcp.json)."""
        mock_home = Path(self.test_dir) / "fake_home"
        mock_home.mkdir(exist_ok=True)
        global_config = mock_home / ".firebird-mcp.json"
        
        catalog_data = {
            "databases": {
                "central_db": {
                    "host": "localhost",
                    "port": 3050,
                    "database": "/dados/GLOBAL.FDB",
                    "projects": ["fake_project"]
                }
            }
        }
        with open(global_config, "w", encoding="utf-8") as f:
            json.dump(catalog_data, f)

        # Mocka get_global_config_path e get_current_project
        with patch.object(self.manager, "get_global_config_path", return_value=global_config):
            with patch.object(self.manager, "get_current_project", return_value="fake_project"):
                self.manager.reload_config()
                self.assertEqual(self.manager.config_file_loaded, str(global_config.resolve()))
                self.assertTrue(self.manager.is_global_config)
                self.assertEqual(len(self.manager.databases), 1)

                # Auto-seleção transparente do banco único do projeto
                cfg = self.manager.get_config()
                self.assertEqual(cfg.alias, "central_db")
                self.assertEqual(cfg.database, "/dados/GLOBAL.FDB")

    def test_local_config_precedence_over_global_catalog(self):
        """O arquivo local do projeto deve ter precedência sobre o catálogo global."""
        mock_home = Path(self.test_dir) / "fake_home"
        mock_home.mkdir(exist_ok=True)
        global_config = mock_home / ".firebird-mcp.json"
        with open(global_config, "w", encoding="utf-8") as f:
            json.dump({"databases": {"db_global": {"database": "/dados/GLOBAL.FDB"}}}, f)

        local_config = Path(self.test_dir) / ".firebird-mcp.json"
        with open(local_config, "w", encoding="utf-8") as f:
            json.dump({"databases": {"db_local": {"database": "/dados/LOCAL.FDB"}}}, f)

        with patch.object(self.manager, "get_global_config_path", return_value=global_config):
            self.manager.reload_config()
            self.assertEqual(self.manager.config_file_loaded, str(local_config.resolve()))
            self.assertFalse(self.manager.is_global_config)
            self.assertIn("db_local", self.manager.databases)
            self.assertNotIn("db_global", self.manager.databases)

    def test_project_contextual_filtering_and_blocking(self):
        """Testa filtragem por projeto: auto-seleção se 1 banco, bloqueio se múltiplos."""
        config_data = {
            "databases": {
                "erp_principal": {
                    "database": "/dados/ERP_DADOS.FDB",
                    "projects": ["erp_app"],
                    "tags": ["financeiro"]
                },
                "erp_auditoria": {
                    "database": "/dados/ERP_AUDITORIA.FDB",
                    "projects": ["erp_app"],
                    "tags": ["logs"]
                },
                "pdv_caixa": {
                    "database": "/dados/PDV.FDB",
                    "projects": ["pdv_app"],
                    "tags": ["caixa"]
                },
                "banco_geral": {
                    "database": "/dados/GERAL.FDB",
                    "projects": []  # Banco compartilhado globalmente
                }
            }
        }
        config_path = Path(self.test_dir) / ".firebird-mcp.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        # Simula estar no projeto 'pdv_app'
        with patch.object(self.manager, "get_global_config_path", return_value=config_path):
            with patch.object(self.manager, "get_current_project", return_value="pdv_app"):
                self.manager.reload_config()
                
                # pdv_app tem pdv_caixa + banco_geral (compartilhado) = 2 bancos
                # Deve requerer seleção
                info = self.manager.list_databases()
                self.assertTrue(info["requires_selection"])
                self.assertEqual(info["project_databases_count"], 2)

                # Chamada sem alias deve levantar ValueError
                with self.assertRaises(ValueError) as ctx:
                    self.manager.get_config()
                self.assertIn("Existem múltiplos bancos de dados associados ao projeto", str(ctx.exception))

    def test_intelligent_alias_resolution_and_direct_investigation(self):
        """Testa busca inteligente de alias por aproximação e direcionamento direto."""
        config_data = {
            "databases": {
                "erp_principal": {
                    "database": "/dados/ERP_DADOS.FDB",
                    "projects": ["erp_app"],
                    "tags": ["financeiro", "vendas"]
                },
                "erp_auditoria_prod": {
                    "database": "/dados/AUDITORIA.FDB",
                    "projects": ["erp_app"],
                    "tags": ["logs", "seguranca"]
                },
                "pdv_loja1": {
                    "database": "/dados/PDV1.FDB",
                    "projects": ["pdv_app"],
                    "tags": ["frente_caixa"]
                }
            }
        }
        config_path = Path(self.test_dir) / ".firebird-mcp.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        with patch.object(self.manager, "get_global_config_path", return_value=config_path):
            with patch.object(self.manager, "get_current_project", return_value="erp_app"):
                self.manager.reload_config()

                # 1. Direcionamento direto para banco de outro projeto via db_alias
                cfg_pdv = self.manager.get_config(db_alias="pdv_loja1")
                self.assertEqual(cfg_pdv.database, "/dados/PDV1.FDB")

                # 2. Resolução inteligente por aproximação/substring ('auditoria' -> 'erp_auditoria_prod')
                cfg_audit = self.manager.get_config(db_alias="auditoria")
                self.assertEqual(cfg_audit.alias, "erp_auditoria_prod")

                # 3. Resolução por tag ('frente_caixa' -> 'pdv_loja1')
                cfg_tag = self.manager.get_config(db_alias="frente_caixa")
                self.assertEqual(cfg_tag.alias, "pdv_loja1")

                # 4. Ativação via set_default_database com aproximação
                set_res = self.manager.set_default_database("auditoria")
                self.assertEqual(set_res["active_database"]["alias"], "erp_auditoria_prod")
                self.assertEqual(self.manager.session_selected_alias, "erp_auditoria_prod")

                # 5. Agora chamadas sem db_alias usam o banco ativo
                cfg_active = self.manager.get_config()
                self.assertEqual(cfg_active.alias, "erp_auditoria_prod")

    def test_server_tools_wrapper_with_projects_and_tags(self):
        """Testa as ferramentas FastMCP com projetos e tags."""
        from firebird_mcp.server import fb_create_config, fb_list_databases, fb_use_database, fb_configure_database

        target_file = Path(self.test_dir) / ".firebird-mcp.json"

        # 1. Criação com projetos e tags
        res = fb_create_config(
            database="/dados/SISTEMA.FDB",
            alias="sistema_erp",
            projects=["web_projects", "desktop"],
            tags=["erp", "financeiro"],
            filepath=str(target_file)
        )
        self.assertEqual(res["active_database"], "sistema_erp")

        # 2. Configuração de segundo banco
        conf_res = fb_configure_database(
            alias="sistema_auditoria",
            database="/dados/LOGS.FDB",
            projects=["web_projects"],
            tags=["logs"]
        )
        self.assertEqual(conf_res["database"]["alias"], "sistema_auditoria")

        # 3. Seleção inteligente via fb_use_database com substring
        use_res = fb_use_database("auditoria")
        self.assertEqual(use_res["active_database"]["alias"], "sistema_auditoria")


if __name__ == "__main__":
    unittest.main()
