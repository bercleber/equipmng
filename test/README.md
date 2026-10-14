# Testes

Execute a suíte completa na raiz do projeto:

```bash
.venv/bin/python -m pytest -q
```

Somente as rotas:

```bash
.venv/bin/python -m pytest test/endpoints -q
```

Os testes cobrem as 19 operações HTTP de autenticação, usuários, equipamentos,
categorias e empréstimos: sucesso, validação, permissões, identidade, filtros,
conflitos, registros inexistentes e transições de estado.

`conftest.py` configura credenciais exclusivas de teste antes de importar a
aplicação e bloqueia conexões do engine principal. Os testes de integração usam
um banco SQLite em memória por teste, com chaves estrangeiras habilitadas, e
restauram as dependências ao finalizar. Os testes de contrato existentes também
usam mocks de serviços/repositórios. Nenhuma migração é aplicada ao banco real.

`test_api_routes.py` mantém um inventário das rotas: se uma operação for adicionada
ou removida, atualize o inventário e os respectivos cenários. Isso não equivale a
100% de cobertura de linhas ou de combinações possíveis.

`test_refresh_tokens.py` cobre emissão, prazo absoluto de 7 dias, rotação,
reutilização, revogação, separação dos tokens de acesso e rollback.
`test_refresh_migration.py` executa upgrade/downgrade da nova migração em SQLite
e verifica a geração do SQL MySQL sem abrir conexão.

Limitação: SQLite não verifica particularidades do MySQL, a cadeia completa de migrações ou bloqueios
concorrentes de `SELECT FOR UPDATE`. Esses cenários exigem uma suíte separada com
uma instância MySQL descartável.
