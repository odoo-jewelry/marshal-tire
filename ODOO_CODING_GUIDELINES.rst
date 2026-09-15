======================================
Odoo 19 CE coding guidelines (compact)
======================================

Purpose and precedence
======================

These guidelines contain project-relevant conventions for new Odoo 19 code.
Consult only the section relevant to the current change.

When editing an existing file, preserve its established style and keep the diff
minimal. Do not reformat or reorganize unrelated code merely to apply these
guidelines. Repository-specific conventions take precedence where they are more
specific.

Execution restrictions in ``AGENTS.md`` take precedence over these guidelines,
including the bans on installing dependencies and creating or running
browser-based automated tests.

Module layout and naming
========================

Use standard addon directories only when needed:

* ``models/`` for persistent business models;
* ``wizard/`` for ``models.TransientModel`` and its views;
* ``controllers/`` for HTTP controllers;
* ``views/`` for backend views, menus, and website/portal templates;
* ``security/`` for groups, access rights, and record rules;
* ``data/`` and ``demo/`` for installed and demonstration records;
* ``report/`` for report models, actions, and templates;
* ``static/src/`` for frontend source and ``static/tests/`` for frontend tests
  only when permitted by ``AGENTS.md``;
* ``tests/`` for Python tests and ``migrations/`` for versioned migrations.

Use lowercase ``[a-z0-9_]`` filenames. Name files after their main model or
purpose:

* ``models/sale_order.py`` for an inherited ``sale.order`` model;
* ``views/sale_order_views.xml`` for backend views;
* ``views/sale_order_templates.xml`` for QWeb templates;
* ``wizard/<wizard_name>.py`` and ``<wizard_name>_views.xml``;
* ``security/ir.model.access.csv``, ``<module>_groups.xml``, and
  ``<model>_security.xml``;
* ``data/<purpose>_data.xml`` and ``demo/<purpose>_demo.xml``.

Do not keep unrelated inherited models in one large file. Avoid empty directories
and placeholder files.

Python and ORM
==============

Imports
-------

Order imports in three groups, alphabetically within each group:

1. Python standard library and external packages;
2. Odoo imports;
3. imports from Odoo addons, used only when necessary.

Prefer explicit, readable code. Remove unused imports and dead code. Add comments
or docstrings only when they explain intent, invariants, or non-obvious tradeoffs.

Names and class order
---------------------

* Model technical names are singular dot-separated names, normally prefixed by
  the module domain.
* Python model classes use PascalCase; ordinary variables and methods use
  ``snake_case``.
* ``Many2one`` fields end in ``_id``; ``One2many`` and ``Many2many`` fields end
  in ``_ids``.
* Variables ending in ``_id`` or ``_ids`` contain integer IDs, not recordsets.
* Use ``_compute_<field>``, ``_inverse_<field>``, ``_search_<field>``,
  ``_default_<field>``, ``_selection_<field>``, ``_onchange_<field>``, and
  ``_check_<constraint>`` where applicable.
* User-triggered object actions use the ``action_`` prefix.

Keep model members in this general order:

1. private model attributes;
2. default helpers;
3. fields;
4. SQL constraints and indexes;
5. compute, inverse, and search methods in field order;
6. selection helpers;
7. constraints and onchange methods;
8. CRUD overrides;
9. action methods;
10. other business methods.

Declare SQL table constraints as model attributes using ``models.Constraint``;
``_sql_constraints`` is no longer supported in Odoo 19. Use ``models.Index`` for
custom indexes, such as composite or partial indexes. Keep ordinary field indexes
declared through the field's ``index`` parameter, for example ``index=True``.

Recordsets and extension
------------------------

Methods must support multi-recordsets unless their contract is genuinely
single-record. Use ``ensure_one()`` only for such contracts, not as a shortcut.
Preserve batch behavior in ``create``, ``write``, computed fields, constraints,
and business methods. Use ``@api.model_create_multi`` for batch-aware ``create``
overrides.

Prefer ORM and recordset operations over direct SQL. Avoid repeated searches and
N+1 queries inside loops; batch reads, writes, and record creation where practical.
Use ``Command`` for relational-field commands.

Split methods by responsibility when it creates a meaningful extension point.
Avoid both large monolithic methods and trivial wrapper helpers. Put variable
business criteria in small overrideable helpers rather than hardcoding them deep
inside an action.

Computed values and validation
------------------------------

Declare complete ``@api.depends`` dependencies and use stored computed fields only
when justified. Business invariants must be enforced server-side with constraints,
CRUD logic, or model methods; ``onchange`` is only a user-interface aid.

Use company-aware fields, domains, and checks where records can cross companies.
Use ``sudo()`` only with an explicit reason and retain the intended access and
company boundaries.

Context, transactions, and exceptions
-------------------------------------

