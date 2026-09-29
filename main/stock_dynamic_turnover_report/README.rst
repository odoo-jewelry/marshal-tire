Dynamic Stock Turnover Report
=============================

The module adds one stock turnover action to Dynamic Financial Reports and
Inventory Reporting. It depends on dynamic_accounts_report and uses its
shared /xlsx_report route. Only inventory-tracked products owned by the
selected company participate. The report reads standard Odoo stock and
valuation records; it does not create a valuation ledger or change stock.

Modes
-----

* Stock locations: choose and order warehouse, location, product and
  product-category row dimensions. Opening and closing quantities are
  reconstructed from current quants and completed move lines. Company
  valuation is allocated to locations by owned quantity, and by valuation
  lot first when applicable. Ordinary incoming and outgoing amounts are
  measured at each row boundary, so parent gross turnover may differ from
  the sum of child gross turnovers for internal transfers.
* FIFO receipts: choose and order receipt, product and category. A
  receipt is identified by its incoming valued stock move, and its label
  shows the movement date, readable PO number and recorded valuation unit
  cost. FIFO receipt attribution is company-wide. It does not claim the
  physical origin of units at a location. PO and receipt filters are applied
  after the complete company FIFO calculation. Unsupported or ambiguous
  history is shown as unattributed; it is never assigned to a selected PO.

Quantity cells keep product units separate. Values are in company currency.
The valuation difference is closing value minus opening value minus signed
recorded turnover; it is a reconciliation amount, not a posted operation.
An unavailable value is distinct from a recorded zero. The fixed cutoff
and revision bind details and XLSX to the displayed source state. Refresh
to view changes to stock, valuation, access or classifications.

Access
------

The action, calculations, details, filter search and export require Inventory
Manager rights. The service scopes a request to one allowed company and
rejects incomplete source visibility before invoking standard valuation,
which can compute with elevated rights internally. Commercial links are
shown only when the user may read their records.

Replacing the previous report
-----------------------------

The old stock_product_turnover_report source was removed from the current
repository tree and remains available in Git history. Its OpenSpec artifacts
remain in the repository. The old module is not a dependency of this module.
Do not uninstall the old module before updating tire because Odoo's saved
dependency graph can cascade-uninstall tire.

1. Back up the main database and check that dynamic_accounts_report and
   its required accounting dependencies are installed.
2. Install stock_dynamic_turnover_report and update tire on the
   permitted <main_database>_testing copy. Run the module and integration
   checks, including both report modes and XLSX.
3. Read stock_product_turnover_report.downstream_dependencies() in the
   test database. If it contains any installed business module, update that
   module's manifest and database dependency records first.
4. Uninstall the old report on the test copy. Verify tire and the new
   report remain installed; compare stock moves, move lines, quants, POS
   orders and accounting moves before and after.
5. Repeat the installation/update, graph check and old report uninstall in
   the main database only after the test copy passes. Keep the old source
   available until the old module is uninstalled. No install hook performs
   an automatic uninstall.

The report has no persistent business data requiring a versioned migration.
