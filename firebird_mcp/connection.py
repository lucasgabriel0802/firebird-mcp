import os
from typing import Optional, Dict, Any
import firebirdsql
from dotenv import load_dotenv

load_dotenv()

class FirebirdConnectionManager:
    """Gerencia a conexão com o banco de dados Firebird (versões 2.5 a 5.0)."""

    def __init__(self):
        self.host = os.getenv("FIREBIRD_HOST", "localhost")
        self.port = int(os.getenv("FIREBIRD_PORT", "3050"))
        self.database = os.getenv("FIREBIRD_DATABASE", "")
        self.user = os.getenv("FIREBIRD_USER", "SYSDBA")
        self.password = os.getenv("FIREBIRD_PASSWORD", "masterkey")
        self.charset = os.getenv("FIREBIRD_CHARSET", "WIN1252")

    def configure(
        self,
        database: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        charset: Optional[str] = None
    ) -> Dict[str, Any]:
        """Atualiza os parâmetros de conexão em tempo de execução."""
        if database is not None:
            self.database = database
        if host is not None:
            self.host = host
        if port is not None:
            self.port = port
        if user is not None:
            self.user = user
        if password is not None:
            self.password = password
        if charset is not None:
            self.charset = charset

        return self.get_config_summary()

    def get_config_summary(self) -> Dict[str, Any]:
        """Retorna o resumo da configuração atual (ocultando a senha)."""
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "charset": self.charset,
            "configured": bool(self.database)
        }

    def get_connection(self):
        """Abre e retorna uma conexão com o banco Firebird."""
        if not self.database:
            raise ValueError(
                "Banco de dados Firebird não configurado. "
                "Defina a variável FIREBIRD_DATABASE ou use a tool fb_configure_connection."
            )

        return firebirdsql.connect(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
            charset=self.charset
        )

# Instância singleton do gerenciador
connection_manager = FirebirdConnectionManager()