Context is immutable; change it with ``with_context``. Prefix custom context keys
with the module name when collision or accidental propagation is possible. Do not
use context as hidden persistent state.

Never call ``commit()`` or ``rollback()`` in normal model code. Manual transaction
control is allowed only for an explicitly created cursor whose complete lifecycle
and error handling are owned by that code.

Scheduled jobs may use the standard ``ir.cron._commit_progress()`` API within its
batch-processing contract, including respecting the returned remaining time.
Do not use it outside a cron job to bypass transaction ownership: outside cron,
it simply commits the current transaction.

Catch only exceptions that can be handled meaningfully and keep ``try`` blocks
narrow. Do not suppress unexpected errors. When intentionally handling an ORM
failure and continuing, isolate the operation with a database savepoint.

Translations
------------

Pass a literal source string to ``self.env._`` and place interpolation arguments
inside the translation call. Do not translate a dynamically assembled string or
a field value that is already translatable. Prefer named placeholders when a
message contains several values.

XML, data, and security
=======================

XML records
-----------

For ``<record>``, put ``id`` before ``model``. For ``<field>``, put ``name`` first,
then its value or ``eval``, followed by other attributes. Group records by model
when dependencies allow it.

Odoo 19 compatibility rules:

* use ``<list>`` instead of the removed ``<tree>`` view type;
* use ``list`` rather than ``tree`` in ``view_mode``;
* link ``res.groups.privilege_id`` to ``res.groups.privilege`` and its
  ``category_id`` to ``ir.module.category``;
* inside a search-view ``<group>``, do not use ``expand`` or ``string`` on the
  group; ``<separator/>`` is allowed and group-by filters do not require
  ``domain="[]"``;
* use only expressions supported by the XML domain evaluator; do not embed
  arbitrary Python.

Declare records before other records that reference them. When menus reference
actions from several files, keep menus in a dedicated file loaded after those
actions. Order manifest data according to dependencies.

Use ``noupdate="1"`` only for data that module upgrades must not overwrite.
Separate demonstration data from required operational data.

External IDs
------------

Use predictable external IDs:

* ``<model>_view_<type>`` for views;
* ``<model>_action`` or ``<model>_action_<purpose>`` for actions;
* ``<model>_menu`` or ``<model>_menu_<purpose>`` for menus;
* ``<module>_group_<name>`` for groups;
* ``<model>_rule_<scope>`` for record rules.

For an inherited view, normally reuse the original record's ID under the current
module namespace and give the view name an ``.inherit.<purpose>`` suffix. Target
stable fields, elements, classes, or names in XPath expressions; never target
translated ``string`` labels.

Views and templates
-------------------

Use inheritance rather than copying standard views or templates. Keep XPath
changes narrow and resilient. Do not replace a large view subtree to modify one
field or attribute. Preserve standard behavior when the custom feature is absent.

Security
--------

Define intentional access control for every new persistent model. Add appropriate
ACLs and manifest entries, reusing existing groups where suitable. Add record
rules and multi-company restrictions where the data requires them; shared
reference data may remain company-independent. Extending an existing model with
``_inherit`` without a new ``_name`` does not require duplicating its ACLs.
Avoid blanket permissions and global rules that unintentionally intersect with
other rules. Validate access with representative user roles, not only as
administrator.

Treat user-provided domains, filenames, URLs, and HTML as untrusted input. Use
Odoo helpers for escaping, safe evaluation, content disposition, and access
checks. Public controllers must have explicit authentication, authorization,
CSRF, and data-exposure decisions.

Frontend
========

Follow nearby Odoo 19 OWL 2 patterns and native module conventions. Register
components through the appropriate registry and use services and hooks rather
than global state. Use ``patch`` only when no supported extension point exists,
and keep patches small.

Declare assets in the manifest and keep JavaScript, XML templates, and SCSS under
``static/src``. Do not add minified third-party source or load runtime assets from
uncontrolled external URLs.

Prefix CSS classes with ``o_<module_name>`` or the component's established Odoo
prefix. Avoid ID selectors and excessively specific selectors. Prefer existing
Odoo variables and utilities; use SCSS variables for design-system values and CSS
variables for contextual DOM-level adaptation.

Tests and review
================

Add focused tests for non-trivial business behavior and regressions, especially
for stock, procurement, manufacturing, accounting, permissions, cancellation,
retry, return, and partial-processing paths. Test batch operations, multi-company
boundaries where relevant, and unchanged standard behavior when the feature is
disabled or unused.

Before completion, check as applicable:

* Python syntax and imports;
* model, field, method, and external-ID names;
* XML syntax, inheritance targets, and reference/data order;
* ACLs, record rules, and manifest entries;
* module installation or update on an explicit development database;
* focused automated tests and upgrade safety.

Report checks that were not run. Do not claim runtime validation based only on
static inspection. For frontend changes, use static checks and non-browser tests
where practical, and report browser behavior as not automatically verified.
