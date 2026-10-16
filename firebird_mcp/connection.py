import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict, field
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
    projects: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_safe_dict(self) -> Dict[str, Any]:
        """Retorna os dados da conexão omitindo a senha."""
        d = asdict(self)
        d["password"] = "******" if self.password else ""
        return d


class FirebirdConnectionManager:
    """
    Gerenciador inteligente de conexões Firebird.
    Suporta:
    - Catálogo Central Global de bancos em ~/.firebird-mcp.json com metadados de projetos e tags
    - Precedência de configuração local (.firebird-mcp.json na raiz do projeto)
    - Filtragem automática de bancos baseada no contexto do projeto ativo (CWD)
    - Resolução inteligente de alias (exato, case-insensitive, substring e tags)
    - Proteção ativa com pergunta de confirmação quando houver múltiplos bancos no projeto
    - Direcionamento direto sem atrito em investigações pontuais
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
        self.is_global_config: bool = False
        
        # Inicializa tentando carregar do projeto ou do catálogo global
        self.reload_config()

    def get_global_config_path(self) -> Path:
        """Retorna o caminho padrão do catálogo central global (~/.firebird-mcp.json)."""
        return (Path.home() / ".firebird-mcp.json").resolve()

    def get_current_project(self) -> str:
        """Identifica o nome do projeto ativo a partir de variável de ambiente ou do diretório CWD."""
        return os.getenv("FIREBIRD_PROJECT") or Path.cwd().name

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
        """
        Carrega ou recarrega a configuração de bancos respeitando a hierarquia:
        1. Caminho explícito fornecido
        2. Variável de ambiente FIREBIRD_CONFIG_PATH
        3. Arquivo local no projeto (.firebird-mcp.json)
        4. Catálogo Central Global (~/.firebird-mcp.json)
        """
        self.databases.clear()
        self.config_file_loaded = None
        self.session_selected_alias = None
        self.default_alias = None
        self.is_global_config = False

        # 1. Tenta caminho explícito se fornecido
        config_path = Path(explicit_path) if explicit_path else None

        # 2. Se não fornecido, procura via variável de ambiente
        if not config_path:
            env_config = os.getenv("FIREBIRD_CONFIG_PATH")
            if env_config:
                candidate = Path(env_config)
                if candidate.is_file():
                    config_path = candidate

        # 3. Procura no projeto local (subindo até .git)
        if not config_path:
            config_path = self.find_project_config()

        # 4. Fallback para Catálogo Central Global no Home (~/.firebird-mcp.json)
        if not config_path:
            global_candidate = self.get_global_config_path()
            if global_candidate.is_file():
                config_path = global_candidate
                self.is_global_config = True

        if config_path and config_path.is_file():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self.config_file_loaded = str(config_path.resolve())
                if config_path.resolve() == self.get_global_config_path():
                    self.is_global_config = True

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
                            description=cfg.get("description"),
                            projects=cfg.get("projects", []),
                            tags=cfg.get("tags", [])
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
                        description=data.get("description", "Banco padrão do projeto"),
                        projects=data.get("projects", []),
                        tags=data.get("tags", [])
                    )
                    self.default_alias = "default"

                # Avalia os bancos aplicáveis ao projeto atual para decidir auto-seleção
                project_dbs = self.get_databases_for_project()
                if len(project_dbs) == 1:
                    only_alias = next(iter(project_dbs.keys()))
                    self.session_selected_alias = only_alias
                    self.default_alias = only_alias
                else:
                    self.session_selected_alias = None

            except Exception:
                # Se falhar ao ler o JSON, self.config_file_loaded permanece None
                pass

    def get_databases_for_project(self, project_name: Optional[str] = None) -> Dict[str, DatabaseConfig]:
        """
        Retorna os bancos de dados relevantes para o projeto especificado (ou CWD atual).
        Regra:
        - Se for arquivo local do projeto (!is_global_config): todos os bancos cadastrados pertencem a este projeto.
        - Se for catálogo global: banco é relevante se 'projects' contiver o projeto atual, '*' ou se 'projects' estiver vazio (compartilhado globalmente).
        """
        target_project = (project_name or self.get_current_project()).strip().lower()

        if not self.is_global_config:
            return self.databases.copy()

        result = {}
        for alias, cfg in self.databases.items():
            if not cfg.projects:
                # Banco compartilhado globalmente
                result[alias] = cfg
            elif "*" in cfg.projects:
                result[alias] = cfg
            elif any(p.strip().lower() == target_project for p in cfg.projects):
                result[alias] = cfg

        return result

    def resolve_alias(self, alias_or_hint: str) -> Optional[str]:
        """
        Busca inteligente de alias do banco:
        1. Casamento exato de chave
        2. Casamento exato case-insensitive
        3. Casamento por substring no alias
        4. Casamento por tag
        5. Casamento por substring na descrição
        """
        if not alias_or_hint:
            return None

        clean_hint = alias_or_hint.strip()

        # 1. Casamento exato
        if clean_hint in self.databases:
            return clean_hint

        hint_lower = clean_hint.lower()

        # 2. Case-insensitive exato
        for alias in self.databases:
            if alias.lower() == hint_lower:
                return alias

        # 3. Substring no alias
        matches = [alias for alias in self.databases if hint_lower in alias.lower()]
        if len(matches) == 1:
            return matches[0]

        # 4. Casamento por tag
        tag_matches = [
            alias for alias, cfg in self.databases.items()
            if any(hint_lower == t.strip().lower() for t in cfg.tags)
        ]
        if len(tag_matches) == 1:
            return tag_matches[0]

        # 5. Substring na descrição
        desc_matches = [
            alias for alias, cfg in self.databases.items()
            if cfg.description and hint_lower in cfg.description.lower()
        ]
        if len(desc_matches) == 1:
            return desc_matches[0]

        # Se houver múltiplos matches por substring, mas apenas um pertencer ao projeto atual
        if matches:
            project_dbs = self.get_databases_for_project()
            proj_matches = [m for m in matches if m in project_dbs]
            if len(proj_matches) == 1:
                return proj_matches[0]

        return None

    def save_to_file(self, target_filepath: Optional[str] = None) -> str:
        """Salva a configuração atual de bancos no arquivo JSON especificado, local ou catálogo global."""
        if target_filepath:
            path = Path(target_filepath).resolve()
        elif self.config_file_loaded:
            path = Path(self.config_file_loaded).resolve()
        else:
            path = self.get_global_config_path()

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
            if cfg.projects:
                db_dict["projects"] = cfg.projects
            if cfg.tags:
                db_dict["tags"] = cfg.tags
            data["databases"][alias] = db_dict

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.config_file_loaded = str(path)
        self.is_global_config = (path == self.get_global_config_path())
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
        projects: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        filepath: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cria e salva um novo arquivo de configuração (Catálogo Central Global por padrão)."""
        assigned_projects = projects if projects is not None else [self.get_current_project()]
        assigned_tags = tags if tags is not None else []

        cfg = DatabaseConfig(
            alias=alias,
            database=database,
            host=host,
            port=port,
            user=user,
            password=password,
            charset=charset,
            description=description or f"Banco de dados do projeto {self.get_current_project()}",
            projects=assigned_projects,
            tags=assigned_tags
        )
        self.databases[alias] = cfg
        self.session_selected_alias = alias
        self.default_alias = alias
        
        saved_path = self.save_to_file(filepath)
        return {
            "message": f"Arquivo de configuração criado com sucesso em '{saved_path}'.",
            "config_file": saved_path,
            "is_global_catalog": self.is_global_config,
            "active_database": alias,
            "database": cfg.to_safe_dict()
        }

    def get_config(self, db_alias: Optional[str] = None) -> DatabaseConfig:
        """
        Recupera a configuração do banco desejado.
        
        Regras de Negócio:
        1. Se não existir arquivo de configuração local (.firebird-mcp.json) nem catálogo central,
           interrompe e exige que sejam solicitados ao usuário os dados para criação do catálogo.
        2. Se db_alias foi informado ou indicado pelo usuário, resolve diretamente (inclusive por aproximação)
           e conecta SEM fazer perguntas redundantes.
        3. Se não houver db_alias especificado:
           - Se houver banco ativo na sessão (fb_use_database), utiliza-o.
           - Se o projeto atual tiver exatamente 1 banco correspondente, auto-seleciona.
           - Se o projeto atual tiver múltiplos bancos correspondentes, interrompe e exige que o usuário
             seja perguntado sobre em qual banco trabalhar.
        """
        # Regra 1: Validação de existência do arquivo
        if not self.config_file_loaded:
            raise FileNotFoundError(
                "Nenhum arquivo de configuração local (.firebird-mcp.json) ou Catálogo Central (~/.firebird-mcp.json) "
                "foi encontrado. Solicite ao usuário os dados de conexão do Firebird (caminho do banco .FDB, host, porta, "
                "usuário, senha, charset, alias e projetos) para criar o catálogo de bancos. "
                "Após receber os dados, utilize a ferramenta fb_create_config para salvar o arquivo."
            )

        if not self.databases:
            raise ValueError(
                f"O arquivo de configuração '{self.config_file_loaded}' foi encontrado, mas não contém nenhum banco configurado. "
                "Solicite os dados de conexão ao usuário para configurar o banco."
            )

        # Regra 2: Se o alias foi explicitamente passado ou mencionado:
        if db_alias:
            resolved = self.resolve_alias(db_alias)
            if not resolved or resolved not in self.databases:
                available = list(self.databases.keys())
                raise ValueError(
                    f"Banco de dados '{db_alias}' não encontrado no arquivo de configuração. "
                    f"Bancos disponíveis: {available}."
                )
            return self.databases[resolved]

        # Se há banco selecionado ativamente na sessão:
        if self.session_selected_alias and self.session_selected_alias in self.databases:
            return self.databases[self.session_selected_alias]

        # Regra 3: Filtragem contextual por projeto atual:
        project_dbs = self.get_databases_for_project()

        # Se há apenas 1 banco vinculado ao projeto atual: auto-seleção transparente
        if len(project_dbs) == 1:
            only_alias = next(iter(project_dbs.keys()))
            self.session_selected_alias = only_alias
            return project_dbs[only_alias]

        # Se há múltiplos bancos para o projeto atual: OBRIGATÓRIO perguntar ao usuário
        if len(project_dbs) > 1:
            available = list(project_dbs.keys())
            curr_proj = self.get_current_project()
            raise ValueError(
                f"Existem múltiplos bancos de dados associados ao projeto '{curr_proj}' ({available}). "
                "É OBRIGATÓRIO perguntar ao usuário em qual banco ele deseja trabalhar antes de executar "
                "qualquer operação genérica. Após a escolha do usuário, informe o parâmetro 'db_alias' ou "
                "defina o banco ativo através de fb_use_database."
            )

        # Se nenhum banco estiver associado especificamente ao projeto, lista todos os disponíveis
        available = list(self.databases.keys())
        raise ValueError(
            f"Nenhum banco está associado especificamente ao projeto '{self.get_current_project()}'. "
            f"Bancos disponíveis no catálogo: ({available}). "
            "É obrigatório perguntar ao usuário em qual banco trabalhar e definir via fb_use_database."
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

    def list_databases(self, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Lista todos os bancos configurados no projeto e no catálogo com status de seleção."""
        if not self.config_file_loaded:
            return {
                "status": "config_missing",
                "message": (
                    "Nenhum arquivo de configuração local (.firebird-mcp.json) ou Catálogo Central (~/.firebird-mcp.json) "
                    "foi encontrado. Solicite ao usuário os dados de conexão do Firebird (caminho .FDB, host, porta, "
                    "usuário, senha, charset e alias) para criação do arquivo."
                ),
                "config_file": None,
                "total_configured": 0,
                "databases": []
            }

        curr_project = (project_filter or self.get_current_project()).strip().lower()
        project_dbs = self.get_databases_for_project(curr_project)

        db_list = []
        for alias, cfg in self.databases.items():
            db_info = cfg.to_safe_dict()
            db_info["is_active"] = (alias == self.session_selected_alias)
            db_info["is_file_default"] = (alias == self.default_alias)
            db_info["is_project_match"] = (alias in project_dbs)
            db_list.append(db_info)

        has_multiple_in_project = len(project_dbs) > 1
        requires_selection = has_multiple_in_project and (self.session_selected_alias is None)

        msg = "Configuração carregada com sucesso."
        if requires_selection:
            msg = (
                f"Existem múltiplos bancos configurados para o projeto '{self.get_current_project()}' "
                f"({list(project_dbs.keys())}). É OBRIGATÓRIO perguntar ao usuário em qual banco trabalhar antes de executar comandos genéricos."
            )
        elif self.session_selected_alias:
            msg = f"Banco ativo na sessão: '{self.session_selected_alias}'."

        return {
            "status": "ok",
            "config_file": self.config_file_loaded,
            "is_global_catalog": self.is_global_config,
            "current_project": self.get_current_project(),
            "total_configured": len(self.databases),
            "project_databases_count": len(project_dbs),
            "active_database": self.session_selected_alias,
            "requires_selection": requires_selection,
            "message": msg,
            "databases": db_list
        }

    def set_default_database(self, alias: str) -> Dict[str, Any]:
        """Define o banco padrão/ativo para as consultas da sessão (suporta busca inteligente)."""
        if not self.config_file_loaded:
            raise FileNotFoundError(
                "Nenhum arquivo de configuração local ou catálogo central foi encontrado. "
                "Solicite ao usuário os dados para criação do arquivo."
            )

        resolved = self.resolve_alias(alias)
        if not resolved or resolved not in self.databases:
            raise ValueError(f"Banco '{alias}' não encontrado. Disponíveis: {list(self.databases.keys())}")

        self.session_selected_alias = resolved
        self.default_alias = resolved
        return {
            "message": f"Banco ativo definido com sucesso para '{resolved}'.",
            "active_database": self.databases[resolved].to_safe_dict()
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
        projects: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        set_as_default: bool = False,
        save_to_file: bool = True
    ) -> Dict[str, Any]:
        """Adiciona ou atualiza um banco dinamicamente no catálogo e persiste no arquivo."""
        existing = self.databases.get(alias)
        if projects is not None:
            assigned_projects = projects
        elif existing and existing.projects:
            assigned_projects = existing.projects
        else:
            assigned_projects = [self.get_current_project()]

        assigned_tags = tags if tags is not None else (existing.tags if existing else [])

        cfg = DatabaseConfig(
            alias=alias,
            database=database,
            host=host,
            port=port,
            user=user,
            password=password,
            charset=charset,
            description=description,
            projects=assigned_projects,
            tags=assigned_tags
        )
        self.databases[alias] = cfg
        
        if set_as_default or len(self.databases) == 1:
            self.session_selected_alias = alias
            self.default_alias = alias

        saved_path = None
        if save_to_file:
            saved_path = self.save_to_file()

        project_dbs = self.get_databases_for_project()
        return {
            "message": f"Banco '{alias}' configurado com sucesso." + (f" Arquivo salvo em '{saved_path}'." if saved_path else ""),
            "database": cfg.to_safe_dict(),
            "config_file": self.config_file_loaded,
            "is_global_catalog": self.is_global_config,
            "active_database": self.session_selected_alias,
            "requires_selection": (len(project_dbs) > 1 and self.session_selected_alias is None)
        }


# Instância singleton
connection_manager = FirebirdConnectionManager()
