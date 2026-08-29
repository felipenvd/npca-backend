# Save game — Notícias, Pesquisadores, Projetos e Publicações concluídos

Última atualização: 29 de agosto de 2026.

Este documento registra o ponto de retomada dos dois repositórios do novo site do NPCA.

## Repositórios

| Repositório | Branch atual | Último marco funcional |
| --- | --- | --- |
| `npca-backend` | `develop` | `4fb6133` |
| `npca-frontend` | `develop` | `5fd4822` |
| `site-npca` | somente referência | `f348889` |

Os commits coordenados das três fatias concluídas são:

```text
Notícias backend:       d1d602e feat(news): implementa gerenciamento e API bilíngue
Notícias frontend:      c6a7861 feat(news): integra páginas bilíngues ao site
Pesquisadores backend:  f1c4e08 feat(researchers): implementa gerenciamento e API bilíngue
Pesquisadores frontend: 275a37e feat(researchers): integra perfis bilíngues ao site
Projetos backend:        4fb6133 feat(projects): implementa gerenciamento e API bilíngue
Projetos frontend:       5fd4822 feat(projects): integra projetos bilíngues ao site
```

A quarta fatia, Publicações, está implementada e validada no working tree dos dois
repositórios, ainda sem commit coordenado registrado neste documento.

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

A segunda fatia vertical está implementada e validada na branch `develop`.

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

## Projetos

A terceira fatia vertical está implementada e validada na branch `develop`.

### Backend

- app `apps.projects` com Admin, formulários, schemas, API, validações e testes;
- status editorial independente da situação acadêmica manual;
- rascunhos incompletos e publicação bilíngue validada;
- coordenador obrigatório e equipe simples relacionados a Pesquisadores;
- pesquisadores relacionados protegidos contra exclusão e sem duplicação entre
  coordenação e equipe;
- início obrigatório, término validado e obrigatório para projetos concluídos;
- capa decorativa opcional com nome UUID e validação compartilhada de imagem;
- descrição em WYSIWYG com sanitização compartilhada;
- apoio, parceiros, site, repositório, destaque, ordem e auditoria;
- `published_at` preservado após arquivamento, rascunho ou republicação;
- migration `projects.0001_initial` criada e aplicada no PostgreSQL de desenvolvimento;
- endpoints públicos adicionados:

```text
GET /api/v1/projects?lang=pt-br&page=1&page_size=12
GET /api/v1/projects?lang=pt-br&page=1&page_size=3&featured=true
GET /api/v1/projects/{slug}?lang=pt-br
```

### Frontend

- OpenAPI regenerado e cliente SSR tipado;
- três projetos destacados na home, imediatamente após Sobre;
- listagem e detalhe SSR em PT-BR e EN;
- situação e período localizados, capa decorativa e fallback visual;
- coordenador e equipe com links somente para perfis públicos ativos;
- apoio, parceiros e links externos seguros;
- navegação e CTA do hero apontando para Projetos;
- canonical, Open Graph, `hreflang` e JSON-LD `ResearchProject`.

Rotas:

```text
/pt-br/projetos/
/pt-br/projetos/[slug]/
/en/projects/
/en/projects/[slug]/
```

## Publicações

A quarta fatia vertical está implementada e validada na branch `develop`.

### Backend

- app `apps.publications` com Admin, formulários, schemas, API, validações e testes;
- rascunhos incompletos e publicação bilíngue validada;
- ano, periódico ou evento e pelo menos um autor obrigatórios para publicar;
- autoria ordenada, aceitando Pesquisadores relacionados ou nomes externos;
- cada autoria usa exatamente uma identidade e Pesquisadores relacionados são protegidos
  contra exclusão;
