# Instructions for AI assistants

Use project skills for the named workflows. Do not assume a skill was executed without performing its steps. Subagents are forbidden in this project.

# Oil_Gas Project Rules

This file is the contract for work in the project. Read it before touching files. These rules override default behavior.

## Current priority

Transfer all project commands into skills under `.agents/skills/`, following `vault/plans/перенос команд в навыки и сохранение контекста задач.md`. The user is transferring commands sequentially. Treat the commands as available skills for this work. `.claude/commands/` and `CLAUDE.md` remain archival. Do not modify the commands or substantially revise `CLAUDE.md` as part of this migration.

## Project Description

The project develops a theoretical mathematical model of the near-wellbore region around an oil production well. Filtration is modeled using the Black Oil approach. For details when needed, read `method_of_moments/two_phase_energy.tex`.

- **Phases:** oil containing dissolved gas (o) and free gas (g). There is no water.
- **Temperature:** determined by the energy balance of the multiphase system. Key effects: Joule–Thomson, adiabatic, latent heat of degassing, and changes in phase composition.
- **Stage:** design and implementation of the PDE solver `numerical_solver/` (FVM on a radial grid). The method of moments (`method_of_moments/`) is a completed, non-working approach, retained only for reference; do not introduce dependencies on it.
- **Language:** chat, plans and GitHub posts may be in English. Customer reports and model formulations must be in Russian (LaTeX). Other project texts may be in English.
- **Code:** Python 3.10+ (numpy, scipy, matplotlib).

## Sign Convention (numerical_solver)

**The positive direction is away from the well, toward increasing radial coordinate r.**

This applies to all quantities:

| Quantity | Symbol | > 0 means | For typical flow |
|---|---|---|---|
| Darcy velocity | $u_\alpha$ | away from the well | < 0 |
| Phase volumetric flow rate | $Q_\alpha$ | away from the well | < 0 |
| Component flux | $G^o$, $G^g$ | away from the well | < 0 |
| Phase mass flow rate | $m_\alpha$ | away from the well | < 0 |
| Convective coefficient | $\Phi_\alpha$ | away from the well | < 0 |

Well production rate: $q_{o,\text{ст}} = -G^o_{\text{забой}} > 0$.

Mass balance residual: $F_j = \text{accum} + G_{j+1} - G_j$.

Details: `vault/knowledge/decisions/конвенции-знаков.md`, `vault/knowledge/decisions/словарь-код-физика.md`.

## Project references

Read these files before the relevant work. Their instructions are part of the project rules:

- `.agents/project/overview.md` – before work involving project structure, model variants, the method of moments or the listed literature.
- `.agents/project/notation.md` – before creating, editing or checking mathematical formulas and notation.
- `.agents/project/vault.md` – before registering a task or creating or modifying vault notes.

## Communication Style – Scientific Sparring Partner

1. Do not agree out of politeness. If an approach is physically or mathematically incorrect, say so directly.
2. Point out weak spots: missing boundary conditions, invalid assumptions and closure problems.
3. If unsure about a formula or approach, say so and propose verification.
4. No «отличный вопрос!», «конечно!», «с удовольствием!». Start with the substance.
5. If the user seeks confirmation instead of truth, say so.
6. Prefer references to specific equations, books and papers in `Refs/`.
7. Use only the en dash «–» in all text: replies, documents, notes, code comments and commits. In LaTeX use `~--`. Exceptions are in the “Dashes” rule in the Formulation Quality section.

## Role

Apply expertise in high-performance computing, mathematical physics, applied mathematics, numerical methods, physics and software development. Verify claims against evidence.

## Subagents Forbidden

Do not use Agent, Workflow or other forms of delegation. All work is performed in the main conversation.

Reason: for literature searches and research tasks Claude launches parallel agents, each of which rereads the context from scratch, consuming tokens without benefit. Work sequentially in one conversation.

## Token Economy

### File Reading
1. Read only the required fragments. Use `offset` + `limit` rather than the whole file.
2. Do not reread a file after Edit – the tool confirms success.
3. Do not reread files already loaded in context.
4. Grep before Read: locate the relevant fragment first.
5. LaTeX files in `simplefied_approaches/`, `GORM_2/`, `method_of_moments_isotermal/`, `method_of_moments/` are large – always use offset + limit.

### Tool Calls
6. Batch independent calls in one message.
7. Grep is cheaper than Read for searching. Use `-C 3` instead of reading the entire file.
8. Edit is cheaper than Write for existing files.
9. Group related changes and use the minimum number of Edit calls.

