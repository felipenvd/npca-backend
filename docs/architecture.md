# Arquitetura do site do NPCA

## 1. Objetivo

Este documento define a arquitetura inicial do novo site do NPCA (Núcleo de Pesquisa em Computação Aplicada). O sistema substituirá o frontend atual por uma aplicação Astro e terá um backend próprio em Django com Django Ninja.

Os objetivos principais são:

- oferecer boa performance, SEO e acessibilidade no site público;
- permitir que integrantes autorizados atualizem o conteúdo pelo Django Admin;
- separar claramente o frontend público, a API e a administração;
- facilitar desenvolvimento, testes, deploy e manutenção;
- executar todo o sistema no servidor do grupo de pesquisa usando Docker Compose;
- manter banco de dados, arquivos enviados e backups sob controle do grupo.

## 2. Decisões arquiteturais

### 2.1 Repositórios separados

O projeto não será um monorepo. Serão mantidos dois repositórios independentes:

1. `npca-frontend`: site público em Astro;
2. `npca-backend`: API, Django Admin, banco, mídia e orquestração Docker.

Os arquivos abaixo ficarão no repositório do backend, por ele concentrar os serviços persistentes e as operações de deploy:

```text
compose.yaml
compose.dev.yaml
compose.production.yaml
.env.example
```

No desenvolvimento e no servidor, os repositórios deverão ser clonados como diretórios irmãos:

```text
npca/
├── npca-backend/
└── npca-frontend/
```

Essa convenção permite que o Compose do backend utilize `../npca-frontend` como contexto de build do frontend. Caso futuramente sejam publicadas imagens em um registry, o Compose de produção poderá consumir as imagens prontas e deixar de depender da posição dos diretórios.

### 2.2 Site público separado do painel

O Astro será responsável somente pelo site público. O painel administrativo não será reconstruído no frontend.

O Django será responsável por:

- autenticação dos administradores;
- usuários, grupos e permissões;
- cadastro e edição do conteúdo;
- upload de imagens e documentos;
- persistência no PostgreSQL;
- API pública com Django Ninja.

### 2.3 Armazenamento local de mídia

Como o sistema ficará em um único servidor do grupo, não será utilizado S3 inicialmente. Os uploads serão armazenados pelo Django em `MEDIA_ROOT`, dentro de um volume persistente do Docker.

Em produção, o Django receberá os uploads, mas não será responsável por servir os arquivos de mídia. O proxy reverso deverá servir `/media/` diretamente a partir do volume, em modo somente leitura.

Essa decisão exige:

- volume persistente exclusivo para mídia;
- permissões corretas entre o container do backend e o proxy;
- backup recorrente do volume;
- validação de extensão, MIME type e tamanho dos uploads;
- monitoramento do espaço disponível no servidor.

Migrar para armazenamento S3 compatível continuará sendo possível no futuro sem alterar o modelo de dados público.

## 3. Tecnologias

### 3.1 Frontend

- Astro;
- TypeScript;
- Tailwind CSS;
- shadcn/ui;
- React somente para componentes interativos;
- temas claro e escuro, usando a preferência do sistema como escolha inicial;
- roteamento i18n nativo do Astro;
- português brasileiro e inglês;
- cliente TypeScript gerado a partir do OpenAPI;
- `openapi-typescript` e `openapi-fetch`;
- ESLint e Prettier.

O shadcn/ui utiliza componentes React. Componentes estruturais e sem interatividade deverão ser escritos preferencialmente em `.astro`. React e hidratação no navegador serão usados apenas quando agregarem comportamento real, por exemplo:

- menu móvel;
- dialog e drawer;
- carousel;
- combobox;
- filtros interativos.

### 3.2 Backend

- Python;
- Django;
- Django Unfold para a interface do painel administrativo;
- Django Ninja;
- nh3 para sanitização do HTML editorial;
- PostgreSQL;
- uv para gerenciamento de dependências e lockfile;
- Poe the Poet para comandos locais, Docker de desenvolvimento e CI;
- Pillow para processamento de imagens;
- Ruff para lint e formatação;
- pytest e pytest-django;
- servidor ASGI em produção.

