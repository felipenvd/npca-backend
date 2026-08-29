# Save game — Notícias concluídas e Pesquisadores em andamento

Última atualização: 29 de agosto de 2026.

Este documento registra o ponto de retomada dos dois repositórios do novo site do NPCA.

## Repositórios

| Repositório | Branch atual | Base da fatia |
| --- | --- | --- |
| `npca-backend` | `develop` | `d1d602e` |
| `npca-frontend` | `develop` | `c6a7861` |
| `site-npca` | somente referência | `f348889` |

Os hashes-base são os commits coordenados que entregaram Notícias:

```text
Backend:  d1d602e feat(news): implementa gerenciamento e API bilíngue
Frontend: c6a7861 feat(news): integra páginas bilíngues ao site
```

Não modificar nem importar código, cards ou registros fictícios do `site-npca`.

## Notícias

A primeira fatia vertical está concluída:

- gerenciamento bilíngue no Django Admin;
- rascunho, publicação conjunta e arquivamento;
- slugs automáticos e estáveis;
- WYSIWYG sanitizado;
- capa segura com mídia relativa, crédito opcional e tratamento decorativo no frontend;
- migration `news.0002_remove_newstranslation_cover_alt_text` remove o campo manual
  de texto alternativo da capa;
- API paginada e tipada;
- home, listagem e detalhe SSR em PT-BR e EN;
- SEO, canonical, `hreflang` e `NewsArticle`.

## Pesquisadores

A segunda fatia vertical está implementada e validada na branch `develop`. Os
hashes dos commits que contêm esta entrega devem ser consultados no Git ou na entrega da
tarefa.

### Backend

- app `apps.researchers` registrado;
- `Researcher` com nome, categoria acadêmica, foto, e-mail público opcional, Lattes, ORCID,
  LinkedIn, ativo/inativo, ordem e auditoria;
- `ResearcherTranslation` com idioma, slug, área, biografia e SEO;
- inativos podem permanecer incompletos;
- ativação exige área e biografia completas em PT-BR e EN;
- fotos usam automaticamente o nome completo como texto alternativo;
- slugs são gerados a partir do nome e preservados;
- biografia usa WYSIWYG e sanitização compartilhada;
- imagem usa validação compartilhada com wrappers específicos por app;
- migration `researchers.0001_initial` criada e aplicada no ambiente de desenvolvimento;
- migration `researchers.0002_researcher_academic_category` adiciona a categoria obrigatória
  sem classificar silenciosamente registros existentes;
- migration `researchers.0003_add_master_academic_category` diferencia Mestre(a) de
  Mestrando(a);
- migration `researchers.0004_remove_translation_role_and_photo_alt_text` remove os
  campos editoriais redundantes de função e texto alternativo;
- ordenação pública: categoria, ordem interna, nome e ID;
- endpoints públicos adicionados:

```text
GET /api/v1/researchers?lang=pt-br&page=1&page_size=24
GET /api/v1/researchers/{slug}?lang=pt-br
```

### Frontend

- OpenAPI regenerado;
- cliente SSR tipado;
- quatro pesquisadores na home;
- listagem paginada e perfil individual em PT-BR e EN;
- fallback por iniciais quando não houver foto;
- categorias localizadas nos cards, perfis e grupos da listagem;
- atalhos opcionais de Lattes, ORCID e LinkedIn nos cards;
- e-mail e perfis acadêmicos públicos quando informados;
- navegação atualizada;
- canonical, Open Graph `profile`, `hreflang` e JSON-LD `Person`.

Rotas:

```text
/pt-br/pesquisadores/
/pt-br/pesquisadores/[slug]/
/en/researchers/
/en/researchers/[slug]/
```

## Verificações realizadas nesta fatia

- suíte completa do backend: 59 testes passaram com PostgreSQL;
- Ruff, formatação, Django Check e migrations check passaram;
- migration aplicada no PostgreSQL de desenvolvimento;
- OpenAPI regenerado a partir do backend em execução;
- Prettier, ESLint, Astro Check e build passaram.
- Compose de desenvolvimento e produção passou na validação;
- smoke integrado confirmou home, listagem e perfis PT-BR/EN com `200`;
- perfil inexistente e perfil desativado retornaram `404`;
- desativação removeu imediatamente o perfil da API pública;
- canonical, Open Graph, `hreflang` e JSON-LD foram conferidos no HTML;
- smoke de categorias confirmou prioridade, ordem interna e agrupamentos PT-BR/EN;
- o registro temporário usado no smoke foi removido do banco.

Não havia navegador integrado conectado para inspeção visual automatizada. Layout,
responsividade, temas e navegação por teclado ainda devem ser conferidos manualmente.

## Próximos passos

1. Conferir visualmente Admin, home, listagem e perfil em desktop e mobile.
2. Validar temas claro e escuro e navegação por teclado.
3. Enviar a branch `develop` dos dois repositórios.
4. Fazer code review e publicar em homologação.

Comandos principais:

```bash
cd npca-backend
uv run poe check
docker compose -f compose.yaml -f compose.dev.yaml config --quiet
docker compose -f compose.yaml -f compose.production.yaml config --quiet

cd ../npca-frontend
npm run format:check
npm run lint
npm run check
npm run build
```