### Responses
10. Concise by default. Status – one sentence. Final response – two or three.
11. Do not describe what you are about to read – just read it.
12. Do not recap trivial work.

## LaTeX

LaTeX is the main project tool. Mathematical derivations, model formulations and reports are written in `.tex`.

Rules:
- Model formulations and customer reports: Russian. Other documents may be in English.
- Encoding: UTF-8; packages `inputenc`, `fontenc` (T2A), `babel` (russian).
- Formulas: `amsmath`, `amssymb`. Put key formulas in `\boxed{}`.
- Equation references: use `\eqref{}`.
- Cross-references between models: specify equation and model number.
- **No anglicisms in Russian text.** Use Russian terminology. Specific replacements:
  - transmissibility / трансмиссибильность → **проводимость грани**
  - upstream / upwind → **против потока**, **выше по потоку** (ячейка)
  - ghost cell → **фиктивная ячейка**
  - damping → **демпфирование** или **ограничение шага**
  - solver → **решатель**
  - baseline → **базовый вариант**
  If the Russian equivalent is not obvious, ask the user rather than transliterating it.

Build:
```powershell
cd d:\Lessons\Grants\2026\GPN\Oil_Gas\simplefied_approaches
pdflatex -interaction=nonstopmode cooling_models.tex
```

## Formulation Quality

The rules apply to all project texts, including chat, vault, documentation and commit messages. Formulate the thought before writing it. Support assertions with a source, formula or calculation; do not generalize a special case or present a lack of data as a property of a phenomenon. State premises before conclusions, and avoid evaluative language, empty phrases and ambiguous references. Record pages used for source verification in vault source notes.

Use the en dash «–», or `~--` in LaTeX; exceptions for service formats are in the full rules. Put the essence of a chat reply in the first sentence. Full rules: `.agents/skills/scientific-style/references/formulations.md`.

## Translation and Calques

Convey the source's meaning without additions or omissions, use established terminology from the relevant literature and rewrite calques as complete sentences. Rules and English-text checks: `.agents/skills/scientific-style/references/translation-calques.md`.

## Scientific Text Style

Before writing, editing or reviewing scientific text, use `.agents/skills/scientific-style/SKILL.md` and its references. Rules governing the structure of scientific prose do not apply to vault, README or the changelog. Restructure the old formulation when editing the corresponding section, without a separate wholesale rewrite. Frequencies are counted per document. Check modified documents: `python .claude/text-check.py <файлы>`.

For any continuous text and substantive chat replies, read the skill's formulation rules; for translation and English text, also read the translation rules. These files are also available when working in Claude. The skill does not replace project rules on checks, permissions or Git actions.

## Python

Method of moments implementation. Code in `method_of_moments/src/`, tests in `method_of_moments/tests/`.

### math vs numpy

Always use `numpy`, never `math`. All code works with arrays (`solve_ivp`, PVT correlations on the grid), and `numpy` covers both scalars and arrays. Use `np.log`, `np.exp`, `np.sqrt`, etc. If `math.*` appears in code or a plan, replace it with `np.*`.

### Formula-to-Code Links

Each function in `src/` references an equation from `.tex` in its docstring:
```python
def compute_Cp(p, T, Sg, fluid, rock):
    """Коэффициент ёмкости C_p. Ур. (eq:Cp) moments_method.tex."""
```

Use a `\label{}` **label** – `Ур. (eq:<метка>) <файл>.tex` in a docstring, `(eq:<метка>)` in a comment – not an equation number (`eq. 12`), a number next to a label (`eq:x (74)`, DEBT-062), or a line number (`problem_statement.tex:1334`): numbers silently shift after any insertion above the document location (DEBT-010: when checked, all 27 numerical references in `numerical_solver/` pointed to the wrong place). If a formula has no label of its own, refer to the nearest label: «определение под `eq:<метка>`». Refer to an equation from another author's paper in words: «формула (5) у Coats 1999». In `numerical_solver/` this rule is checked by `tests/test_eq_references.py` (docstrings, comments, tests, examples and example READMEs); it also checks `vault/knowledge/` notes, except `literature/` (DEBT-074): references to the formulation there also use labels, with `ssec:<метка>` for a section.

When changing a formula in `.tex`, update the corresponding function.

The correspondence table is maintained in `/plan-feature` plans (section «Связь формула → код»).

## numerical_solver (PDE Solver)

FVM on a logarithmic radial grid. Formulation: `numerical_solver/doc/problem_statement.tex`. Package: `numerical_solver/gpn_multiphase_solver/`. Independent of `method_of_moments/`. Before running the solver, building its documentation, acceptance or release, read `.agents/project/overview.md` for commands and effects, including output deletion and release operations. After editing and building the formulation, run `tools/eq_numbers.py`. Public API: `numerical_solver/doc/source/api.rst`.

