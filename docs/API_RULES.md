# Política e correções da API

## Plano aplicado

1. Proteger administração de usuários e alterações de inventário por perfil.
2. Vincular cada rota de empréstimo à ação que seu nome representa.
3. Validar equipamentos, motivos e transições antes de persistir alterações.
4. Distinguir duplicidade, referência inexistente e erros inesperados.
5. Normalizar datas em UTC na entrada, armazenamento e saída.
6. Completar as respostas, usar 204 sem corpo e configurar erros/CORS.
7. Atualizar e executar os testes de regressão. Instruções e limites da suíte em
   [test/README.md](../test/README.md).

## Acesso

- Cadastro (`POST /users`) e login são públicos. Cadastro sempre cria aluno inativo.
- Administradores podem listar, consultar por ID, ativar e desativar qualquer usuário.
- Gestores podem listar e consultar apenas alunos, incluindo os inativos. O filtro
  `active` continua disponível em `GET /users`.
- `GET /users/{user_id}` retorna 404 para registros inexistentes ou fora do escopo
  de consulta do gestor, sem expor dados de gestores e administradores.
- Gestores podem ativar/desativar apenas alunos; tentar alterar um gestor ou
  administrador retorna 403, inclusive quando o alvo é o próprio gestor.
- `PATCH /users/promote/{user_id}` é exclusivo do administrador e promove apenas
  alunos para gestor. Alvo inexistente retorna 404; alvo que já não é aluno, 409.
- Alunos não podem acessar as rotas de consulta/administração de usuários.
- As permissões também são verificadas no serviço. Promoção e alteração de status
  bloqueiam a linha do usuário até a gravação para serializar essas operações.
- Consultar equipamentos e categorias exige usuário autenticado e ativo.
- Criar/desativar equipamentos e criar/excluir categorias exige administrador.
  Gestores e alunos recebem 403 nessas operações.
- Consultas de equipamentos e categorias continuam disponíveis para todos os
  perfis autenticados e ativos. Ainda não há endpoints de edição; quando criados,
  também devem ser exclusivos do administrador.
- Todos solicitam empréstimos apenas para si. `requested_by` não é aceito na entrada.
- Alunos consultam apenas os próprios empréstimos; consulta alheia por ID retorna 404.
- Gestores e administradores consultam todos e podem avaliar os próprios empréstimos.
- `reviewed_by` sempre identifica o usuário autenticado que realizou a avaliação.

## Refresh tokens

Configure o prazo no `.env`, em dias inteiros positivos:

```dotenv
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

Reinicie a aplicação após alterar a configuração. O novo prazo vale para os
próximos logins; sessões existentes mantêm o vencimento já armazenado.

Antes de iniciar a aplicação atualizada, aplique a nova migração:

```bash
.venv/bin/alembic upgrade head
```

A revisão `c87e20a4bd61` cria `refresh_session` e `refresh_token`, sem modificar
os dados existentes. A migração não é executada automaticamente pela aplicação.
Seu downgrade remove essas duas tabelas e invalida todos os refresh tokens.

`POST /auth/login` mantém a entrada atual e passa a retornar:

```json
{
  "access_token": "<JWT>",
  "refresh_token": "<token aleatório>",
  "refresh_expires_at": "2026-10-12T12:00:00Z",
  "token_type": "bearer"
}
```

Para renovar, envie `POST /auth/refresh` com:

```json
{"refresh_token": "<último refresh token recebido>"}
```

- Não exige access token: autentica usando o refresh token do corpo.
- Retorna o mesmo formato do login, com **ambos os tokens novos**. O frontend
  deve substituir os dois e serializar renovações, sem chamadas simultâneas.
- A validade para renovação usa `JWT_REFRESH_TOKEN_EXPIRE_DAYS` (**7 dias desde
  o login** na configuração atual), em UTC. Rotação não
  estende esse prazo. Após o vencimento é necessário fazer login novamente.
- O access token mantém a duração de `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`; não passa
  a durar 7 dias. Access tokens antigos sem o campo `type` continuam compatíveis.
- Refresh tokens são aleatórios (256 bits), não JWTs. Apenas hashes SHA-256
  são persistidos. Não servem como Bearer nas rotas protegidas.
- Cada login cria uma sessão independente. Cada renovação consome o token anterior
  atomicamente. Reutilizar um token consumido revoga toda sua sessão de renovação,
  inclusive os tokens posteriores, mas não outras sessões do usuário.
- Token desconhecido, expirado ou revogado retorna 401 com `WWW-Authenticate: Bearer`.
  Corpo ausente ou inválido retorna 422. Usuário inativo retorna 403 e revoga a
  sessão apresentada. Usuário excluído perde os registros por `ON DELETE CASCADE`.
- Revogar a sessão de refresh não revoga JWTs de acesso já emitidos: estes expiram
  normalmente, mas continuam sujeitos à verificação do usuário ativo em cada chamada.
- Respostas de sucesso usam `Cache-Control: no-store` e `Pragma: no-cache`.
  Use HTTPS e não registre tokens em logs. A entrega continua em JSON, sem cookies.
- O histórico de hashes é mantido para detectar reutilização. Uma futura rotina
  de limpeza pode remover sessões expiradas; seus tokens são removidos em cascata.

A rotação e a detecção de reutilização seguem a orientação do
[RFC 9700, seção 4.14](https://www.rfc-editor.org/rfc/rfc9700.html#section-4.14).
O bloqueio transacional usa `SELECT FOR UPDATE` no MySQL; os testes SQLite não
substituem testes de concorrência nesse banco.

## Empréstimos

- A criação falha com 409 se qualquer equipamento não existir, estiver inativo
  ou já estiver reservado por um empréstimo em aberto. Nada é criado parcialmente.
- IDs devem ser positivos. Repetições são consolidadas em um único item.
- Aprovação e negativa são permitidas antes da retirada, incluindo reavaliações.
  Aprovação/reaprovação verifica a disponibilidade novamente, excluindo o próprio
  empréstimo da consulta de conflitos.
- Negativa exige motivo não vazio. Aprovação limpa o motivo anterior.
- Retirada exige aprovação, ausência de negativa e nenhuma retirada/devolução anterior.
- Devolução exige retirada e não pode ser repetida.
- Avaliação após retirada/devolução e demais transições inválidas retornam 409.
- Criação e alterações de estado bloqueiam os equipamentos em ordem de ID, antes
  de bloquear o empréstimo existente, até o commit/rollback (MySQL). A verificação
  de conflitos usa leitura com bloqueio para enxergar gravações concorrentes já
  confirmadas, mesmo sob REPEATABLE READ.

### Disponibilidade de equipamentos

- `GET /equipments?available=true` retorna somente equipamentos ativos sem vínculo
  com empréstimos aguardando análise, aguardando retirada, em uso ou atrasados.
- Negados e devolvidos não bloqueiam. As datas não participam dessa decisão:
  uma solicitação futura também reserva o equipamento imediatamente.
- A disponibilidade é calculada com `NOT EXISTS` nas tabelas existentes, sem
  coluna adicional, sem alterar `active` e sem consultas N+1.
- `GET /equipments` sem `available` mantém o inventário atual. `available=false`
  retorna os indisponíveis (inativos ou reservados). O filtro `active`, quando
  informado, é aplicado junto com `available`.
- O formato dos equipamentos e as permissões das rotas não mudaram. A negativa
  ou devolução libera o equipamento se ele continuar ativo e não houver outro
  empréstimo bloqueante. Conflitos antigos não são corrigidos automaticamente.
- Não é necessária migração. As alterações não foram validadas por execução de
  testes; a concorrência deve ser verificada em MySQL, não apenas SQLite.

#### Integração do frontend

No formulário de empréstimo, carregue as opções por
`GET /equipments?available=true`, com o Bearer token habitual. Não envie datas
para filtrar disponibilidade; elas continuam obrigatórias no `POST /loans`.
O corpo da criação permanece igual, incluindo `equipments: [id, ...]`.

Se criação ou aprovação retornar 409 com `equipment_ids`, destaque os IDs
indisponíveis, avise o usuário e atualize a lista. Não remova seleções
silenciosamente. Exemplo de erro:

```json
{
  "detail": "Equipment does not exist, is inactive or is already reserved: [12]",
  "equipment_ids": [12]
}
```

Atualize a lista após criar, negar ou devolver um empréstimo. Na tela de
inventário, continue usando `GET /equipments` sem o filtro de disponibilidade.

### Corpo das ações

- `PATCH /loans/allow/{loan_id}`: sem corpo ou `{}`.
- `PATCH /loans/deny/{loan_id}`: `{"reason": "Motivo da negativa"}`.
- `PATCH /loans/pickup/{loan_id}`: sem corpo ou `{}`.
- `PATCH /loans/close/{loan_id}`: sem corpo ou `{}`.

O antigo campo `type` continua aceito quando corresponde à rota. Valores contraditórios
retornam 422. Exemplos: `type=denied` em `/allow` e `type=returned` em `/pickup`.

## Datas e respostas

- Envie datas ISO 8601 com fuso, preferencialmente `Z`. Datas sem fuso são interpretadas
  como UTC por compatibilidade; datas com outro offset são convertidas para UTC.
- Colunas MySQL DATETIME armazenam UTC sem offset. Respostas incluem UTC com `Z`.
- Filtros de atraso e serialização usam o relógio UTC da aplicação.
- Dados históricos sem fuso são tratados como UTC; não há conversão automática de
  registros antigos que eventualmente tenham sido gravados no horário local.
- Apenas `GET /loans/{loan_id}` usa `LoanDetail` e retorna `equipments`, com
  `{ "id": ..., "name": ..., "category": { "id": ..., "name": ... } }`
  para cada equipamento vinculado, incluindo os que foram desativados.
- `GET /loans` e as respostas de criação/alteração usam `LoanRead`, sem
  `equipments`. Os demais campos, incluindo `requester`, `requested_by` e
  `status`, permanecem iguais.
- No detalhe, equipamentos são carregados com `selectinload` e suas categorias
  com `joinedload`, evitando consultas N+1. A listagem não carrega equipamentos.
- `LoanRead.requester` contém somente `{ "id": ..., "name": ... }`, mantendo
  `requested_by` por compatibilidade. Isso inclui `GET /loans` e
  `GET /loans/{loan_id}`, além das respostas que compartilham esse schema.
- Quem pode consultar o empréstimo recebe o nome atual do solicitante,
  independentemente do perfil atual dele. Isso não concede acesso adicional a
  `/users`: as restrições de consulta/administração de usuários permanecem iguais.
- Solicitantes são carregados em lote com `selectinload`, sem consulta individual
  por empréstimo, selecionando apenas `id` e `name`.
- `GET /equipments` retorna ativos e inativos com `active` explícito; use
  `?active=true` ou `?active=false` para filtrar.
- Ativação/desativação de usuários e exclusões retornam 204 sem corpo.
- Duplicidade retorna 409, recurso ausente 404 e falha inesperada 500 genérico.
- `debug` permanece desativado; detalhes inesperados são registrados apenas no servidor.

## CORS

Configure as origens do frontend no ambiente, como lista JSON:

```dotenv
CORS_ORIGINS=["http://localhost:5173","https://app.exemplo.com"]
```

Sem configuração, nenhuma origem externa é autorizada por CORS. Wildcard `*` é
rejeitado. A autenticação usa o cabeçalho Bearer; credenciais por cookie não estão
habilitadas no CORS.

As correções anteriores das rotas não exigiam migração; refresh tokens exigem a
migração descrita acima. O primeiro administrador precisa
existir previamente; o cadastro público não concede privilégios administrativos.
