# Manutenção de Código Fonte — 2026-10-16_configuracao-central-bancos

## Objetivo Técnico
Implementar a resolução hierárquica de configuração com Catálogo Central Global (`~/.firebird-mcp.json`), metadados de projetos e tags, filtragem automática de bancos por contexto de workspace/CWD e direcionamento direto em investigações pontuais.

## Arquivos / Units Afetados
- `firebird_mcp/connection.py` (`firebird_mcp/connection.py`):
  - Inclusão do campo `projects: List[str]` e `tags: List[str]` no `DatabaseConfig`.
  - Atualização do método `find_project_config()` para resolução hierárquica:
    1. Caminho explícito (`FIREBIRD_CONFIG_PATH` ou `--config`).
    2. Arquivo local do projeto (`.firebird-mcp.json` subindo até `.git`).
    3. Catálogo Global Central (`~/.firebird-mcp.json`).
  - Implementação de `get_context_databases(project_name: Optional[str] = None)` para filtrar os bancos associados ao projeto atual.
  - Implementação de resolução inteligente de aliases (match exato e por substring).
- `firebird_mcp/server.py` (`firebird_mcp/server.py`):
  - Parâmetros `projects` e `tags` em `fb_create_config` e `fb_configure_database`.
  - Exibição de contexto de projeto e status de seleção em `fb_list_databases`.
  - Suporte a seleção por substring em `fb_use_database`.
- `tests/test_connection_rules.py` (`tests/test_connection_rules.py`):
  - Novos testes unitários validando carga do catálogo global, fallback local, filtro por CWD e direcionamento direto.

## Métodos e Rotinas Alterados/Criados
- `DatabaseConfig`:
  - Adicionados campos `projects: List[str] = field(default_factory=list)` e `tags: List[str] = field(default_factory=list)`.
- `FirebirdConnectionManager.get_global_config_path()`:
  - Retorna `Path.home() / ".firebird-mcp.json"`.
- `FirebirdConnectionManager.get_active_project_name()`:
  - Extrai o nome do projeto a partir do `Path.cwd().name`.
- `FirebirdConnectionManager.list_databases_for_context()`:
  - Filtra bancos compatíveis com o projeto ativo e indica se requer seleção.

## Racional Técnico e Decisões de Arquitetura
1. **Hierarquia Limpa:** O desenvolvedor pode ter um único arquivo `~/.firebird-mcp.json` na sua máquina com 10, 20 ou 50 bancos catalogados e nunca mais precisar versionar senhas ou arquivos de conexão dentro dos repositórios git.
2. **Contexto sem Bloqueio:** Ao trabalhar em um projeto específico (ex: `web_projects`), o MCP reconhece o projeto automaticamente e só questiona entre os bancos que realmente pertencem àquele sistema.
3. **Direcionamento em Incidentes:** Se um desenvolvedor precisa consultar um banco de outro sistema (ex: `pdv_loja`), basta passar `db_alias="pdv_loja"` que o MCP conecta diretamente no catálogo global sem precisar alterar a pasta ou o projeto atual.
4. **Reconhecimento de Intenção Explícita no Prompt:** Quando o desenvolvedor especificar o banco diretamente no pedido (ex: "investigar bug no banco de auditoria"), o assistente deve direcionar a operação imediatamente para aquele banco (resolvendo por alias ou aproximação) sem emitir perguntas de confirmação.

## Checklist de Validação e Testes
- [x] Carregamento prioritário de `~/.firebird-mcp.json` quando não há arquivo local
- [x] Precedência do arquivo local `.firebird-mcp.json` quando explicitamente presente
- [x] Filtro correto de bancos baseado em `projects: ["..."]` comparado ao CWD
- [x] Bancos globais (sem `projects`) visíveis em qualquer contexto
- [x] Pergunta obrigatória de seleção quando o projeto atual possui múltiplos bancos e a consulta foi genérica
- [x] Auto-seleção transparente quando o projeto atual possui apenas 1 banco
- [x] Consulta direta para qualquer banco do catálogo global via `db_alias` ou quando o usuário indicar o banco no prompt
- [x] 100% dos testes unitários passando

## Sugestões de Melhoria Futura
- Comando CLI ou interface TUI/interativa para gerenciar o arquivo `~/.firebird-mcp.json` sem necessidade de editar o JSON manualmente.
- Suporte a agrupamento por ambiente (`producao`, `homologacao`, `desenvolvimento`).