### 3.3 Infraestrutura

- Docker;
- Docker Compose;
- Caddy como proxy reverso e terminador HTTPS;
- volumes Docker persistentes para PostgreSQL, mídia e arquivos estáticos do Django;
- GitHub Actions para validação dos dois repositórios;
- Sentry, ou solução equivalente, como evolução para monitoramento de erros.

## 4. Arquitetura de execução

O acesso externo deverá utilizar uma única origem:

```text
https://npca.example.br/          -> frontend Astro
https://npca.example.br/api/v1/   -> Django Ninja
https://npca.example.br/admin/    -> Django Admin
https://npca.example.br/media/    -> arquivos do MEDIA_ROOT
https://npca.example.br/static/   -> arquivos estáticos do Django Admin
```

O Caddy será o único serviço exposto publicamente nas portas HTTP e HTTPS. Frontend, backend e PostgreSQL deverão permanecer em uma rede interna do Compose.

```text
Internet
   |
   v
Caddy
   |-- / ----------------> Astro
   |-- /api/v1/ ---------> Django Ninja
   |-- /admin/ ----------> Django Admin
   |-- /media/ ----------> volume de mídia (somente leitura)
   `-- /static/ ---------> volume de staticfiles (somente leitura)

Django ------------------> PostgreSQL
```

Usar uma única origem reduz a configuração de CORS e simplifica cookies, CSRF e links de mídia.

## 5. Estrutura do frontend

Estrutura inicial sugerida para `npca-frontend`:

```text
npca-frontend/
├── public/
├── src/
│   ├── components/
│   │   ├── features/
│   │   ├── layout/
│   │   ├── sections/
│   │   └── ui/
│   ├── layouts/
│   ├── lib/
│   │   ├── api/
│   │   ├── env/
│   │   ├── i18n/
│   │   ├── theme/
│   │   └── utils/
│   ├── pages/
│   │   ├── index.astro
│   │   ├── noticias/
│   │   │   ├── index.astro
│   │   │   └── [slug].astro
│   │   ├── eventos/
│   │   ├── laboratorios/
│   │   ├── pesquisadores/
│   │   ├── projetos/
│   │   └── publicacoes/
│   └── styles/
├── tests/
├── .env.example
├── astro.config.mjs
├── Dockerfile
├── package.json
└── tsconfig.json
```

Os componentes devem ser organizados por responsabilidade, evitando páginas extensas que concentrem layout, dados e comportamento.

### 5.1 Estratégia de renderização

As páginas institucionais que mudam raramente poderão ser pré-renderizadas:

- página inicial estrutural;
- sobre o NPCA;
- contato;
- informações institucionais.

As rotas de conteúdo administrável deverão usar renderização sob demanda quando a publicação precisar aparecer imediatamente:

- notícias;
- eventos;
- projetos;
- publicações;
- pesquisadores;
- laboratórios.

O frontend usará o adapter Node do Astro. Durante a renderização no servidor, a API poderá ser acessada pelo endereço interno do Compose. Requisições feitas diretamente pelo navegador deverão utilizar `/api/v1/`.

### 5.2 Tema claro e escuro

O site oferecerá uma alternância direta entre os temas claro e escuro. Quando o
usuário ainda não tiver feito uma escolha, a preferência do sistema operacional será
usada automaticamente, sem aparecer como uma terceira opção na interface.

Não será adicionada inicialmente uma biblioteca equivalente ao `next-themes`. O Astro e o shadcn/ui permitem implementar o tema com um pequeno script inline no layout principal, executado antes da pintura da página. O script deverá:

- consultar a preferência salva no `localStorage`;
- usar `prefers-color-scheme` enquanto uma preferência explícita ainda não existir;
- aplicar a classe `.dark` no elemento `<html>` antes da renderização visual;
- observar mudanças na preferência do sistema;
- persistir somente a escolha explícita do usuário;
- evitar flash do tema incorreto durante o carregamento.

As cores serão definidas por tokens CSS semânticos para os dois temas. Componentes não deverão depender somente de cor para comunicar estado. O botão de tema terá rótulos acessíveis traduzidos nos dois idiomas.

### 5.3 Internacionalização

O site terá português brasileiro e inglês desde a primeira versão. Será utilizado o roteamento i18n nativo do Astro, sem uma biblioteca de tradução adicional no frontend.

As URLs terão o idioma explícito:

```text
/pt-br/
/pt-br/noticias/
/pt-br/noticias/{slug}/
/en/
/en/news/
/en/news/{slug}/
```

O idioma padrão será `pt-br` e todas as rotas, inclusive as do idioma padrão, terão prefixo. A raiz `/` redirecionará para o idioma adequado, com português brasileiro como fallback. O idioma presente na URL será a fonte de verdade; a preferência salva ou o idioma do navegador serão usados somente para auxiliar a primeira escolha.

Textos fixos da interface, como navegação, botões, mensagens vazias e labels, serão mantidos em dicionários TypeScript tipados dentro do frontend. Conteúdo editorial, como notícias, projetos e biografias, será traduzido e administrado no backend.

Cada página deverá configurar corretamente:

- atributo `lang` no HTML;
- título e descrição no idioma atual;
- URL canônica;
- links alternativos `hreflang` para `pt-BR` e `en`;
- opção `x-default` quando aplicável;
- seletor de idioma apontando para a tradução equivalente da página atual.

Não deverá ocorrer tradução automática no navegador. Quando uma tradução editorial não existir, a versão inglesa não deverá misturar silenciosamente conteúdo em português; a interface poderá ocultar o item ou informar que ele ainda não está disponível naquele idioma.

### 5.4 Navegação responsiva

O cabeçalho deverá priorizar a marca, os links principais e os controles de idioma e
tema. O nome institucional por extenso ficará no rodapé, nas páginas institucionais e
nos rótulos acessíveis, sem ocupar espaço permanente na barra de navegação.

Em desktop, a rota de conteúdo atual será indicada visualmente e com
`aria-current="page"`. Em telas menores, os links, a troca de idioma e o botão de tema
ficarão em um menu lateral acessível. O menu deverá usar semântica de diálogo, manter o
foco contido enquanto estiver aberto e permitir fechamento pelo botão, pela tecla
`Esc` e pelo fundo da página.

## 6. Estrutura do backend

Estrutura inicial sugerida para `npca-backend`:

```text
npca-backend/
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── asgi.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── core/
│   ├── events/
│   ├── laboratories/
│   ├── news/
│   ├── people/
│   ├── projects/
│   └── publications/
├── api/
│   └── v1/
│       └── router.py
├── tests/
├── .env.example
├── Dockerfile
├── compose.yaml
├── compose.dev.yaml
├── compose.production.yaml
├── manage.py
├── pyproject.toml
└── uv.lock
```

Cada app Django deverá manter seus próprios modelos, regras, admin, schemas, serviços e endpoints. O router principal da API apenas reunirá os routers das aplicações.

## 7. Django Admin

O Django Admin será o painel oficial de conteúdo do NPCA. Sua interface utilizará
Django Unfold com identidade visual do núcleo e temas claro e escuro, preservando
autenticação, sessões e permissões nativas do Django. A primeira versão não terá um
painel administrativo duplicado no Astro nem um dashboard customizado; indicadores
serão avaliados quando os módulos editoriais existirem.

O usuário administrativo continuará autenticando somente por e-mail e senha. A
primeira versão será operada por uma única conta administrativa individual, sem
workflow de Editor e Publicador. Novos grupos e permissões somente serão criados se
mais pessoas passarem a participar da operação editorial. Todos os `ModelAdmin`,
inclusive usuários e grupos, deverão herdar das classes do Unfold para que
formulários e widgets mantenham estilização consistente.

Os `ModelAdmin` deverão configurar, conforme o modelo:

- pesquisa;
- filtros;
- ordenação;
- campos somente leitura;
- geração e validação de slug;
- seleção de relacionamentos;
- ações em lote;
- preview de imagem;
- auditoria básica de criação e alteração.

Caso no futuro os editores precisem montar páginas livremente, usar preview editorial, revisões completas ou workflows mais sofisticados, deverá ser avaliado um CMS como Wagtail. Isso não faz parte do escopo inicial.

## 8. Modelagem inicial

### 8.1 Campos comuns de conteúdo

Os modelos publicáveis deverão compartilhar, quando aplicável:

- identificador interno;
- status (`draft`, `published`, `archived`);
- data de publicação;
- data de criação;
- data de atualização;
- usuário que criou;
- usuário que atualizou;

Campos editoriais traduzíveis não serão duplicados diretamente no modelo principal. Cada tipo de conteúdo terá uma entidade de tradução relacionada contendo idioma, slug, título, resumo, corpo e metadados de SEO quando aplicável.

### 8.2 Entidades

#### Notícia

- título;
- slug;
- resumo;
- conteúdo;
- imagem de capa;
- crédito da imagem;
- status e data de publicação;

#### Pesquisador

- nome;
- categoria acadêmica;
- foto;
- biografia;
- área de pesquisa;
- e-mail institucional;
- currículo Lattes;
- ORCID;
- LinkedIn;
- ativo/inativo;
- ordem de exibição.

#### Projeto

- status editorial (`draft`, `published` ou `archived`);
- situação acadêmica manual (`planned`, `ongoing` ou `completed`);
- capa decorativa e crédito opcionais;
- datas de início e término;
- um coordenador relacionado a Pesquisadores;
- equipe simples relacionada a Pesquisadores;
- financiamento e parceiros globais opcionais;
- site e repositório opcionais;
- destaque, ordem de exibição, publicação e auditoria;
- traduções com título, slug, resumo, descrição HTML e SEO.

#### Publicação

- título;
- autores relacionados;
- autores externos;
- resumo;
- ano;
- periódico ou evento;
- DOI;
- URL externa;
- arquivo, quando sua distribuição for permitida;
- projeto relacionado.

#### Evento

- título;
- slug;
- descrição;
- imagem;
- tipo;
- data e hora inicial;
- data e hora final;
- local ou URL;
- situação;
- inscrição externa.

#### Laboratório

- nome;
- sigla;
- slug;
- descrição;
- identidade visual;
- imagens;
- coordenação e equipe;
- projetos relacionados;
- links e contatos.

Relacionamentos reais devem ser usados no banco. Autores, coordenadores e membros não devem ser armazenados somente como texto quando corresponderem a pesquisadores cadastrados.

### 8.3 Traduções de conteúdo

Dados independentes de idioma permanecerão no modelo principal, por exemplo:

- datas;
- status estrutural;
- imagem de capa;
- relacionamentos;
- financiadores;
- DOI;
- URLs externas.

Dados localizados ficarão em registros de tradução, por exemplo:

- idioma;
- título ou nome exibido;
- slug;
- resumo;
- conteúdo ou biografia;
- texto alternativo de imagem, quando ela transmitir informação não descrita no conteúdo;
- título e descrição de SEO;
- título e descrição para SEO.

Deverá existir no máximo uma tradução por idioma para cada conteúdo. Slugs serão únicos dentro de cada idioma. O Django Admin exibirá as traduções de português e inglês de forma agrupada ou inline, sem obrigar o editor a duplicar os dados não traduzíveis.

Na primeira versão, a publicação será conjunta: português brasileiro e inglês
deverão estar completos antes que o conteúdo assuma o status `published`. O status e
a data de publicação ficarão no modelo principal. A API informará os slugs dos dois
idiomas para que o seletor encontre a página equivalente.

Notícias serão a primeira implementação desse padrão. Seu corpo utilizará o editor
visual simples do Unfold, sem imagens internas. O HTML será sanitizado no backend
com uma lista restrita de elementos de formatação antes de ser persistido e exposto
pela API. Como a capa é ilustrativa e sempre acompanha o título, ela será renderizada
com texto alternativo vazio e não exigirá preenchimento duplicado no Admin.

Pesquisadores serão a segunda implementação. Nome, categoria acadêmica, foto, e-mail,
links e ordem de exibição serão globais; área de pesquisa, slug, biografia e SEO serão
localizados. O perfil inativo poderá permanecer incompleto, mas sua ativação exigirá
as duas traduções completas. A foto usará automaticamente o nome completo do
pesquisador como texto alternativo, sem exigir preenchimento duplicado no Admin. A
biografia usará o mesmo editor visual limitado e a mesma sanitização de HTML adotada
em Notícias. O relacionamento com projetos será mantido pelo app de Projetos;
publicações e laboratórios adicionarão seus vínculos quando forem implementados.
Lattes, ORCID e LinkedIn serão incluídos também na listagem pública para permitir
atalhos opcionais nos cards.

A categoria acadêmica será obrigatória e usará os códigos estáveis `doctor`,
`doctoral_student`, `master`, `masters_student` e `undergraduate_researcher`. A
exibição seguirá essa prioridade, depois a ordem configurada dentro da categoria, o
nome e o ID. Os rótulos serão localizados pelo frontend.

Projetos serão a terceira implementação do padrão bilíngue. O status editorial será
independente da situação acadêmica, que será alterada manualmente. Rascunhos poderão
ficar incompletos; a publicação exigirá coordenador, início e traduções PT-BR e EN com
título, slug, resumo e descrição. Projetos concluídos também exigirão término, sempre
igual ou posterior ao início. A primeira publicação definirá `published_at`, preservado
em arquivamentos, retornos a rascunho e republicações.

Coordenador e equipe serão relacionados a Pesquisadores com proteção contra exclusão,
sem papéis ou ordem individuais. O coordenador não poderá ser repetido na equipe.
Pesquisadores inativos permanecerão identificados pelo nome na resposta pública, mas
sem URL de perfil ou foto. A capa será decorativa e validada pelo mecanismo compartilhado
de imagens. A descrição usará o editor visual limitado e a sanitização já adotada pelos
outros módulos. Financiamento e parceiros serão textos globais simples; não haverá
taxonomias, participantes externos, anexos ou mudança automática de situação nesta fase.

## 9. API

A API pública será versionada a partir de `/api/v1/`.

Rotas iniciais:

```text
GET /api/v1/news
GET /api/v1/news/{slug}
GET /api/v1/events
GET /api/v1/events/{slug}
GET /api/v1/laboratories
GET /api/v1/laboratories/{slug}
GET /api/v1/researchers
GET /api/v1/researchers/{slug}
GET /api/v1/projects
GET /api/v1/projects/{slug}
GET /api/v1/publications
GET /api/v1/publications/{id}
GET /api/v1/health
```

Endpoints de conteúdo exigirão explicitamente `lang=pt-br` ou `lang=en`. O idioma
explícito torna o comportamento previsível e permite cache por URL. Valores ausentes
ou inválidos serão tratados como erros de validação.

Somente conteúdo publicado poderá ser retornado pela API pública. Criação, edição e exclusão serão feitas pelo Django Admin, não por endpoints públicos de CRUD na primeira versão.

A API deverá oferecer:

- schemas explícitos de entrada e saída;
- paginação;
- filtros necessários;
- ordenação controlada;
- respostas de erro consistentes;
- documentação OpenAPI;
- queries otimizadas com `select_related` e `prefetch_related`;
- testes para permissões e visibilidade de rascunhos.

O schema OpenAPI será usado para gerar os tipos e o cliente do frontend. O código gerado deverá ser atualizado de forma controlada quando o contrato da API mudar.

Projetos exporá as consultas abaixo:

```text
GET /api/v1/projects?lang=pt-br&page=1&page_size=12
GET /api/v1/projects?lang=pt-br&page=1&page_size=3&featured=true
GET /api/v1/projects/{slug}?lang=pt-br
```

A listagem geral priorizará projetos em andamento, planejados e concluídos, seguida
da ordem manual, título e ID. A consulta de destaques priorizará a ordem manual. Apenas
projetos publicados serão retornados. O detalhe incluirá equipe, apoio, links, SEO e
slugs equivalentes; mídia continuará usando caminhos relativos a `/media/`.

Erros da API usarão Problem Details conforme o RFC 9457, com
`Content-Type: application/problem+json` e os campos `type`, `title`, `status`,
`detail` e `instance`. Erros de validação usarão o tipo estável
`urn:npca:problem:validation-error` e a extensão `errors`, contendo `pointer`,
`code` e `detail` para cada campo inválido. O Django Admin continuará usando
respostas HTML e o endpoint `/api/v1/health` manterá seu contrato operacional
próprio, inclusive quando responder `503`.

## 10. Mídia e arquivos estáticos

Configuração conceitual do Django:

```text
MEDIA_URL=/media/
MEDIA_ROOT=/app/media
STATIC_URL=/static/
STATIC_ROOT=/app/staticfiles
```

Volumes persistentes:

```text
postgres_data
media_data
static_data
```

Responsabilidades:

- o backend terá acesso de leitura e escrita a `media_data`;
- o Caddy terá acesso somente de leitura a `media_data`;
- o processo de deploy executará `collectstatic`;
- o Caddy terá acesso somente de leitura a `static_data`;
- o frontend não terá acesso direto aos volumes.

Os uploads deverão ter:

- limite de tamanho por tipo de arquivo;
- lista de formatos aceitos;
- nomes gerados pelo sistema;
- validação no backend;
- texto alternativo para imagens informativas e vazio para imagens decorativas;
- processamento opcional de dimensões e qualidade;
- proteção contra execução de arquivos enviados.

O diretório de mídia nunca deverá fazer parte da imagem Docker nem ser incluído no Git.

## 11. Docker Compose

### 11.1 `compose.yaml`

Definirá a base compartilhada:

- rede interna;
- serviço `frontend`;
- serviço `backend`;
- serviço `postgres`;
- volumes persistentes;
- dependências e healthchecks fundamentais.

### 11.2 `compose.dev.yaml`

Adicionará configurações de desenvolvimento:

- bind mounts dos códigos;
- hot reload do Astro;
- reload do Django;
- portas locais expostas;
- banco acessível localmente apenas quando necessário;
- `DEBUG=true`;
- logs mais detalhados;
- serviços auxiliares opcionais, como Mailpit.

Execução:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

### 11.3 `compose.production.yaml`

Adicionará configurações de produção:

- Caddy;
- imagens ou targets de produção;
- reinício automático;
- healthchecks;
- nenhuma montagem do código-fonte;
- nenhuma exposição pública do PostgreSQL;
- cookies seguros;
- hosts e origens confiáveis;
- volumes persistentes;
- configuração de logs;
- limites de recursos, quando definidos após medição.

Execução:

```bash
docker compose -f compose.yaml -f compose.production.yaml up -d --build
```

Cada repositório terá seu próprio Dockerfile multi-stage. O backend deverá instalar as dependências com o lockfile do uv. O frontend deverá produzir e executar o build do Astro com o adapter escolhido.

## 12. Variáveis de ambiente

Nenhum segredo deverá ser versionado. Cada repositório manterá apenas seu `.env.example`.

Variáveis esperadas no backend:

```text
DJANGO_SETTINGS_MODULE
DJANGO_SECRET_KEY
DJANGO_ALLOWED_HOSTS
DJANGO_CSRF_TRUSTED_ORIGINS
DJANGO_DEBUG
DATABASE_URL
MEDIA_ROOT
STATIC_ROOT
```

Variáveis esperadas no frontend:

```text
API_INTERNAL_URL
PUBLIC_API_BASE_URL
PUBLIC_SITE_URL
PUBLIC_DEFAULT_LOCALE
```

O endereço interno da API não deverá ser exposto ao JavaScript enviado ao navegador.

## 13. Segurança

Requisitos mínimos para produção:

- HTTPS obrigatório;
- `DEBUG=false`;
- segredo do Django forte e externo ao Git;
- cookies `Secure` e `HttpOnly` quando aplicável;
- configuração de `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS`;
- proteção do Django Admin por autenticação e permissões;
- contas individuais, sem compartilhamento de senha;
- princípio do menor privilégio;
- limite de tentativas de login;
- validação rigorosa de uploads;
- headers de segurança no proxy e no Django;
- atualizações recorrentes das dependências;
- logs sem senhas, tokens ou dados sensíveis.

JWT armazenado em `localStorage` não será usado para o Django Admin. O admin utilizará autenticação de sessão do Django.

## 14. Qualidade e testes

### Frontend

- verificação de tipos;
- lint e formatação;
- build em CI;
- smoke test manual das rotas, idiomas, temas e metadados SEO;
- validação manual de acessibilidade e layout responsivo nesta etapa inicial;
- testes automatizados de navegador serão adicionados quando existirem fluxos reais,
  como formulários, busca e filtros;
- tratamento dos estados de loading, vazio e erro conforme os módulos forem implementados.

### Backend

- Ruff;
- pytest e pytest-django;
- testes de modelos;
- testes da API;
- testes de filtros e paginação;
- testes de permissões;
- testes para impedir exposição de rascunhos;
- verificação de migrations em CI;
- `manage.py check --deploy` antes da publicação.

Os dois repositórios deverão impedir merge quando lint, testes ou build falharem.

## 15. Backup e recuperação

O uso de mídia local torna o backup uma parte obrigatória da operação.

O servidor deverá manter backup de:

- banco PostgreSQL;
- volume de mídia;
- configurações de deploy necessárias para reconstrução;
- arquivo de variáveis de produção em local seguro.

Recomendação inicial:

- backup diário do PostgreSQL;
- backup diário incremental da mídia;
- cópia em outro disco ou outra máquina;
- política de retenção definida pelo grupo;
- teste periódico de restauração.

Um backup que permanece somente no mesmo disco do servidor não protege contra falha física do equipamento.

## 16. Tecnologias condicionais

Não serão adicionadas inicialmente sem uma necessidade concreta:

- Redis;
- Celery;
- MinIO;
- Elasticsearch ou Meilisearch;
- WebSockets;
- Kubernetes.

Redis e Celery poderão ser introduzidos caso surjam tarefas demoradas, envio em massa de e-mails, importações ou processamento assíncrono. Para a busca inicial, os recursos do PostgreSQL deverão ser avaliados antes de adicionar outro serviço.

## 17. Estratégia de migração

O frontend atual não será usado como base arquitetural. Serão reaproveitados somente itens avaliados e aprovados:

- textos institucionais corretos;
- logotipos;
- fotografias;
- links externos;
- identidade visual;
- requisitos funcionais identificados nas telas existentes.

Etapas sugeridas:

1. inventariar conteúdo e páginas atuais;
2. aprovar sitemap e modelos de dados;
3. criar o backend, modelos e Django Admin;
4. publicar a primeira versão da API;
5. criar o design system e layouts do Astro;
6. integrar as páginas à API;
7. configurar Docker e ambiente de desenvolvimento;
8. preparar o servidor, volumes, HTTPS e backups;
9. importar o conteúdo validado;
10. executar testes, revisão editorial e publicação.

## 18. Escopo da primeira versão

A primeira versão deverá entregar:

- site responsivo e acessível;
- temas claro e escuro, usando a preferência do sistema na primeira visita;
- interface e conteúdo em português brasileiro e inglês;
- páginas institucionais;
- notícias;
- pesquisadores;
- projetos;
- publicações;
- eventos;
- laboratórios, incluindo o LabCompaP;
- Django Admin com grupos e permissões;
- API pública documentada;
- uploads persistentes no servidor;
- deploy com Docker Compose e HTTPS;
- rotina documentada de backup e restauração;
- CI nos dois repositórios.

Funcionalidades adicionais deverão ser avaliadas depois que conteúdo, operação editorial e infraestrutura básica estiverem estáveis.
