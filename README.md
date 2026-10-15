# NPCA Backend

API, administração e infraestrutura do novo site do Núcleo de Pesquisa em Computação Aplicada.

## Requisitos

- Python 3.14
- uv
- Docker e Docker Compose para a integração completa

## Desenvolvimento local

```bash
cp .env.example .env
uv sync
uv run poe migrate
uv run poe superuser
uv run poe dev
```

`createsuperuser` solicita e-mail e senha; o projeto não usa nome de usuário.
O Poe é instalado no ambiente do projeto, portanto não precisa ser instalado globalmente.

Para executar o Django localmente usando o PostgreSQL do Docker, inicie o banco antes
das migrations:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d postgres
```

O banco fica disponível em `localhost:5433`. No `.env`, mantenha `POSTGRES_PORT=5433`
e a porta `5433` em `DATABASE_URL`. Dentro do Docker, os serviços usam `postgres:5432`.

Na execução local, deixe `MEDIA_ROOT` e `STATIC_ROOT` sem definição no `.env` para
usar as pastas `media/` e `staticfiles/` do backend. O Docker Compose configura
os caminhos `/app/media` e `/app/staticfiles` automaticamente dentro dos containers.
No Docker, tanto em desenvolvimento quanto em produção, os uploads ficam no
volume persistente `media_data`, montado em `/app/media`. Esse volume é separado
da pasta local `media/`: ao usar o ambiente integrado, execute os seeds pelos
comandos `docker-seed-*` para que banco e arquivos sejam preenchidos no mesmo
ambiente. Se houver dados criados localmente, copie os arquivos para o volume
antes de passar a servir esse mesmo banco pelo Docker.

O painel oficial usa Django Admin com Django Unfold, identidade visual do NPCA e
alternância nativa entre os temas claro e escuro. Ele estará em
`http://localhost:8000/gestao-npca/`. A documentação da API estará em
`http://localhost:8000/api/v1/docs` e o healthcheck em
`http://localhost:8000/api/v1/health`.
Erros da API seguem RFC 9457 e usam `application/problem+json`; o Admin e o
healthcheck mantêm seus formatos próprios.

## Verificações

```bash
uv run poe check
```

Execute `uv run poe` para listar as tarefas disponíveis. Entre elas estão `format`,
`lint`, `test`, `migrations`, `migrate`, `superuser`, `seed-labcompap`,
`seed-courses` e `dev`.

## Idioma do painel administrativo

O admin usa português brasileiro independentemente do idioma do navegador ou do
cookie de idioma. As demais rotas mantêm a negociação normal de idioma.
Os textos adicionais do Django Unfold ficam em `locale/pt_BR/LC_MESSAGES/django.po`.
O catálogo compilado `django.mo` também é versionado e incluído nas imagens Docker.

Após editar as traduções, compile e reinicie o backend:

```bash
uv run poe compile-translations
```

A compilação requer GNU gettext no ambiente de desenvolvimento. O catálogo já
compilado permite executar o backend sem instalar essa ferramenta no servidor.

## Formulários de conteúdo

Nos cadastros de pesquisadores, notícias, projetos, eventos, publicações e cursos,
cada campo em português aparece seguido da versão em inglês. Os idiomas são fixos;
não é necessário adicionar traduções separadas ou selecionar o idioma.
Os dados gerais, fotos, links, equipes e autores continuam compartilhados.

Slug, SEO e ordem de exibição ficam em **Opções avançadas**, recolhidas por padrão.
Slugs vazios são gerados automaticamente e os campos de SEO mantêm os valores
alternativos existentes. A ativação ou publicação fica ao final do formulário;
rascunhos podem ser salvos antes de completar o inglês. O histórico aparece
recolhido ao editar um registro existente. Não há tradução automática de textos.

## Carga inicial do LabCompAp

Os equipamentos bilíngues e as imagens iniciais da galeria ficam em
`scripts/seed/labcompap/`. O comando valida o pacote, cria registros reais no banco e
copia a galeria para o `MEDIA_ROOT` configurado. Todo o conteúdo institucional e as três
imagens do hero são estáticos e versionados no frontend:

```bash
uv run poe seed-labcompap
uv run poe seed-courses
```

O comando não sobrescreve uma página existente. `--force` deve ser usado somente quando
a substituição integral do conteúdo editorial for intencional.

## Dados de demonstração para testes

Com o banco em execução e as migrations aplicadas, preencha todas as áreas do admin:

```bash
uv run poe seed-demo
```

O comando cria 2 grupos, 2 contas inativas sem senha utilizável, 6 pesquisadores,
5 projetos com coordenadores e equipes, 15 notícias, 8 eventos, 6 publicações com
autores e projetos relacionados, 8 cursos, 3 equipamentos e 3 imagens de galeria.
Os registros são identificados com `[DEMO]`, têm traduções PT-BR/EN e reutilizam
as imagens ilustrativas do pacote de seed do LabCompAp. Os links externos usam
`example.org` e são fictícios.

Há conteúdo publicado, rascunhos e arquivados, pesquisadores ativos e inativos,
eventos futuros, em andamento, encerrados, adiados e cancelados. As 13 notícias
publicadas permitem testar a paginação do site.

O comando funciona somente com `DEBUG=True`. Pode ser repetido sem duplicar os
registros de demonstração nem sobrescrever alterações editoriais. Registros
existentes de outros seeds também são preservados. Em caso de falha, a transação
é desfeita e os arquivos criados por essa execução são removidos.

No ambiente Docker de desenvolvimento:

```bash
uv run poe docker-seed-demo
```

## Ambiente integrado

Mantenha `npca-backend` e `npca-frontend` como diretórios irmãos. Depois execute:

```bash
uv sync
uv run poe up
```

Com o ambiente em execução:

```bash
uv run poe ps
uv run poe logs
uv run poe docker-superuser
uv run poe docker-seed-labcompap
uv run poe docker-seed-courses
uv run poe docker-seed-demo
uv run poe down
```

`down` remove os containers, mas preserva os volumes do PostgreSQL, mídia e
arquivos estáticos. Para validar o Compose sem iniciar serviços, use
`uv run poe docker-config`.

O Poe é apenas uma conveniência. Também é possível executar diretamente:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

Em produção, preencha um `.env` seguro e execute:

```bash
docker compose -f compose.yaml -f compose.production.yaml config
docker compose -f compose.yaml -f compose.production.yaml up -d --build
```

Após as migrations, a carga inicial de produção é uma operação manual e única:

```bash
docker compose -f compose.yaml -f compose.production.yaml exec backend \
  uv run --no-sync python manage.py seed_labcompap

docker compose -f compose.yaml -f compose.production.yaml exec backend \
  uv run --no-sync python manage.py seed_courses
```

Ela não é executada automaticamente no startup nem pelo serviço `setup`.

Consulte a [arquitetura do projeto](docs/architecture.md) para decisões de dados, mídia, segurança e deploy.
