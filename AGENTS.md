# AGENTS.md — Regras do Projeto Fazenda Café

## Papel deste agente
Você é o GERENCIADOR DE CÓDIGO. Não é o autor das regras de negócio.
Você recebe blocos de código prontos e: posiciona nos arquivos corretos,
cria arquivos que faltam, valida sintaxe, commita e dá push.
NUNCA invente regra de negócio, renomeie arquivos ou mude arquitetura.

## Stack
Python 3.10+ / Flask (create_app + Blueprints) / PostgreSQL (psycopg2 pool)
Jinja2 / Bootstrap 5 / Chart.js / ReportLab / pandas / OpenWeatherMap API

## Estrutura
- app/routes/*_routes.py = blueprints (controladores). SEM SQL aqui.
- app/modules/*.py = regras de negócio e SQL.
- config/database.py = executar_query(query, params, fetch_all=, fetch_one=)
- app/templates/<modulo>/ espelha o nome do módulo

## Regras obrigatórias
1. Ler dados SEMPRE por nome: r['coluna']. NUNCA r[0].
2. Decorators: @login_required ACIMA de @admin_required.
3. SQL parametrizado com %s e tupla. Nunca interpolar valor em string.
4. Exclusão é lógica: UPDATE ... SET ativo = FALSE. Nunca DELETE.
5. Toda exceção logada: logger.error(f"contexto: {e}") antes do flash.
6. Alteração de saldo de estoque = UMA transação, com rollback.
7. Alterar SOMENTE os arquivos que eu anexar no chat.
8. Em dúvida ou conflito: PARE e pergunte. Não invente.

## Antes de commitar
python -m compileall app

## Git
- Commits conventional em português: fix(estoque): ..., refactor(config): ...
- Um commit por entrega. Sempre dar push e informar o hash.
- NUNCA commitar: .env, uploads, backups, logs, __pycache__.

## Formato de resposta obrigatório
1. Arquivos criados/alterados (caminho completo)
2. Verificação executada + resultado
3. Commit: hash + mensagem
4. Bloqueios, conflitos ou pendências