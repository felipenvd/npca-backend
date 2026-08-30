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

O painel oficial usa Django Admin com Django Unfold, identidade visual do NPCA e
alternância nativa entre os temas claro e escuro. Ele estará em
`http://localhost:8000/admin/`. A documentação da API estará em
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
