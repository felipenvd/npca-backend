# Save game — primeira fatia vertical de Notícias

Última atualização: 29 de agosto de 2026.

Este documento registra o estado de trabalho dos repositórios do NPCA para que a
implementação possa ser retomada sem depender do histórico da conversa.

## Objetivo atual

Entregar Notícias bilíngues de ponta a ponta:

- gerenciamento por um único usuário no Django Admin;
- publicação global, permitida somente com PT-BR e EN completos;
- API pública tipada;
- home, listagem e detalhe no Astro;
- solução pragmática, sem Repository genérico, Use Cases artificiais ou workflow de
  Editor/Publicador.

A implementação está funcional e falta fechar a aceitação manual, revisar os diffs e criar
commits coordenados nos dois repositórios.

## Repositórios e commits-base

Os projetos permanecem separados em diretórios irmãos:

| Repositório | Diretório | Commit-base atual |
| --- | --- | --- |
| Backend | `npca-backend` | `7622be8` |
| Frontend | `npca-frontend` | `5eb91e7` |
| Site legado, somente referência | `site-npca` | `f348889` |

Não modificar nem importar código do `site-npca`. Seus cards e registros fictícios não devem
ser migrados.

## Estado do backend

Foi criado o app `apps.news` com:

- modelos `News` e `NewsTranslation`;
- status `draft`, `published` e `archived`;
- traduções `pt-br` e `en`;
- slug por idioma, gerado automaticamente a partir do título quando estiver vazio;
- slug preservado depois de criado para não quebrar URLs existentes;
- data da primeira publicação preservada em republicações;
- auditoria com usuário e datas de criação e atualização;
- capa opcional com nome UUID e validação real por Pillow;
- JPEG, PNG e WebP, com limites de 5 MiB e 20 megapixels;
- corpo HTML editado pelo WYSIWYG do Unfold e sanitizado com `nh3`;
- Admin com dois formulários inline, um para cada idioma;
- API pública paginada e detalhe localizado;
- respostas de erro em Problem Details.

Rotas públicas:

```text
GET /api/v1/news?lang=pt-br&page=1&page_size=12
GET /api/v1/news/{slug}?lang=pt-br
```

### Regras exibidas no Admin

- `Título *`, `Resumo *` e `Conteúdo *` são obrigatórios para publicar, mas podem ficar vazios
  em rascunhos.
- O slug é gerado automaticamente quando deixado vazio e continua editável para alterações
  intencionais de URL.
- O texto alternativo é obrigatório nos dois idiomas somente quando houver capa.
- Título e descrição de SEO são opcionais; usam título e resumo como fallback.
- Uma notícia incompleta deve permanecer como rascunho.

### Arquivos pendentes no backend

Modificados:

```text
config/settings/base.py
config/urls.py
docs/architecture.md
pyproject.toml
uv.lock
```

Novos e ainda não rastreados:

```text
apps/news/
docs/save-game.md
```

## Estado do frontend

Foi implementado:

- schema OpenAPI atualizado e tipado;
- cliente SSR para Notícias;
- homes PT-BR e EN alimentadas pelas três notícias mais recentes;
- listagens server-rendered com paginação por links;
- detalhes localizados;
- estados vazio, `404` e `503`;
- fallback quando não houver capa;
- canonical, Open Graph, `hreflang` e `NewsArticle` em JSON-LD;
- componentes Astro sem hidratação React para Notícias;
- cabeçalho, rodapé e shell compartilhados;
- estilos editoriais para o HTML já sanitizado pelo backend;
- proxy de desenvolvimento para `/api` e `/media` no Astro.

Rotas:

```text
/pt-br/noticias/
/pt-br/noticias/[slug]/
/en/news/
/en/news/[slug]/
```

Em desenvolvimento, a imagem deve funcionar tanto em
`http://localhost:8000/media/...` quanto em `http://localhost:4321/media/...`. Em produção, o
Caddy é responsável por servir `/media/`.

### Arquivos pendentes no frontend

Modificados:

```text
astro.config.mjs
src/components/layout/HomeShell.astro
src/layouts/BaseLayout.astro
src/lib/api/schema.d.ts
src/lib/i18n/translations.ts
src/pages/en/index.astro
src/pages/pt-br/index.astro
src/styles/global.css
```

Novos e ainda não rastreados:

```text
src/components/layout/SiteFooter.astro
src/components/layout/SiteHeader.astro
src/components/layout/SitePageShell.astro
src/components/news/
src/lib/api/news.ts
src/lib/i18n/format.ts
src/lib/news-page-data.ts
src/pages/en/news/
src/pages/pt-br/noticias/
```

## Verificações já realizadas

Antes do último ajuste visual do Admin:

- backend completo com PostgreSQL: 35 testes passaram;
- Ruff, verificação de migrations e Django checks passaram;
- `check --deploy` passou;
- frontend: Prettier, ESLint, Astro Check e build passaram sem avisos;
- Compose de desenvolvimento e produção foi validado;
- smoke integrado confirmou home, listagem e detalhes PT-BR/EN com `200` e notícia inexistente
  com `404`;
- canonical, `hreflang` e JSON-LD foram conferidos;
- mídia foi conferida no backend e através do proxy do frontend.

Depois do ajuste que identifica os campos obrigatórios no Admin:

- 8 testes direcionados de formulário e Admin passaram;
- Ruff passou;
- Django Check passou sem problemas.

Não havia navegador integrado disponível na última sessão. O HTML real gerado pelo Admin foi
validado por teste automatizado, mas a aparência final ainda deve ser conferida manualmente.

## Como iniciar

No backend:

```bash
cd npca-backend
uv run poe up
```

Endereços locais esperados:

```text
Admin:    http://localhost:8000/admin/
API:      http://localhost:8000/api/v1/
Frontend: http://localhost:4321/
```

Para acompanhar os serviços:

```bash
uv run poe ps
uv run poe logs
```

## Próxima ação recomendada

Fechar a aceitação da fatia de Notícias antes de iniciar outro módulo:

1. Atualizar o Admin e conferir as marcações e textos de ajuda.
2. Criar uma notícia incompleta e confirmar que ela pode ser salva como rascunho.
3. Completar PT-BR e EN, deixar os slugs vazios e publicar.
4. Confirmar a geração automática dos dois slugs.
5. Conferir home, listas, detalhes, capa e troca de idioma.
6. Conferir tema claro/escuro, responsividade, teclado e metadados.
7. Arquivar a notícia e confirmar sua remoção imediata da API e do site.
8. Executar todas as verificações novamente.
9. Revisar os diffs sem alterar o `site-npca`.
10. Criar commits coordenados no backend e frontend e registrar abaixo os hashes finais.

Comandos de fechamento:

```bash
cd npca-backend
uv run poe check
docker compose -f compose.yaml -f compose.production.yaml config --quiet

cd ../npca-frontend
npm run format:check
npm run lint
npm run check
npm run build
```

## Registro da entrega

Preencher depois dos commits coordenados:

```text
Backend:  pendente
Frontend: pendente
Tag:      pendente
```

Somente após essa validação a estrutura de Notícias deve ser reutilizada como padrão para o
próximo módulo.