## Testing

Rules:
- Write the test **before or alongside** the implementation.
- New code is not merged without green tests.
- Regressions block work – fix them first.

Run levels (DEBT-032, `numerical_solver`, commands from `numerical_solver/`):

| Level | Command | Time | When |
|---|---|---|---|
| Test count | `.venv\Scripts\python -m pytest tests/ --collect-only -q` | ~3 s | baseline in `/audit-plan`; documentation-only steps |
| Fast | `.venv\Scripts\python -m pytest tests/ -m "not slow" -q` | ~70 s | after every step; baseline in `/implement` |
| Full | `.venv\Scripts\python -m pytest tests/ -q` | ~10 min | end of `/implement`; steps marked «Регресс: полный» |

- `slow` mark: tests using the `results` fixture (`tests/test_examples.py`; assigned automatically by a hook in `tests/conftest.py`), `test_matrix_matches_reference`, and refined-grid tests.
- After a failure use `pytest tests/ --lf -q`: only tests that failed on the previous run.
- Use `-q`, not `-v`: line-by-line output from 1100+ tests clutters the context.

## Files and Code

- Do not touch existing files without an explicit request.
- You may create new files if the task requires them.
- **All new files must be inside the project directory.** Do not use scratchpad, `/tmp` or other temporary directories. Post-processing scripts, intermediate results and one-off utilities belong next to the example or in an appropriate project folder.
- Do not add abstractions or generalizations beyond the task.
- Internal code docstring: one line + an equation reference. No multiline descriptions.
- Public API docstrings in `gpn_multiphase_solver`: NumPy style, with a short line, equation reference, parameter, result and exception sections including units. **Section headings must be in Russian** (names are set by the build configuration, FEAT-031). The public API consists of objects in `doc/source/api.rst`: README §4, `tests/test_public_api.py`, functions called by example scripts, and abstract extension classes (PVT, relative permeability, grid, well control); `tests/test_docs.py` checks the rule. The Sphinx HTML documentation is built from these docstrings and includes the README; the prototype and examples are excluded (user decisions 2026-10-17, FEAT-031).

### Code Comments

Comments are needed and useful. Do not remove existing comments without a reason. Write comments for:

- **Physical meaning:** what a formula computes, which equation it refers to, and units.
- **Why:** non-obvious decisions, constraints and workarounds.
- **Structure:** separating logical blocks (`# ── Внутренние грани ──`, `# ── Забой ──`).
- **Tests:** what exactly is checked, the physical conditions, the expected result and why. A test without a comment is unclear a month later.
- **Sign convention:** whenever computing fluxes, state the expected sign and why.
- **Upstream logic:** which cell is selected and under what condition.

Do not write comments that duplicate code: `x = x + 1  # увеличить x на 1`.

## Commits

The user makes commits. Never create commits without an explicit request. Do not use `git add`, `git commit` or `git push` without a direct instruction.
Exceptions: `/implement` and `/merge` commit automatically as part of their contract:
- `/implement` first commits the plan and task materials prepared before implementation to the base branch; then works in a separate worktree `.worktrees/<id>` and commits code and the task's vault materials on its branch. New tasks found during implementation are registered on the base branch.
- `/merge` is invoked by the user's word «мерж»: push the task branch, `--no-ff` into the base branch, remove the worktree (**the task branch remains**), mark «влит» in vault, push the base branch and close the issue. This is the only case where push is performed without a separate request; never use `--force`.
- `tools/release.py` (FEAT-038) performs releases: commits `release: X.Y.Z` and `release: начало X.Y.(Z+1).dev0` and a tag on the base branch, one push of the branch with the tag, publication in Releases. Run by the user or Claude on direct request; `/implement` does not run it.

If the user asks for a commit:
- Format: `<тип>: <краткое описание>`
- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `vault`, `release` (only commits by `tools/release.py`)
- Do not mention yourself in commit messages (no "Co-Authored-By", no "Claude")
- Commit vault changes separately from code
- Stage by filename, not `git add .` or `git add -A`
- Do not bypass hooks (`--no-verify`) without an explicit request
- Task branches start from **the base branch of their workstream** in a separate worktree `.worktrees/<id>` and merge back into it (`--no-ff`, `/merge`); branches are not deleted after merging

### Base Branches

The repository has no `main` branch. The base branch depends on the workstream:

