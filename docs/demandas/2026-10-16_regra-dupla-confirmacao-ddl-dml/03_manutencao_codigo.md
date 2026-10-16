# Registro de Manutenção Técnica — Regra Rígida de Dupla Confirmação para DDL e DML

**ID da Demanda:** `2026-10-16_regra-dupla-confirmacao-ddl-dml`  
**Data:** 16/10/2026  
**Status:** Concluído e Testado  

---

## 1. Arquivos Modificados e Criados

### Código Fonte:
- `firebird_mcp/analyzer.py`:
  - Assinatura de `execute_dml(sql, db_alias=None, confirmed=False)` e `execute_ddl(ddl, db_alias=None, confirmed=False)`.
  - Validações de comandos proibidos (SELECT em DML/DDL, DDL em DML, DML em DDL).
  - Bloqueio rígido com `PermissionError` caso `confirmed` seja falso, emitindo alerta para `UPDATE`/`DELETE` sem WHERE e `DROP`/`RECREATE`.
- `firebird_mcp/server.py`:
  - Atualização dos endpoints `@mcp.tool()` para `fb_execute_dml` e `fb_execute_ddl` expondo o parâmetro `confirmed: bool = False` e docstrings com diretrizes estritas.

### Testes Automatizados:
- `tests/test_safety_rules.py`:
  - 10 novos testes unitários cobrindo bloqueio de DML e DDL sem confirmação, alerta de alto risco sem WHERE, rejeição de SELECT/DDL/DML cruzados e execução com sucesso após confirmação.
- `tests/test_connection_rules.py`:
  - Isolamento de `Path.home()` nos testes para evitar contaminação do ambiente do usuário.

### Configurações de IDE e Agente:
- `/home/lucas/.gemini/antigravity-ide/mcp/firebird/fb_execute_dml.json`
- `/home/lucas/.gemini/antigravity-ide/mcp/firebird/fb_execute_ddl.json`
- `/home/lucas/.gemini/antigravity-ide/mcp/firebird/instructions.md`
- `/home/lucas/.gemini/config/rules/database-safety.md`
- `/home/lucas/.gemini/config/skills/firebird-master/SKILL.md`

### Documentação:
- `README.pt-BR.md` e `README.md`: Atualizados com seção de regra de segurança e parâmetros da tabela de ferramentas.

---

## 2. Checklist de Validação

- [x] Tentativa de rodar `fb_execute_dml` sem confirmação é bloqueada com `PermissionError`.
- [x] Tentativa de rodar `fb_execute_ddl` sem confirmação é bloqueada com `PermissionError`.
- [x] Alerta de alto risco emitido quando `DELETE` ou `UPDATE` não tem cláusula `WHERE`.
- [x] Alerta de alto risco emitido quando `DROP` ou `RECREATE` é invocado.
- [x] Execução de `fb_execute_dml` com `confirmed=True` roda com sucesso e efetua commit imediato.
- [x] Execução de `fb_execute_ddl` com `confirmed=True` roda com sucesso e efetua commit explícito.
- [x] 100% de aprovação na suíte de testes (`17/17 testes OK`).
