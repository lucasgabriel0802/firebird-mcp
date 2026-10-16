# Perguntas e Respostas — Regra de Dupla Confirmação para DDL e DML

**ID da Demanda:** `2026-10-16_regra-dupla-confirmacao-ddl-dml`  
**Data:** 16/10/2026  

---

### P01: Quais comandos se enquadram nesta regra rígida?
- **Resposta:** Todos os comandos estruturais DDL (`CREATE`, `ALTER`, `DROP`, `RECREATE`, `COMMENT`) e todos os comandos de manipulação/mutação de dados DML (`INSERT`, `UPDATE`, `DELETE`, `EXECUTE PROCEDURE` com alteração de registros, `MERGE`). Consultas de leitura pura (`SELECT`, `WITH`) permanecem liberadas em `fb_query` com limite seguro de linhas.

### P02: O que caracteriza a "dupla confirmação com explicação clara e impacto"?
- **Resposta:** O fluxo se divide em duas etapas obrigatórias:
  1. **Etapa 1 (Apresentação e Impacto pelo Assistente):**
     - O assistente exibe o comando exato que planeja executar.
     - Explica claramente o que o comando faz.
     - Detalha o impacto: linhas e tabelas afetadas, presença ou ausência de cláusula WHERE, risco de lock exclusivo de metadados, impacto no gap OAT/OIT, irreversibilidade de `DROP`.
     - Pergunta expressamente ao usuário se ele confirma a execução.
  2. **Etapa 2 (Autorização Humana e Execução):**
     - O assistente aguarda o usuário responder expressamente (ex: "sim", "confirmo", "pode executar").
     - Somente com a resposta afirmativa, executa a ferramenta com `confirmed=True`.

### P03: O que acontece se o assistente tentar chamar a ferramenta diretamente com `confirmed=False` ou sem parâmetro?
- **Resposta:** O servidor MCP levanta imediatamente uma exceção `PermissionError` bloqueando a transação. O erro contém um texto explicativo claro com o comando, banco afetado, alerta de riscos (ex: `UPDATE`/`DELETE` sem `WHERE` ou `DROP` de tabela) e orientações passo a passo para o assistente obter autorização prévia.

### P04: Como evitar que comandos incorretos sejam enviados para as ferramentas trocadas?
- **Resposta:** Foram implementadas validações cruzadas:
  - Comandos de leitura (`SELECT`/`WITH`) enviados para `fb_execute_dml` ou `fb_execute_ddl` são rejeitados com orientação para usar `fb_query`.
  - Comandos DDL enviados para `fb_execute_dml` são rejeitados com orientação para usar `fb_execute_ddl`.
  - Comandos DML enviados para `fb_execute_ddl` são rejeitados com orientação para usar `fb_execute_dml`.