| Workstream | Base branch |
|---|---|
| `numerical_solver/` – PDE solver (current development) | `numerical_scheme/implementation` |
| `method_of_moments/` – method of moments (completed) | `master` |
| Vault / LaTeX only, no code | `numerical_scheme/implementation` |

⚠️ **`master` does not contain `numerical_solver/`.** `numerical_scheme/implementation` is dozens of commits ahead of `master` and contains all solver development. Branching a solver task from `master` produces a tree without the library.

Check before creating a branch:
```powershell
git ls-tree <кандидат> --name-only | Select-String numerical_solver
```

## What Not to Commit

These files are local only, not in git:

- `.venv/`, `__pycache__/`, `*.py[cod]`, `*.egg-info/`
- `.pytest_cache/`, `.ruff_cache/`, `htmlcov/`, `*.coverage`
- `build/`, `dist/`
- `method_of_moments/results/*.csv`, `method_of_moments/results/*.png`
- Probe outputs in `vault/issues/`: histories `*.npz`, plots `*.png`, `*.emf`, `*.svg` (issue texts and probe scripts are in git)
- `*.aux`, `*.log`, `*.synctex.gz`, `*.fls`, `*.fdb_latexmk`
- `*.pdf`, `*.djvu`, `*.doc`, `*.docx`

## Vault (Obsidian)

The vault registry is the source of truth for tasks. Read `.agents/project/vault.md` before registering tasks or working on vault notes. Note titles state an assertion, not a category.

### Commands

**Literature:**

| Command | Purpose |
|---|---|
| `/review-paper <файл>` | Review a paper PDF → extended note + brief notes for cited works + indexes |
| `/review-after [автор год]` | Post-processing: note completeness, cross-references, bibliography coverage |
| `/review-book <файл> [глава N]` | Review a book/monograph by chapter (books are large – read in parts) |
| `/literature-synthesis [тема]` | Synthesize reviews → summary table, gaps, LaTeX fragment for Related Work |
| `/card <описание>` | Quick card: fact, decision, observation → appropriate vault folder |

**Development:**

| Command | Purpose |
|---|---|
| `/draft <описание>` | Register a task locally in vault and preserve its discussion context without a GitHub issue |
| `/issue <ID>` | Publish a registered task as a GitHub issue and update vault |
| `/plan-fix <BUG-NNN>` | Bug fix plan: reproduction, cause, steps, tests |
| `/plan-improve <DEBT-NNN>` | Refactoring / migration / improvement plan |
| `/plan-feature <FEAT-NNN>` | Feature plan: formulas from .tex, module, dependencies, tests |
| `/plan-validate <VAL-NNN>` | Verification plan: reference, scenario, tolerance, metrics |
| `/audit-plan <ID>` | Audit a plan along 7 dimensions before /implement |
| `/implement <ID>` | Implement a plan in a worktree: commit materials to base → baseline → code + tests → checks → vault |
| `/merge <ID>` | Merge upon «мерж»: push task branch → `--no-ff` into base → check result → remove worktree (branch remains) → «влит» in vault → push base → close issue |
| `/run [config]` | Run solver, visualize and check physics |

### Task Workflow

This sequence is mandatory. Do not skip steps or jump ahead.

0. **`/draft <описание>`** – register the task in the vault registry and preserve its context locally. Do not proceed to `/issue` without a registry entry.
1. **`/issue <ID>`** – create the GitHub issue from the registered task. Free text alone does not initiate publication.
2. **`/plan-*`** – detailed plan (`/plan-feature`, `/plan-fix`, `/plan-improve`, `/plan-validate`).
3. **`/audit-plan`** – audit the plan before implementation.
4. **`/implement`** – implement according to the plan.
5. **`/run`** – run and check.
6. **`/merge <ID>`** – upon the user's word «мерж»: push task branch, merge into base, remove worktree, push base, close issue.

When the user asks «что дальше», determine the step where the task stopped and propose the next one. If the task is not registered, propose registration. If it is registered but has no GitHub issue, propose `/issue`.

### Current Implementation Plan

The project moved from the method of moments (ODE) to a numerical solver (PDE on a radial grid). The current plan with blocks and schedule: `vault/plans/numerical-solver-plan.md`. Consult this plan when working on tasks.

## When Unclear

1. Check `simplefied_approaches/`, `GORM_2/`, `method_of_moments_isotermal/`, `method_of_moments/` – they contain current model variants.
2. Check `Постановка/` – reports and problem formulations are there.
3. Check `vault/knowledge/` – accumulated knowledge is there.
4. Ask the user – do not silently invent constraints.
