import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
import firebirdsql
from dotenv import load_dotenv

load_dotenv()

@dataclass
class DatabaseConfig:
    alias: str
    database: str
    host: str = "localhost"
    port: int = 3050
    user: str = "SYSDBA"
    password: str = "masterkey"
    charset: str = "WIN1252"
    description: Optional[str] = None

    def to_safe_dict(self) -> Dict[str, Any]:
        """Retorna os dados da conexão omitindo a senha."""
        d = asdict(self)
        d["password"] = "******" if self.password else ""
        return d


class FirebirdConnectionManager:
    """
    Gerenciador inteligente de conexões Firebird.
    Suporta:
    - Múltiplos bancos de dados por projeto (aliases)
    - Auto-discovery de configuração via arquivo .firebird-mcp.json na raiz do projeto (ou diretórios pais)
    - Fallback para variáveis de ambiente (.env ou MCP environment)
    - Suporte a todas as versões do Firebird (2.5, 3.0, 4.0 e 5.0) via protocolo nativo wire
    """

    CONFIG_FILENAMES = [
        ".firebird-mcp.json",
        "firebird-mcp.json",
        ".firebird.json",
        "firebird.config.json"
    ]

    def __init__(self):
        self.databases: Dict[str, DatabaseConfig] = {}
        self.default_alias: str = "default"
        self.config_file_loaded: Optional[str] = None
        
        # Inicializa tentando carregar do projeto ou de variáveis de ambiente
        self.reload_config()

    def find_project_config(self, start_dir: Optional[Path] = None) -> Optional[Path]:
        """Procura o arquivo de configuração subindo a árvore de diretórios a partir do CWD."""
        current = (start_dir or Path.cwd()).resolve()
        
        # Sobe até a raiz procurando o arquivo
        for parent in [current, *current.parents]:
            for config_name in self.CONFIG_FILENAMES:
                candidate = parent / config_name
                if candidate.is_file():
                    return candidate
        return None

    def reload_config(self, explicit_path: Optional[str] = None) -> None:
        """Carrega ou recarrega a configuração de bancos."""
        self.databases.clear()
        self.config_file_loaded = None

        # 1. Tenta caminho explícito se fornecido
        config_path = Path(explicit_path) if explicit_path else None

        # 2. Se não fornecido, procura no projeto
        if not config_path:
            env_config = os.getenv("FIREBIRD_CONFIG_PATH")
            if env_config:
                config_path = Path(env_config)
            else:
                config_path = self.find_project_config()

        if config_path and config_path.is_file():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self.config_file_loaded = str(config_path.resolve())

                # Se for um formato com "databases": { ... }
                if "databases" in data and isinstance(data["databases"], dict):
                    for alias, cfg in data["databases"].items():
                        self.databases[alias] = DatabaseConfig(
                            alias=alias,
                            database=cfg.get("database", ""),
                            host=cfg.get("host", "localhost"),
                            port=int(cfg.get("port", 3050)),
                            user=cfg.get("user", "SYSDBA"),
                            password=cfg.get("password", "masterkey"),
                            charset=cfg.get("charset", "WIN1252"),
                            description=cfg.get("description")
                        )
                    if "default" in data and data["default"] in self.databases:
                        self.default_alias = data["default"]
                    elif self.databases:
                        self.default_alias = next(iter(self.databases.keys()))
                
                # Se for um formato de banco único direto no JSON: { "database": "...", "host": ... }
                elif "database" in data:
                    self.databases["default"] = DatabaseConfig(
                        alias="default",
                        database=data.get("database", ""),
                        host=data.get("host", "localhost"),
                        port=int(data.get("port", 3050)),
                        user=data.get("user", "SYSDBA"),
                        password=data.get("password", "masterkey"),
                        charset=data.get("charset", "WIN1252"),
                        description=data.get("description", "Banco padrão do projeto")
                    )
                    self.default_alias = "default"

            except Exception as e:
                # Registra o erro mas não quebra para permitir fallback para env
                pass

        # 3. Fallback / Adição via Variáveis de Ambiente caso não haja banco configurado
        env_db = os.getenv("FIREBIRD_DATABASE", "")
        if env_db and "default" not in self.databases:
            self.databases["default"] = DatabaseConfig(
                alias="default",
                database=env_db,
                host=os.getenv("FIREBIRD_HOST", "localhost"),
                port=int(os.getenv("FIREBIRD_PORT", "3050")),
                user=os.getenv("FIREBIRD_USER", "SYSDBA"),
                password=os.getenv("FIREBIRD_PASSWORD", "masterkey"),
                charset=os.getenv("FIREBIRD_CHARSET", "WIN1252"),
                description="Configurado via variáveis de ambiente"
            )
            if not self.default_alias or self.default_alias not in self.databases:
                self.default_alias = "default"

    def get_config(self, db_alias: Optional[str] = None) -> DatabaseConfig:
        """Recupera a configuração do banco desejado ou do default."""
        target_alias = db_alias or self.default_alias

        if not target_alias or target_alias not in self.databases:
            available = list(self.databases.keys())
            raise ValueError(
                f"Banco de dados '{target_alias}' não encontrado. "
                f"Bancos disponíveis: {available if available else 'Nenhum'}. "
                "Crie o arquivo .firebird-mcp.json na raiz do projeto ou configure via fb_configure_database."
            )

        return self.databases[target_alias]

    def get_connection(self, db_alias: Optional[str] = None):
        """Abre uma conexão com o banco de dados especificado pelo alias (ou default)."""
        cfg = self.get_config(db_alias)
        
        if not cfg.database:
            raise ValueError(f"O banco de dados '{cfg.alias}' não possui o caminho do arquivo .FDB configurado.")

        return firebirdsql.connect(
            host=cfg.host,
            port=cfg.port,
            database=cfg.database,
            user=cfg.user,
            password=cfg.password,
            charset=cfg.charset
        )

    def list_databases(self) -> Dict[str, Any]:
        """Lista todos os bancos configurados no projeto e o ativo."""
        db_list = []
        for alias, cfg in self.databases.items():
            db_info = cfg.to_safe_dict()
            db_info["is_default"] = (alias == self.default_alias)
            db_list.append(db_info)

        return {
            "config_file": self.config_file_loaded or "Nenhum arquivo .firebird-mcp.json encontrado (usando memória/ambiente)",
            "default_database": self.default_alias,
            "total_configured": len(self.databases),
            "databases": db_list
        }

    def set_default_database(self, alias: str) -> Dict[str, Any]:
        """Define o banco padrão para as consultas."""
        if alias not in self.databases:
            raise ValueError(f"Banco '{alias}' não cadastrado. Disponíveis: {list(self.databases.keys())}")
        self.default_alias = alias
        return {
            "message": f"Banco padrão alterado com sucesso para '{alias}'.",
            "active_database": self.get_config(alias).to_safe_dict()
        }

    def configure_database(
        self,
        alias: str,
        database: str,
        host: str = "localhost",
        port: int = 3050,
        user: str = "SYSDBA",
        password: str = "masterkey",
        charset: str = "WIN1252",
        description: Optional[str] = None,
        set_as_default: bool = False
    ) -> Dict[str, Any]:
        """Adiciona ou atualiza um banco dinamicamente na sessão do MCP."""
        cfg = DatabaseConfig(
            alias=alias,
            database=database,
            host=host,
            port=port,
            user=user,
            password=password,
            charset=charset,
            description=description
        )
        self.databases[alias] = cfg
        if set_as_default or len(self.databases) == 1:
            self.default_alias = alias

        return {
            "message": f"Banco '{alias}' configurado com sucesso.",
            "database": cfg.to_safe_dict(),
            "is_default": (self.default_alias == alias)
        }


# Instância singleton
connection_manager = FirebirdConnectionManager()
