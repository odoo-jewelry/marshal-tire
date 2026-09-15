# Project instructions

This file keeps team rules, Odoo development policy, and project settings together
in the repository. When reusing it, adapt the Project environment and Project
workflows sections to the target project.

## Team working rules

### Communication and output

- Answer in Russian, concisely, and lead with the result. Write natural Russian prose; do not mix English technical nouns into Russian sentences when a clear Russian equivalent exists. Keep only established abbreviations, code identifiers, Odoo model/field names, and exact UI labels. When an English term is necessary, explain it in Russian on first use.
- Prefer technical accuracy over brevity when explaining architecture, migrations,
  risks, or destructive operations.
- Use English in the codebase for identifiers, comments, docstrings, logs, and
  source strings for technical errors.
- For repository edits, report changed files, key decisions, validation performed,
  and anything not verified.

### Existing work and secrets

- Preserve unrelated pre-existing and user changes. Keep diffs focused and retain
  established local style; do not reformat unrelated code.
- Never hardcode or expose secrets. Read only configuration keys needed for the
  current task; never print complete configuration or environment contents, or
  `/proc/1/environ`.

### Dependency installation and browser testing

- Never install packages, dependencies, tools, browsers, system libraries, or runtime components.
- This prohibition applies to system-wide, user-local, project-local, virtual environment, container, and temporary-directory installations.
- Never use `apt`, `pip`, `pipx`, `npm`, `yarn`, `pnpm`, or similar installation commands, including `pip --target`, `--user`, and `--break-system-packages`.
- Do not work around missing dependencies by changing `PYTHONPATH`, creating a virtual environment, or downloading executables.
- If a required dependency is unavailable, skip the affected validation and explicitly report what was not verified.

- Do not create or run browser-based automated tests, including HOOT, browser QUnit suites, tours, and UI test runners.
- Validate frontend changes with static checks and non-browser tests where practical. Explicitly report browser behavior as not automatically verified.

## Odoo development

### Reference and coding guidelines

- Use the installed standard Odoo source for the target version as the primary
  implementation reference.
- Do not read `ODOO_CODING_GUIDELINES.rst` in full at the start of every task.
- Consult only its relevant section when creating or reviewing Odoo code:
  module layout, Python/ORM, XML/data/security, frontend, or tests/review.

### Critical design validation

Before designing or implementing a requested solution, critically validate its premise. Check whether it conflicts with standard Odoo workflows, duplicates the source of truth, breaks lifecycle/accounting/stock traceability, creates irreversible data consequences, or fails the stated business goal.
If a critical flaw is found, stop before implementation: explain the failure scenario and recommend a safer direction. Continue only after the user explicitly confirms the decision. Do not block work for stylistic preferences or minor architectural trade-offs.

### Development workflow

1. Inspect the affected custom module and its existing tests.
2. Inspect the relevant standard Odoo implementation for the target version and
   project extension points.
3. Prefer, in order: standard configuration, existing project functionality,
   inheritance of standard behavior, then minimal custom implementation.
4. Do not duplicate standard state machines, procurement, stock moves,
   manufacturing, or accounting logic.
5. Preserve ORM batch-recordset behavior and behavior when the custom feature is
   not used.
6. Keep installed databases safely upgradeable; update manifests, security, data
   ordering, migrations, and tests when required.

### Data integrity and security

- Use ORM by default. Use parameterized SQL only when ORM is insufficient or
  materially inefficient, and document why.
- Preserve transaction boundaries and company isolation.
- Give every new persistent model an explicit access policy. Reuse existing
  groups and add access rights, record rules, company restrictions, and manifest
  entries as needed. Extending an existing model with `_inherit` without a new
  `_name` does not require duplicating its access rights. Shared reference data
  does not require artificial company separation.
- Do not implement business invariants only through `onchange`.

### Configuration and migrations

- Prefer XML data, standard configuration, or an explicit migration over runtime
  setup helpers.
- Distinguish one-time development-database cleanup from a permanent deployment
  migration.
- Permanent migrations must be reproducible, versioned, and committed with the
  related module change.
- Do not commit one-time cleanup scripts unless requested.
- Report destructive or irreversible migration requirements before applying them.

### Tests and validation

- Add focused automated tests for non-trivial behavior and regressions. Use the
  Tests and review section of `ODOO_CODING_GUIDELINES.rst` for Odoo-specific cases
  and checks; apply the dependency and browser-test restrictions above.
- Do not build unrelated test infrastructure.
- Run checks applicable to the change. Explicitly report checks that were not
  run, and do not claim runtime validation based only on static inspection.

## Project environment

### Runtime and code locations

- Target Odoo 19.0 Community Edition.
- Each project runs in its own Odoo container. Commands execute inside that
  container; do not use `docker`, `docker compose`, or `docker exec`.
- Repository root: `/mnt/extra-addons/`. Project paths below are relative to it.
- Writable project code is under `main/` and, where present, `solutions/`.
- `forks/`, when present, contains project forks; modify them only when the task
  explicitly targets a fork.
- Treat `3party/` and `/usr/lib/python3/dist-packages/odoo/addons/` as read-only
  unless explicitly requested otherwise.

### Running Odoo

- Configuration file: `/etc/odoo/odoo.conf`. Before module updates, read the
  required settings, including the actual `addons_path`, and pass this file
  explicitly with `-c`.
- For module updates and tests, explicitly select the intended development or
  test database with `-d`.
- When a separate test database is needed, you may create one by appending
  `_testing` to the current database name.
- For temporary Odoo processes, pass an explicit `--http-port`: prefer `8077`;
  if occupied, use a free port starting from `8078`. Port `8069` belongs to the
  persistent server.
- Standard update command (replace the placeholders and adjust the port if
  occupied):

  ```bash
  odoo --http-port=8077 -c /etc/odoo/odoo.conf -u {module_name} -d {db_name} --stop-after-init
  ```

- If overriding `--addons-path`, preserve required configured directories and use
  actual addon-provider subdirectories, not `3party/` itself.

## Project workflows

These sections apply when the corresponding legacy code or OpenSpec workflow is
present in the project.

### Legacy code

- If `legacy/addons/` is present, it may be inspected for business
  behavior, historical workflows, edge cases, data structures, and integrations.
- Never add legacy code to `addons_path`, import it, declare it as a dependency, or
  treat it as the authoritative specification.
- For migrated capabilities, confirm requirements, compare the target standard
  Odoo version, update OpenSpec where applicable, implement in new addons, add
  focused tests, and document intentional differences.

### OpenSpec documentation

- When canonical specifications or feature cards change, rebuild documentation:

  ```bash
  python3 openspec/tools/build_docs.py
  ```

### OpenSpec archive commit

After successfully implementing, validating, syncing, and archiving an OpenSpec
change:

- Create one commit containing the complete change.
- Stage all and only files attributable to that OpenSpec change, including:
  - implementation code, tests, manifests, migrations, security, and data;
  - canonical specs updated or created by spec sync;
  - documentation generated from those specs;
  - the archived OpenSpec change directory.
- "Files changed by the archive operation" means the complete logical change,
  not only files moved into `openspec/changes/archive/`.
- Before committing, inspect `git status` and verify that no file attributable
  to the change remains unstaged.
- Preserve unrelated pre-existing or user changes. If ownership of any changed
  file is ambiguous, stop and ask before staging it.
- Commit with: `<change-name>`.
- Do not split implementation, spec sync, generated documentation, and archive
  artifacts into separate commits unless explicitly requested.
- Do not push automatically.
