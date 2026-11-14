# lib/types

Shared types that cross the Python / TypeScript boundary. Each type lives in its own
directory with one implementation per language, which must stay in sync:

```
lib/types/<type>/
├── python/__init__.py     # -> searchhacks_types.<type_with_underscores>
└── typescript/index.ts    # -> @searchhacks/types/<type>
```

| Type | Python | TypeScript | Values |
|---|---|---|---|
| `query-category` | `QueryCategory(IntEnum)` + `QUERY_CATEGORY_LABELS`, `_PARENTS`, `_PATHS` | `QueryCategory` const object + type, `QUERY_CATEGORY_LABELS`, `_PARENTS`, `_PATHS` | Google Trends category ids (1133) |
| `search-provider` | `SearchProvider(StrEnum)` | `SearchProvider` const object + type, `SEARCH_PROVIDERS` | Telem search provider slugs |

TypeScript enums are `as const` objects plus a same-named union type (not `enum`), so they
work under any TS runtime.

`make check-types` (`lib/types/check_sync.py`) loads both sides of every type and fails on any
missing member or differing value. Run it after changing a type.

The category hierarchy is a DAG (139 categories have several parents). `QUERY_CATEGORY_PARENTS`
maps each id to all its parents; `QUERY_CATEGORY_PATHS` maps each id to its canonical path from
the root (where it first appears in the source), so every consumer places a category the same way.

`query-category` is generated. Don't edit its `python/` or `typescript/` output by hand; edit
`google-trends-categories.md` (vendored from the
[google-trends-api wiki](https://github.com/pat310/google-trends-api/wiki/Google-Trends-Categories))
and run:

```bash
python3 lib/types/query-category/generate.py
```

`search-provider` is hand-written from
[Telem's search providers](https://docs.telem.ai/resources/search-parameters/#providers).
