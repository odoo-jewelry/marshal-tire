from copy import deepcopy
from unittest import SkipTest
from unittest.mock import patch

from freezegun import freeze_time

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.pos_order_correction.tests.common import PosOrderCorrectionCommon

from .test_historical_stock import TestHistoricalStock


@tagged("post_install", "-at_install", "purchase_history_integration")
class TestPurchaseCostIntegration(PosOrderCorrectionCommon):
    _target_session = TestHistoricalStock._target_session
    _source = TestHistoricalStock._source
    _prepare = TestHistoricalStock._prepare

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not hasattr(cls.env["purchase.order"], "_apply_purchase_cost_recompute"):
            raise SkipTest("The optional purchase correction module is not installed.")
        cls.env.user.group_ids = [Command.link(cls.env.ref(name).id) for name in (
            "purchase.group_purchase_manager", "stock.group_stock_manager",
            "pos_historical_stock_writeoff.group_historical_stock",
            "product_card_consolidation.group_product_consolidation_manager",
        )]
        cls.company.inventory_valuation = "periodic"
        cls.env["decimal.precision"].search([("name", "=", "Product Price")]).digits = 2
        cls.category = cls.categ_basic.copy({
            "name": "Integrated purchase FIFO", "property_cost_method": "fifo",
        })
        cls.historical_product = cls.create_product("Integrated canonical", cls.category, 100, 9)
        cls.duplicate = cls.create_product("Integrated duplicate", cls.category, 100, 9)
        cls.source_location = cls.config.picking_type_id.default_location_src_id
        cls.vendor = cls.env["res.partner"].create({"name": "Integrated purchase vendor"})
        cls.duplicate_vendor = cls.env["res.partner"].create({"name": "Integrated duplicate vendor"})
        cls.tax = cls.env["account.tax"].create({
            "name": "Integrated purchase 20%", "type_tax_use": "purchase",
            "amount_type": "percent", "amount": 20, "company_id": cls.company.id,
            "invoice_repartition_line_ids": [
                Command.create({"repartition_type": "base"}),
                Command.create({"repartition_type": "tax",
                                "account_id": cls.company_data["default_account_tax_purchase"].id}),
            ],
            "refund_repartition_line_ids": [
                Command.create({"repartition_type": "base"}),
                Command.create({"repartition_type": "tax",
                                "account_id": cls.company_data["default_account_tax_purchase"].id}),
            ],
        })
        cls.service = cls.env["product.card.consolidation.service"]

    def _purchase(self, price=9, quantity=100, product=None, taxes=None, discount=0,
                  date="2026-01-01 10:00:00", company=None):
        product = product if product is not None else self.historical_product
        taxes = taxes if taxes is not None else self.tax
        company = company if company is not None else self.company
        with freeze_time(date):
            order = self.env["purchase.order"].with_company(company).with_context(
                allowed_company_ids=company.ids,
            ).create({
                "partner_id": (self.duplicate_vendor if product == self.duplicate else self.vendor).id,
                "company_id": company.id,
                "currency_id": company.currency_id.id, "date_order": date,
                "order_line": [Command.create({
                    "product_id": product.id, "product_qty": quantity,
                    "product_uom_id": product.uom_id.id, "price_unit": price,
                    "discount": discount, "tax_ids": [Command.set(taxes.ids)],
                    "date_planned": date,
                })],
            })
            order.button_confirm()
            if order.locked:
                order.button_unlock()
            moves = order.order_line.move_ids
            for move in moves:
                move.quantity = move.product_uom_qty
            moves.picked = True
            moves._action_done()
        return order

    def _merge(self):
        canonical = self.historical_product.product_tmpl_id
        source = self.duplicate.product_tmpl_id
        plan = self.service.analyze(canonical, source, mode="history")
        self.assertFalse(plan["blockers"], plan["blockers"])
        self.service.consolidate(canonical, source, mode="history",
                                 expected_fingerprint=plan["fingerprint"])
        self.assertTrue(canonical._has_full_consolidation_history(self.company))
        return canonical._full_history_operations(self.company)

    def _historical(self, quantity=31, source_quantity=1, state="cancel"):
        target = self._target_session()
        source = self._source(source_quantity, state=state)
        picking = self._prepare(source, target)
        # The source receipt is a preparation source, not an immutable quantity
        # template: the ordinary preparation flow explicitly permits this edit.
        picking.move_ids.product_uom_qty = quantity
        picking.action_apply_historical_stock()
        return source, picking

    def _merged_purchases(self):
        first = self._purchase(price=8.93, quantity=20, date="2026-01-01 09:00:00")
        second = self._purchase(product=self.duplicate)
        audit = self._merge()
        return first | second, audit

    def _sale(self, quantity=1, product=None, date="2026-01-03 10:00:00", refund_line=None):
        product = product if product is not None else self.historical_product
        with freeze_time(date):
            if not self.config.current_session_id:
                self._start_pos_session(self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0)
            line = {"product": product, "quantity": quantity}
            if refund_line:
                line["refunded_orderline_id"] = refund_line.id
            values = self.create_ui_order_data(
                [line], customer=self.customer,
                payments=[(self.bank_pm1, product.lst_price * quantity)],
            )
            result = self.env["pos.order"].with_context(generate_pdf=False).sync_from_ui([values])
            return self.env["pos.order"].browse([
                order["id"] for order in result["pos.order"] if order["uuid"] == values["uuid"]
            ])

    def _source_facts(self, source):
        return (
            source.read(["state", "date_order", "session_id", "amount_total", "amount_tax",
                         "amount_paid", "amount_return", "payment_ids", "account_move", "lines"]),
            source.lines.read(["product_id", "qty", "price_unit", "discount", "total_cost",
                               "is_total_cost_computed", "price_subtotal", "price_subtotal_incl"]),
        )

    def _facts(self, orders, source, picking, sales=None):
        sales = sales if sales is not None else self.env["pos.order"]
        products = orders.order_line.product_id
        moves = self.env["stock.move"].search([
            ("product_id", "in", products.ids), ("company_id", "=", self.company.id),
        ], order="id")
        audits = self.env["product.consolidation.operation"].search([
            ("canonical_id", "in", products.product_tmpl_id.ids),
        ], order="id")
        quants = self.env["stock.quant"].search([
            ("product_id", "in", products.ids), ("company_id", "=", self.company.id),
        ], order="id")
        return deepcopy({
            "source": self._source_facts(source),
            "picking": picking.read([
                "state", "date_done", "historical_pos_order_id", "historical_session_id",
                "historical_effective_at", "historical_source_snapshot", "historical_reason",
                "historical_applied_at", "historical_applied_by_id", "move_ids",
            ]),
            "moves": moves.read([
                "product_id", "product_uom", "product_uom_qty", "quantity", "date", "state",
                "picking_id", "location_id", "location_dest_id", "origin_returned_move_id",
                "move_line_ids", "account_move_id", "cost_repair_line_id", "historical_cost_line_id",
            ]),
            "move_lines": moves.move_line_ids.read([
                "product_id", "product_uom_id", "quantity", "date", "state", "lot_id",
                "package_id", "result_package_id", "owner_id", "location_id", "location_dest_id",
            ]),
            "quants": quants.read(["product_id", "location_id", "quantity", "reserved_quantity"]),
            "sales": sales.read(["state", "date_order", "session_id", "amount_total", "amount_tax",
                                  "amount_paid", "amount_return", "payment_ids", "account_move"]),
            "payments": sales.payment_ids.read(["amount", "payment_date", "payment_method_id"]),
            "sessions": (source.session_id | picking.historical_session_id | sales.session_id).read([
                "state", "start_at", "stop_at", "move_id",
            ]),
            "audit": audits.read(),
            "audit_lines": audits.line_ids.read(),
            "journal_count": self.env["pos.cost.recompute"].search_count([]),
            "manual_count": self.env["product.value"].search_count([]),
            "account_count": self.env["account.move"].search_count([]),
        })

    def _values(self, orders):
        products = orders.order_line.product_id
        moves = self.env["stock.move"].search([
            ("product_id", "in", products.ids), ("company_id", "=", self.company.id),
        ], order="id")
        return (
            orders.order_line.read(["price_unit", "tax_ids", "discount", "product_qty"]),
            moves.read(["value", "quantity", "date", "state"]),
            products.read(["standard_price", "total_value", "qty_available"]),
        )

    def _assert_rejected(self, orders, pattern=None):
        before = self._values(orders)
        assertion = self.assertRaisesRegex(UserError, pattern) if pattern else self.assertRaises(UserError)
        with assertion:
            orders._apply_purchase_cost_recompute()
        self.assertEqual(self._values(orders), before)

    def test_merged_history_writeoff_open_sales_later_receipt_and_repeat(self):
        orders, _audit = self._merged_purchases()
        source, picking = self._historical()
        first = self._sale(quantity=4)
        later = self._purchase(price=30, quantity=10, taxes=self.env["account.tax"],
                               date="2026-01-04 10:00:00")
        second = self._sale(quantity=90, date="2026-01-05 10:00:00")
        sales = first | second
        self.assertEqual(source.lines.qty, 1)
        self.assertEqual(picking.move_ids.quantity, 31)
        self.assertEqual(sales.session_id.state, "opened")
        before = self._facts(orders | later, source, picking, sales)
        unselected_before = later.order_line.read(["price_unit", "tax_ids", "discount"])
        result = orders._apply_purchase_cost_recompute()
        self.assertEqual(orders.order_line.mapped("price_unit"), [10.72, 10.8])
        self.assertFalse(orders.order_line.tax_ids)
        self.assertAlmostEqual(orders[:1].order_line.move_ids.value, 214.4)
        self.assertEqual(orders[1:].order_line.move_ids.value, 1080)
        self.assertAlmostEqual(picking.move_ids.value, 333.2)
        self.assertAlmostEqual(first.lines.total_cost, 43.2)
        self.assertAlmostEqual(second.lines.total_cost, 1068)
        self.assertAlmostEqual(first.margin, 400 - 43.2)
        self.assertAlmostEqual(second.margin, 9000 - 1068)
        self.assertEqual(later.order_line.move_ids.value, 300)
        self.assertEqual(later.order_line.read(["price_unit", "tax_ids", "discount"]), unselected_before)
        self.assertEqual(self.historical_product.qty_available, 5)
        self.assertAlmostEqual(self.historical_product.total_value, 150)
        self.assertAlmostEqual(self.historical_product.standard_price, 30)
        self.assertEqual({key: result[key] for key in ("purchase_lines", "receipts", "issues", "returns", "pos_lines")},
                         {"purchase_lines": 2, "receipts": 2, "issues": 3, "returns": 0, "pos_lines": 2})
        self.assertEqual(self._facts(orders | later, source, picking, sales), before)
        corrected = self._values(orders | later), sales.lines.read(["total_cost", "margin"])
        repeat = orders._apply_purchase_cost_recompute()
        self.assertEqual(repeat["purchase_lines"], 0)
        self.assertEqual((self._values(orders | later), sales.lines.read(["total_cost", "margin"])), corrected)
        self.assertEqual(self._facts(orders | later, source, picking, sales), before)

    def test_historical_source_snapshot_survives_later_full_merge(self):
        order = self._purchase(price=9, quantity=10, product=self.duplicate)
        canonical = self.historical_product
        self.historical_product = self.duplicate
        source, picking = self._historical(quantity=2)
        original_snapshot = picking.historical_source_snapshot
        self._close_session(self.config.current_session_id)
        self.assertEqual(source.session_id.state, "closed")
        self.historical_product = canonical
        audit = self._merge()
        self.assertEqual(source.lines.product_id, canonical)
        self.assertEqual(picking.move_ids.product_id, canonical)
        self.assertNotEqual(source._historical_source_snapshot(), original_snapshot)
        self.assertTrue(audit.line_ids.filtered(lambda line: line.record_model == "stock.move"))
        before = self._facts(order, source, picking)
        result = order._apply_purchase_cost_recompute()
        self.assertEqual(order.order_line.price_unit, 10.8)
        self.assertAlmostEqual(picking.move_ids.value, 21.6)
        self.assertEqual(result["pos_lines"], 0)
        self.assertEqual(self._facts(order, source, picking), before)

    def test_full_merge_and_historical_value_allow_disabled_inventory_tracking(self):
        orders, _audit = self._merged_purchases()
        source, picking = self._historical()
        self.historical_product.is_storable = False
        before = self._facts(orders, source, picking)
        orders._apply_purchase_cost_recompute()
        self.assertAlmostEqual(picking.move_ids.value, 333.2)
        self.assertFalse(self.historical_product.is_storable)
        self.assertEqual(self._facts(orders, source, picking), before)

    def test_incomplete_and_absorbed_cards_remain_rejected(self):
        first = self._purchase(price=8.93, quantity=20)
        second = self._purchase(product=self.duplicate, date="2026-01-01 11:00:00")
        self.service.consolidate(self.historical_product.product_tmpl_id, self.duplicate.product_tmpl_id)
        self.assertFalse(self.historical_product.product_tmpl_id._has_full_consolidation_history(self.company))
        self._assert_rejected(first)
        self.assertEqual(second.order_line.product_id, self.duplicate)
        self._assert_rejected(second)

    def test_full_merge_with_residual_source_move_or_quant_is_rejected(self):
        orders, _audit = self._merged_purchases()
        for kind in ("move", "quant"):
            with self.subTest(kind=kind), self.env.cr.savepoint() as savepoint:
                if kind == "move":
                    self.env["stock.move"].create({
                        "product_id": self.duplicate.id, "product_uom": self.duplicate.uom_id.id,
                        "product_uom_qty": 1, "location_id": self.source_location.id,
                        "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                    })
                else:
                    self.env["stock.quant"]._update_available_quantity(self.duplicate, self.source_location, 1)
                self._assert_rejected(orders)
                savepoint.rollback()

    def test_previous_reviewed_historical_cost_is_preserved(self):
        orders, _audit = self._merged_purchases()
        source, picking = self._historical()
        operation = self.env["pos.cost.recompute"].browse(source.action_prepare_cost_recompute()["res_id"])
        operation.reason = "Protect previously reviewed historical valuation"
        operation.action_preview()
        operation.action_apply()
        self.assertTrue(picking.move_ids.historical_cost_line_id)
        before = operation.stock_line_ids.read(["move_id", "old_value", "new_value", "actual_value"])
        self._assert_rejected(orders)
        self.assertEqual(operation.stock_line_ids.read(["move_id", "old_value", "new_value", "actual_value"]), before)

    def test_merged_historical_financial_and_manual_protections(self):
        orders, _audit = self._merged_purchases()
        source, picking = self._historical()
        for protection in ("manual", "closing", "vendor_bill", "stock_account"):
            with self.subTest(protection=protection), self.env.cr.savepoint() as savepoint:
                if protection == "manual":
                    orders[:1].order_line.move_ids.value_manual = 200
                elif protection == "closing":
                    self.company.purchase_lock_date = "2026-01-02"
                elif protection == "vendor_bill":
                    self.env["account.move"].create({
                        "move_type": "in_invoice", "partner_id": self.vendor.id,
                        "invoice_line_ids": [Command.create({
                            "product_id": self.historical_product.id, "quantity": 20,
                            "price_unit": 8.93, "purchase_line_id": orders[:1].order_line.id,
                        })],
                    })
                else:
                    account = self.env["account.move"].create({
                        "journal_id": self.company_data["default_journal_misc"].id,
                        "date": "2026-01-01",
                    })
                    orders[:1].order_line.move_ids.account_move_id = account
                before = self._facts(orders, source, picking)
                self._assert_rejected(orders)
                self.assertEqual(self._facts(orders, source, picking), before)
                savepoint.rollback()

    def test_late_failure_rolls_back_historical_value_and_retry(self):
        orders, _audit = self._merged_purchases()
        source, picking = self._historical()
        sale = self._sale(quantity=4)
        before = self._values(orders), self._facts(orders, source, picking, sale), sale.lines.total_cost
        original = type(sale.lines)._compute_total_cost

        def fail_after_cost(lines, moves):
            original(lines, moves)
            self.assertAlmostEqual(picking.move_ids.value, 333.2)
            self.assertAlmostEqual(sale.lines.total_cost, 43.2)
            self.assertEqual(orders.order_line.mapped("price_unit"), [10.72, 10.8])
            raise UserError("Failure after integrated POS cost update")

        with patch.object(type(sale.lines), "_compute_total_cost", fail_after_cost):
            self._assert_rejected(orders, "Failure after integrated POS cost update")
        self.assertEqual((self._values(orders), self._facts(orders, source, picking, sale), sale.lines.total_cost), before)
        orders._apply_purchase_cost_recompute()
        self.assertAlmostEqual(picking.move_ids.value, 333.2)
        self.assertAlmostEqual(sale.lines.total_cost, 43.2)

    def test_cancelling_integrated_dialog_does_not_change_values(self):
        orders, _audit = self._merged_purchases()
        source, picking = self._historical()
        before = self._values(orders), self._facts(orders, source, picking)
        action = orders.action_open_cost_recompute()
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        self.assertTrue(wizard._transient)
        self.assertEqual(wizard.order_ids, orders)
        wizard.unlink()
        self.assertEqual((self._values(orders), self._facts(orders, source, picking)), before)

    def test_historical_valuation_does_not_use_other_company_receipts(self):
        self.historical_product.company_id = False
        order = self._purchase(quantity=5)
        source, picking = self._historical(quantity=2, state="draft")
        other = self.env["res.company"].create({
            "name": "Foreign integrated valuation", "currency_id": self.company.currency_id.id,
            "inventory_valuation": "periodic",
        })
        self.env.user.company_ids |= other
        self.category.with_company(other).property_cost_method = "fifo"
        foreign = self._purchase(price=900, quantity=10, taxes=self.env["account.tax"],
                                 date="2026-01-01 08:00:00", company=other)
        foreign_product = self.historical_product.with_company(other).with_context(allowed_company_ids=other.ids)
        before = (foreign.order_line.move_ids.read(["value", "quantity", "date", "state"]),
                  foreign_product.read(["standard_price", "total_value", "qty_available"]))
        order.with_context(allowed_company_ids=(self.company | other).ids)._apply_purchase_cost_recompute()
        self.assertAlmostEqual(picking.move_ids.value, 21.6)
        self.assertEqual((foreign.order_line.move_ids.read(["value", "quantity", "date", "state"]),
                          foreign_product.read(["standard_price", "total_value", "qty_available"])), before)

    def test_mixed_tracking_discount_return_and_shortage_after_writeoff(self):
        orders, _audit = self._merged_purchases()
        source, picking = self._historical(quantity=1)
        other = self.create_product("Integrated nonstock later", self.category, 100, 10)
        additional = self._purchase(price=0.03, quantity=2, product=other, discount=10,
                                    taxes=self.tax.copy({"name": "Integrated half cent", "amount": 50}))
        ordinary = self._sale(quantity=1, product=other)
        sale = self._sale(quantity=150, date="2026-01-03 11:00:00")
        refund = self._sale(quantity=-150, date="2026-01-04 10:00:00", refund_line=sale.lines)
        final = self._sale(quantity=1, date="2026-01-05 10:00:00")
        # Historical movements remain the source of truth after an inventory
        # tracking setting changes; this does not invent nonstock quants.
        other.is_storable = False
        selected = orders | additional
        before = self._facts(selected, source, picking, ordinary | sale | refund | final)
        result = selected._apply_purchase_cost_recompute()
        self.assertEqual(additional.order_line.price_unit, 0.05)
        self.assertEqual(additional.order_line.discount, 10)
        self.assertFalse(additional.order_line.tax_ids)
        self.assertFalse(other.is_storable)
        # Standard purchase_stock rounds the discounted stock unit price too:
        # 0.05 * 0.9 = 0.045 becomes 0.05 at the configured price precision.
        self.assertAlmostEqual(additional.order_line.move_ids.value, 0.10)
        self.assertAlmostEqual(ordinary.lines.total_cost, 0.05)
        self.assertAlmostEqual(picking.move_ids.value, 10.72)
        expected_issue = 19 * 10.72 + 131 * 10.8
        self.assertAlmostEqual(sale.lines.total_cost, expected_issue)
        self.assertAlmostEqual(refund.lines.total_cost, -expected_issue)
        self.assertAlmostEqual(final.lines.total_cost, 10.79)
        self.assertEqual(result["returns"], 1)
        self.assertEqual(result["pos_lines"], 4)
        self.assertEqual(self._facts(selected, source, picking, ordinary | sale | refund | final), before)
