# Especificação de Requisitos — Regra Rígida de Dupla Confirmação para DDL e DML

**ID da Demanda:** `2026-10-16_regra-dupla-confirmacao-ddl-dml`  
**Data:** 16/10/2026  
**Responsável Analítico:** Requirements Copilot  
**Status:** Validado e Implementado  

---

## 1. MAPA DE DOMÍNIOS

| Domínio | Descrição | Nível de Confiança |
| :--- | :--- | :--- |
| **Segurança e Governança Operacional** | Proteção contra mutações acidentais, deleções indevidas ou alterações estruturais sem consentimento humano expresso. | **Alta** |
| **Execução Segura no Engine Firebird** | Execução e validação de comandos DDL (`CREATE`, `ALTER`, `DROP`, `RECREATE`) e DML (`INSERT`, `UPDATE`, `DELETE`, `EXECUTE PROCEDURE`). | **Alta** |
| **Interação Humano-Agente** | Fluxo de comunicação transparente em duas etapas (explicação com detalhamento de impacto prévio + confirmação explícita do usuário). | **Alta** |

---

## 2. MAPA DE STAKEHOLDERS

| Nome / Papel | Tipo | Requisitos que Defendem | Conflitos Identificados |
| :--- | :--- | :--- | :--- |
| **Desenvolvedor / DBA (Lucas)** | Usuário Final & Negócio | Garantia absoluta de que nenhum comando que altere dados ou o esquema do banco seja executado sem explicação clara, impacto visível e autorização expressa no chat. | Nenhum. |
| **Assistente de IA (Agente MCP / IDE)** | Técnico | Parâmetros claros (`confirmed: bool`), mensagens explicativas de bloqueio (`PermissionError`) e guias claros nos schemas e nas regras da IDE. | Nenhum. |

---

## 3. ESTRUTURA DE ÉPICOS

### Épico 1: Trava Rígida de Dupla Confirmação no Servidor MCP
- **Descrição:** Adicionar o parâmetro `confirmed: bool = False` nas ferramentas `fb_execute_dml` e `fb_execute_ddl`, bloqueando a execução caso `confirmed` não seja `True` e fornecendo orientações completas com alerta de riscos.
- **Complexidade:** **P** (Pequena — Validação de parâmetros, inspeção sintática de alto risco e lançamento de `PermissionError`).
- **Domínio:** Segurança e Governança Operacional.

### Épico 2: Diretrizes Comportamentais e Governança na IDE
- **Descrição:** Atualização dos schemas de ferramentas da IDE, instruções do MCP, regras globais de banco de dados (`database-safety.md`) e skill `firebird-master` para assegurar que todo agente apresente comando, objetivo, impacto e aguarde confirmação.
- **Complexidade:** **P** (Pequena — Documentação, schemas JSON e regras do assistente).
- **Domínio:** Interação Humano-Agente.

---

## 4. USER STORIES

### US01: Bloqueio Seguro de DML e DDL sem Confirmação Prévia
- **Card:** Como desenvolvedor/DBA, quero que o Firebird MCP bloqueie sumariamente qualquer comando de alteração estrutural (DDL) ou manipulação de dados (DML) caso não haja autorização expressa, para que meus dados em produção/homologação não sejam corrompidos ou perdidos acidentalmente.
- **Validação INVEST:**
  - **Independent:** PASS (Pode ser testado de forma desacoplada no módulo `analyzer`).
  - **Negotiable:** PASS (Mensagem e formato da exceção ajustados).
  - **Valuable:** PASS (Proteção crítica de integridade de dados).
  - **Estimable:** PASS (1 Story Point).
  - **Small:** PASS (Implementável e testável de forma cirúrgica).
  - **Testable:** PASS (100% testado via unit tests).
- **Critérios de Aceite (Gherkin):**
  ```gherkin
  Cenário: Bloqueio de DML quando confirmed=False
    Dado que uma ferramenta tenta executar fb_execute_dml com sql "DELETE FROM TABELA"
    E o parâmetro confirmed é False ou omitido
    Quando o analisador processar o comando
    Então deve interromper a execução levantando PermissionError
    E a mensagem deve instruir a apresentar comando, objetivo, impacto e solicitar confirmação

  Cenário: Bloqueio de DDL quando confirmed=False
    Dado que uma ferramenta tenta executar fb_execute_ddl com ddl "DROP TABLE TABELA"
    E o parâmetro confirmed é False ou omitido
    Quando o analisador processar a instrução
    Então deve interromper a execução levantando PermissionError com alerta de alto risco
  ```

### US02: Execução Autorizada após Dupla Confirmação
- **Card:** Como usuário, quero que o assistente me mostre o comando SQL/DDL, me explique o impacto e aguarde meu "sim", para que somente após meu consentimento o comando seja efetivamente executado no banco com `confirmed=True`.
- **Critérios de Aceite (Gherkin):**
  ```gherkin
  Cenário: Execução autorizada de DML
    Dado que o usuário confirmou expressamente a execução no chat
    Quando o assistente chamar fb_execute_dml com confirmed=True
    Então o comando deve ser executado com commit imediato e retornar affected_rows

  Cenário: Execução autorizada de DDL
    Dado que o usuário confirmou expressamente a execução no chat
    Quando o assistente chamar fb_execute_ddl com confirmed=True
    Então a instrução estrutural deve ser executada com commit explícito
  ```
