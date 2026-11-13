# Vault reference

Structured project knowledge base.

```
vault/
├── 00-home/
│   └── index.md                    # Navigation hub – links to all sections
├── knowledge/
│   ├── literature/                 # ~70 notes: extended reviews + brief citation-context notes
│   │   ├── index-literature.md     # Topic index (6 sections + extended reviews)
│   │   ├── cited-references.md     # ~60 entries – alphabetical index of brief notes
│   │   └── Автор Год – тема.md     # Notes (extended and brief)
│   ├── science/                    # Physics, models, formulas
│   ├── decisions/                  # Decisions with rationale
│   ├── debugging/                  # Code bug investigations
│   ├── validation/                 # Verification cases (VAL-* results)
│   └── numerics/                   # Numerical notes (ODE stiffness, frozen PVT, ...)
├── plans/                          # Detailed plans from /plan-* commands
├── roadmap/                        # Task registries (BUG/DEBT/FEAT/VAL)
│   ├── известные баги и технический долг.md
│   ├── планируемые фичи.md         # FEAT-001..008 – implementation roadmap
│   └── валидационные кейсы.md       # VAL-001..003
├── inbox/                          # Unprocessed ideas
├── ref_spe202436.md                # (legacy)
└── ref_moments_method.md           # (legacy)
```

### Note Naming

A title is an assertion, not a category: `эффект JT доминирует при разгазировании в ПЗП.md`, not `температура.md`.

### Task Registries (vault/roadmap/)

Each task is **first registered** locally with `/draft` in the vault registry, with its discussion context saved in `vault/issues/<id-lowercase>/00-draft.md`. The registry is the sole source of truth for the project task list. A GitHub issue is created later by a separate `/issue <ID>` request and links to the registry entry.

**Three registry files** (separated by category):

| File | Task types | ID pattern |
|---|---|---|
| `vault/roadmap/известные баги и технический долг.md` | BUG, DEBT | `BUG-NNN`, `DEBT-NNN` |
| `vault/roadmap/планируемые фичи.md` | FEAT | `FEAT-NNN` |
| `vault/roadmap/валидационные кейсы.md` | VAL | `VAL-NNN` |

**How to register a task:**

1. Determine the type: BUG (defect), DEBT (technical debt/refactoring), FEAT (new functionality), VAL (verification case).
2. Open the corresponding registry file.
3. Find the maximum existing entry number (grep `### <PREFIX>-`) and assign the next one.
4. Add section `### <ID>: Краткое описание` using the template in the file header (section «Формат записи»).
5. Set the new entry's status to `🔴 ОТКРЫТ`.

**Required fields at registration** (minimum):
- **BUG:** symptom, file, reproduction
- **DEBT:** current state, motivation, affected modules
- **FEAT:** description, formulas (references to equations in `.tex`), module
- **VAL:** reference, scenario, metric

Fields **GitHub:**, **Ветка:**, **План:** are filled later by the corresponding commands (`/issue`, `/plan-*`).

Numbering is continuous within each prefix. BUG and DEBT share a file but are numbered independently.

### Note Formats

Two types of literature notes:
- **Extended** (from PDF): frontmatter + Задача + Метод + Результаты + Замечания + Значение для проекта + Цитируется в + Ссылается на
- **Brief** (from citation context): warning callout + 2–3 sentence abstract

Categories of cited works: **A** (methodological), **B** (applied), **C** (review/reference).

**Promoting a brief note to an extended note:** if `/review-paper` finds a brief note for the same work, replace it with the extended version, update `status`, and move it from `cited-references.md` to `index-literature.md`.

