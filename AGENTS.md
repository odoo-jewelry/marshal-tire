# Odoo 19 CE Project Instructions

## Communication and output

- Answer in Russian, concisely, and lead with the result.
- Prefer technical accuracy over brevity when explaining architecture, migrations,
  risks, or destructive operations.
- Use English in the codebase for identifiers, comments, docstrings, logs, and
  source strings for technical errors.
- For repository edits, report changed files, key decisions, validation performed,
  and anything not verified.

## Environment and scope

- Target Odoo 19.0 Community Edition.
- Commands run inside the Odoo container. Do not use `docker`, `docker compose`,
  or `docker exec`.
- Repository root: `/mnt/extra-addons/`.
- Writable project code:
  - `/mnt/extra-addons/main/`
  - `/mnt/extra-addons/solutions/`
  - `/mnt/extra-addons/forks/` only when the task explicitly targets a fork
- Treat `/mnt/extra-addons/3party/` and
  `/usr/lib/python3/dist-packages/odoo/addons/` as read-only unless explicitly
  requested otherwise.
- Use the installed standard Odoo source as the primary implementation reference.

## Coding-guideline routing

- Do not read `ODOO_CODING_GUIDELINES.rst` in full at the start of every task.
- Consult only its relevant section when creating or reviewing Odoo code:
  module layout, Python/ORM, XML/data/security, frontend, or tests/review.
- Existing local style wins when modifying stable code. Keep diffs focused and do
  not reformat unrelated code.

## Development workflow

1. Inspect the affected custom module and its existing tests.
2. Inspect the relevant standard Odoo 19 implementation and project extension
   points.
3. Prefer, in order: standard configuration, existing project functionality,
   inheritance of standard behavior, then minimal custom implementation.
4. Do not duplicate standard state machines, procurement, stock moves,
   manufacturing, or accounting logic.
5. Preserve ORM batch-recordset behavior and behavior when the custom feature is
   not used.
6. Keep installed databases safely upgradeable; update manifests, security, data
   ordering, migrations, and tests when required.

## Data integrity and security

- Use ORM by default. Use parameterized SQL only when ORM is insufficient or
  materially inefficient, and document why.
- Preserve transaction boundaries and company isolation.
- Never hardcode or expose secrets. Read only required keys from
  `/etc/odoo/odoo.conf`; never print complete environment contents or
  `/proc/1/environ`.
- For every new persistent model, add appropriate access rights, record rules when
  required, multi-company protection, and manifest entries.
- Do not implement business invariants only through `onchange`.

## Configuration and migrations

- Prefer XML data, standard configuration, or an explicit migration over runtime
  setup helpers such as `_ensure_*_inventory_setup`.
- Distinguish one-time development-database cleanup from a permanent deployment
  migration.
- Permanent migrations must be reproducible, versioned, and committed with the
  related module change.
- Do not commit one-time cleanup scripts unless requested.
- Report destructive or irreversible migration requirements before applying them.

## Running Odoo

- Before module updates, read `/etc/odoo/odoo.conf` and use its actual
  `addons_path`.
- Never guess a database or update an ambiguous shared, staging, or production database. `odoo_jewelry` is the confirmed development database.
- `$odoo` does not set the HTTP port automatically. Every `$odoo` invocation MUST begin with `$odoo --http-port=8077 ...`.
- Standard update command:

  ```bash
  odoo -u {module_name} -d {db_name} --stop-after-init
  ```

- If overriding `--addons-path`, preserve required configured directories and use
  actual addon-provider subdirectories, not `/mnt/extra-addons/3party` itself.
- Port `8069` belongs to the persistent server. Start temporary Odoo processes on
  `8077`; if occupied, try `8078` and higher.


## Tests and validation

- Add focused automated tests for non-trivial behavior, bug fixes, and changes to
  stock, procurement, manufacturing, accounting, cancellation, retries, returns,
  or partial processing.
- Do not build unrelated test infrastructure.
- Before completion, run all applicable checks: Python syntax/imports, XML and
  external IDs, access CSV, manifest dependencies/data order, module update,
  focused tests, upgrade safety, and unchanged standard behavior.
- Explicitly report checks that were not run.

## OpenSpec documentation

- When canonical specifications or feature cards change, rebuild documentation:

  ```bash
  python openspec/tools/build_docs.py
  ```

## Legacy code

- Legacy implementation is under `legacy/addons` and may be inspected for business
  behavior, historical workflows, edge cases, data structures, and integrations.
- Never add legacy code to `addons_path`, import it, declare it as a dependency, or
  treat it as the authoritative specification.
- For migrated capabilities, confirm requirements, compare standard Odoo 19,
  update OpenSpec where applicable, implement in new addons, add focused tests,
  and document intentional differences.


## OpenSpec archive commit

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

## Dependency installation and browser testing

- Never install packages, dependencies, tools, browsers, system libraries, or runtime components.
- This prohibition applies to system-wide, user-local, project-local, virtual environment, container, and temporary-directory installations.
- Never use `apt`, `pip`, `pipx`, `npm`, `yarn`, `pnpm`, or similar installation commands, including `pip --target`, `--user`, and `--break-system-packages`.
- Do not work around missing dependencies by changing `PYTHONPATH`, creating a virtual environment, or downloading executables.
- If a required dependency is unavailable, skip the affected validation and explicitly report what was not verified.

- Do not create or run browser-based automated tests, including HOOT, browser QUnit suites, tours, and UI test runners.
- Validate frontend changes with static checks and non-browser tests where practical. Explicitly report browser behavior as not automatically verified.