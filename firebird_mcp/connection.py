import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
import firebirdsql
from dotenv import load_dotenv

load_dotenv()

# Correção cirúrgica para firebirdsql: garante encerramento imediato de transações
# sem reter o OAT e evita 'cannot disconnect database with open transactions (1 active)'
_orig_connection_exit = firebirdsql.fbcore.Connection.__exit__
def _safe_connection_exit(self, exc, val, tb):
    if getattr(self, "_transaction", None) and getattr(self._transaction, "_trans_handle", None) is not None:
        self._transaction.is_dirty = True
    return _orig_connection_exit(self, exc, val, tb)
firebirdsql.fbcore.Connection.__exit__ = _safe_connection_exit

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
        self.default_alias: Optional[str] = None
        self.session_selected_alias: Optional[str] = None
        self.config_file_loaded: Optional[str] = None
        
        # Inicializa tentando carregar do projeto
        self.reload_config()

    def find_project_config(self, start_dir: Optional[Path] = None) -> Optional[Path]:
        """Procura o arquivo de configuração local no diretório atual ou subindo até a raiz do projeto (.git)."""
        current = (start_dir or Path.cwd()).resolve()
        
        curr = current
        while True:
            for config_name in self.CONFIG_FILENAMES:
                candidate = curr / config_name
                if candidate.is_file():
                    return candidate
            if (curr / ".git").exists() or curr.parent == curr:
                break
            curr = curr.parent
        return None

    def reload_config(self, explicit_path: Optional[str] = None) -> None:
        """Carrega ou recarrega a configuração de bancos a partir de arquivo local."""
        self.databases.clear()
        self.config_file_loaded = None
        self.session_selected_alias = None
        self.default_alias = None

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

                # Define o alias ativo caso haja apenas 1 banco
                if len(self.databases) == 1:
                    only_alias = next(iter(self.databases.keys()))
                    self.session_selected_alias = only_alias
                    self.default_alias = only_alias
                elif len(self.databases) > 1:
                    # Quando há múltiplos bancos no arquivo, session_selected_alias fica None
                    # para OBRIGAR a pergunta ao usuário sobre em qual banco trabalhar.
                    self.session_selected_alias = None

            except Exception:
                # Se falhar ao ler o JSON, self.config_file_loaded permanece None
                pass

    def save_to_file(self, target_filepath: Optional[str] = None) -> str:
        """Salva a configuração atual de bancos no arquivo .firebird-mcp.json."""
        if target_filepath:
            path = Path(target_filepath).resolve()
        elif self.config_file_loaded:
            path = Path(self.config_file_loaded).resolve()
        else:
            path = (Path.cwd() / ".firebird-mcp.json").resolve()

        default_to_save = (
            self.session_selected_alias
            or self.default_alias
            or (next(iter(self.databases.keys())) if self.databases else "principal")
        )

        data: Dict[str, Any] = {
            "default": default_to_save,
            "databases": {}
        }

        for alias, cfg in self.databases.items():
            db_dict: Dict[str, Any] = {
                "host": cfg.host,
                "port": cfg.port,
                "database": cfg.database,
                "user": cfg.user,
                "password": cfg.password,
                "charset": cfg.charset
            }
            if cfg.description:
                db_dict["description"] = cfg.description
            data["databases"][alias] = db_dict

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.config_file_loaded = str(path)
        return str(path)

    def create_config_file(
        self,
        database: str,
        alias: str = "principal",
        host: str = "localhost",
        port: int = 3050,
        user: str = "SYSDBA",
        password: str = "masterkey",
        charset: str = "WIN1252",
        description: Optional[str] = None,
        filepath: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cria e salva um novo arquivo de configuração local (.firebird-mcp.json)."""
        cfg = DatabaseConfig(
            alias=alias,
            database=database,
            host=host,
            port=port,
            user=user,
            password=password,
            charset=charset,
            description=description or "Banco de dados principal do projeto"
        )
        self.databases[alias] = cfg
        self.session_selected_alias = alias
        self.default_alias = alias
        
        saved_path = self.save_to_file(filepath)
        return {
            "message": f"Arquivo de configuração criado com sucesso em '{saved_path}'.",
            "config_file": saved_path,
            "active_database": alias,
            "database": cfg.to_safe_dict()
        }

    def get_config(self, db_alias: Optional[str] = None) -> DatabaseConfig:
        """
        Recupera a configuração do banco desejado.
        
        Regras de Negócio:
        1. Se não existir arquivo de configuração local (.firebird-mcp.json), interrompe e exige
           que sejam solicitados ao usuário os dados para criação do arquivo.
        2. Se existirem múltiplos bancos configurados no arquivo e nenhum alias foi especificado
           nem selecionado na sessão (via fb_use_database), interrompe e exige que seja perguntado
           ao usuário em qual banco trabalhar.
        """
        # Regra 1: Validação de existência do arquivo local
        if not self.config_file_loaded:
            raise FileNotFoundError(
                "Nenhum arquivo de configuração local (.firebird-mcp.json) foi encontrado no projeto. "
                "Solicite ao usuário os dados de conexão do Firebird (caminho do banco .FDB, host, porta, "
                "usuário, senha, charset e alias) para criação do arquivo de configuração local. "
                "Após receber os dados, utilize a ferramenta fb_create_config para salvar o arquivo no projeto."
            )

        if not self.databases:
            raise ValueError(
                f"O arquivo de configuração '{self.config_file_loaded}' foi encontrado, mas não contém nenhum banco configurado. "
                "Solicite os dados de conexão ao usuário para configurar o banco."
            )

        # Se o alias foi explicitamente passado na chamada:
        if db_alias:
            if db_alias not in self.databases:
                available = list(self.databases.keys())
                raise ValueError(
                    f"Banco de dados '{db_alias}' não encontrado no arquivo de configuração. "
                    f"Bancos disponíveis: {available}."
                )
            return self.databases[db_alias]

        # Se há exatamente 1 banco configurado, ele é utilizado diretamente sem ambiguidade
        if len(self.databases) == 1:
            return next(iter(self.databases.values()))

        # Se há múltiplos bancos e um foi selecionado explicitamente na sessão via fb_use_database:
        if self.session_selected_alias and self.session_selected_alias in self.databases:
            return self.databases[self.session_selected_alias]

        # Regra 2: Há múltiplos bancos configurados e nenhum foi selecionado -> OBRIGATÓRIO perguntar ao usuário
        available = list(self.databases.keys())
        raise ValueError(
            f"Existem múltiplos bancos de dados configurados no arquivo ({available}). "
            "É OBRIGATÓRIO perguntar ao usuário em qual banco ele deseja trabalhar antes de executar "
            "qualquer operação. Após a escolha do usuário, informe o parâmetro 'db_alias' ou "
            "defina o banco ativo através de fb_use_database."
        )

    def get_connection(self, db_alias: Optional[str] = None):
        """Abre uma conexão com o banco de dados especificado pelo alias (ou ativo na sessão)."""
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
        """Lista todos os bancos configurados no projeto e o status da seleção."""
        if not self.config_file_loaded:
            return {
                "status": "config_missing",
                "message": (
                    "Nenhum arquivo de configuração local (.firebird-mcp.json) foi encontrado no projeto. "
                    "Solicite ao usuário os dados de conexão do Firebird (caminho do arquivo .FDB, host, porta, "
                    "usuário, senha, charset e alias) para criação do arquivo local."
                ),
                "config_file": None,
                "total_configured": 0,
                "databases": []
            }

        db_list = []
        for alias, cfg in self.databases.items():
            db_info = cfg.to_safe_dict()
            db_info["is_active"] = (alias == self.session_selected_alias)
            db_info["is_file_default"] = (alias == self.default_alias)
            db_list.append(db_info)

        has_multiple = len(self.databases) > 1
        requires_selection = has_multiple and (self.session_selected_alias is None)

        msg = "Configuração carregada com sucesso."
        if requires_selection:
            msg = (
                f"Existem múltiplos bancos configurados no arquivo ({list(self.databases.keys())}). "
                "É OBRIGATÓRIO perguntar ao usuário em qual banco trabalhar antes de executar comandos."
            )
        elif self.session_selected_alias:
            msg = f"Banco ativo na sessão: '{self.session_selected_alias}'."

        return {
            "status": "ok",
            "config_file": self.config_file_loaded,
            "total_configured": len(self.databases),
            "active_database": self.session_selected_alias,
            "requires_selection": requires_selection,
            "message": msg,
            "databases": db_list
        }

    def set_default_database(self, alias: str) -> Dict[str, Any]:
        """Define o banco padrão/ativo para as consultas da sessão."""
        if not self.config_file_loaded:
            raise FileNotFoundError(
                "Nenhum arquivo de configuração local (.firebird-mcp.json) foi encontrado no projeto. "
                "Solicite ao usuário os dados para criação do arquivo."
            )

        if alias not in self.databases:
            raise ValueError(f"Banco '{alias}' não cadastrado. Disponíveis: {list(self.databases.keys())}")

        self.session_selected_alias = alias
        self.default_alias = alias
        return {
            "message": f"Banco ativo definido com sucesso para '{alias}'.",
            "active_database": self.databases[alias].to_safe_dict()
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
        set_as_default: bool = False,
        save_to_file: bool = True
    ) -> Dict[str, Any]:
        """Adiciona ou atualiza um banco dinamicamente no MCP e opcionalmente persiste no arquivo local."""
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
            self.session_selected_alias = alias
            self.default_alias = alias

        saved_path = None
        if save_to_file:
            saved_path = self.save_to_file()

        return {
            "message": f"Banco '{alias}' configurado com sucesso." + (f" Arquivo salvo em '{saved_path}'." if saved_path else ""),
            "database": cfg.to_safe_dict(),
            "config_file": self.config_file_loaded,
            "active_database": self.session_selected_alias,
            "requires_selection": (len(self.databases) > 1 and self.session_selected_alias is None)
        }


# Instância singleton
connection_manager = FirebirdConnectionManager()