- título, resumo e SEO localizados em PT-BR e EN;
- imagem de divulgação opcional com nome UUID, crédito e texto alternativo localizado;
- DOI opcional normalizado e único sem diferenciar maiúsculas de minúsculas;
- URL externa, PDF e projeto relacionado opcionais;
- PDF limitado a 20 MiB, validado por extensão, MIME e assinatura, com nome UUID;
- projeto só é exposto quando estiver publicado e traduzido no idioma solicitado;
- `published_at` preservado após arquivamento, rascunho ou republicação;
- migration `publications.0001_initial` criada e aplicada no PostgreSQL de desenvolvimento;
- migration `publications.0002_publication_cover_publication_cover_credit_and_more` adiciona
  imagem, crédito e texto alternativo e está aplicada no PostgreSQL de desenvolvimento;
- endpoints públicos adicionados:

```text
GET /api/v1/publications?lang=pt-br&page=1&page_size=12
GET /api/v1/publications?lang=pt-br&page=1&page_size=12&year=2026
GET /api/v1/publications/{id}?lang=pt-br
```

### Frontend

- OpenAPI regenerado e cliente SSR tipado;
- três publicações recentes na home, imediatamente após Projetos;
- listagem paginada e detalhe por ID em PT-BR e EN;
- imagem de divulgação nos cards e no detalhe, com fallback visual quando ausente;
- autoria com links somente para perfis públicos ativos;
- acesso seguro por DOI, URL externa e PDF quando informados;
- vínculo opcional com projeto público no idioma atual;
- navegação desktop e mobile atualizada;
- canonical, `hreflang` e JSON-LD `ScholarlyArticle`.

Rotas:

```text
/pt-br/publicacoes/
/pt-br/publicacoes/[id]/
/en/publications/
/en/publications/[id]/
```

## Acabamento global do frontend

- logos vetoriais específicos para os temas claro e escuro;
- símbolo vetorial próprio para o favicon;
- cabeçalho compacto, sem repetição do nome institucional por extenso;
- alternância direta entre claro e escuro, usando o sistema somente antes da primeira
  escolha explícita;
- menu mobile bilíngue com diálogo nativo, fechamento por `Esc`, controle de foco,
  idioma e tema;
- indicação visual e semântica da rota ativa em Notícias, Pesquisadores, Projetos e
  Publicações.

## Verificações realizadas nesta fatia

- suíte completa do backend: 99 testes passaram com PostgreSQL;
- Ruff, formatação, Django Check e migrations check passaram;
- migrations de Projetos e Publicações aplicadas no PostgreSQL de desenvolvimento;
- OpenAPI regenerado a partir do backend em execução;
- Prettier, ESLint, Astro Check e build passaram;
- Compose de desenvolvimento e produção passou na validação;
- smoke HTTP integrado com registro temporário isolado confirmou listagem e detalhe de
  Publicações em PT-BR/EN com `200`;
- o HTML servido confirmou título localizado, `aria-current="page"`, `hreflang`, projeto
  relacionado e JSON-LD `ScholarlyArticle` nos dois idiomas;
- smoke integrado confirmou API e listagens vazias de Projetos em PT-BR/EN com `200`;
- perfil inexistente e perfil desativado retornaram `404`;
- desativação removeu imediatamente o perfil da API pública;
- canonical, Open Graph, `hreflang` e JSON-LD foram conferidos no HTML;
- smoke de categorias confirmou prioridade, ordem interna e agrupamentos PT-BR/EN;
- o registro temporário usado no smoke anterior foi removido do banco;
- o HTML servido confirmou `aria-current="page"`, canonical e `hreflang` nas
  listagens de Projetos em PT-BR e EN;
- Prettier, ESLint, Astro Check e build passaram após o acabamento da navegação.

Não havia navegador integrado conectado para inspeção visual automatizada. O drawer,
os temas, a responsividade e a navegação por teclado ainda devem ser conferidos
manualmente.

## Próximos passos

1. Criar uma publicação real completa no Admin e executar o smoke editorial.
2. Conferir visualmente listagem e detalhe em desktop e mobile.
3. Validar autoria, PDF, links, teclado, alternância de idioma e metadados do detalhe.
4. Criar os commits coordenados de Publicações nos dois repositórios.
5. Enviar a branch `develop`, fazer code review e publicar em homologação.

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
