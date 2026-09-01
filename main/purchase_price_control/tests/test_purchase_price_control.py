from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPurchasePriceControl(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.purchase_price_rounding = 0.01
        cls.company.purchase_default_markup = 0.0
        cls.vendor = cls.env["res.partner"].create({"name": "Price Control Vendor"})
        cls.product = cls.env["product.product"].create({
            "name": "Price Control Product",
            "is_storable": True,
            "list_price": 150.0,
            "standard_price": 80.0,
            "supplier_taxes_id": [Command.clear()],
        })

    def _line_values(self, product=None, **values):
        product = product or self.product
        result = {
            "name": product.name,
            "product_id": product.id,
            "product_qty": 1.0,
            "product_uom_id": product.uom_id.id,
            "price_unit": 100.0,
            "tax_ids": [Command.clear()],
            "date_planned": fields.Datetime.now(),
        }
        result.update(values)
        return result

    def _create_order(self, lines=None):
        return self.env["purchase.order"].create({
            "partner_id": self.vendor.id,
            "company_id": self.company.id,
            "currency_id": self.company.currency_id.id,
            "date_order": fields.Datetime.now(),
            "order_line": [Command.create(values) for values in (lines or [self._line_values()])],
        })

    def test_fill_refill_snapshot_and_copy(self):
        self.product.with_company(self.company).last_purchase_price = 100.0
        order = self._create_order()
        line = order.order_line
        self.assertFalse(line.price_snapshot_initialized)
        self.assertFalse(line.planned_sale_price)

        order.action_fill_current_prices()
        self.assertTrue(line.price_snapshot_initialized)
        self.assertAlmostEqual(line.current_purchase_price, 100.0)
        self.assertAlmostEqual(line.current_sale_price, 150.0)
        self.assertAlmostEqual(line.current_markup, 50.0)
        self.assertAlmostEqual(line.planned_sale_price, 150.0)

        self.product.with_company(self.company).last_purchase_price = 120.0
        self.assertAlmostEqual(line.current_purchase_price, 100.0)
        order.action_fill_current_prices()
        self.assertAlmostEqual(line.current_purchase_price, 120.0)
        self.assertFalse(order.copy().order_line.price_snapshot_initialized)

    def test_default_markup_and_rounding(self):
        self.company.purchase_default_markup = 30.0
        self.company.purchase_price_rounding = 10.0
        order = self._create_order()
        order.action_fill_current_prices()
        self.assertAlmostEqual(order.order_line.current_markup, 30.0)
        self.assertAlmostEqual(order.order_line.planned_sale_price, 130.0)
        with self.assertRaises(ValidationError):
            self.company.purchase_price_rounding = 0.0

    def test_manual_planned_sale_price_is_exact_and_has_no_side_effects(self):
        self.company.purchase_price_rounding = 0.01
        order = self._create_order()
        order.action_fill_current_prices()
        line = order.order_line
        initial_markup = line.current_markup
        product_prices = (
            self.product.with_company(self.company).last_purchase_price,
            self.product.lst_price,
            self.product.standard_price,
        )

        line.planned_sale_price = 12.0
        self.env.flush_all()
        line.invalidate_recordset(["planned_sale_price"])
        self.assertAlmostEqual(line.current_markup, initial_markup)
        self.assertAlmostEqual(line.planned_sale_price, 12.0)
        self.assertTrue(line.planned_sale_price_manually_set)
        self.assertEqual(
            (
                self.product.with_company(self.company).last_purchase_price,
                self.product.lst_price,
                self.product.standard_price,
            ),
            product_prices,
        )

    def test_manual_planned_sale_price_survives_basis_change(self):
        order = self._create_order()
        order.action_fill_current_prices()
        line = order.order_line
        initial_markup = line.current_markup
        line.planned_sale_price = 12.0

        line.price_unit = 120.0
        self.assertAlmostEqual(line.effective_purchase_price, 120.0)
        self.assertAlmostEqual(line.current_markup, initial_markup)
        self.assertAlmostEqual(line.planned_sale_price, 12.0)

        order.action_fill_current_prices()
        self.assertFalse(line.planned_sale_price_manually_set)
        self.assertAlmostEqual(line.planned_sale_price, 120.0)

    def test_manual_planned_sale_price_requires_valid_initialized_basis(self):
        initialized_line = self._create_order().order_line
        initialized_line.order_id.action_fill_current_prices()
        uninitialized_line = self._create_order().order_line
        initial_markup = initialized_line.current_markup

        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            (initialized_line | uninitialized_line).write({
                "planned_sale_price": 150.0,
            })
        self.assertAlmostEqual(initialized_line.current_markup, initial_markup)

        section_line = self._create_order([
            {
                "name": "Price Control Section",
                "display_type": "line_section",
                "product_qty": 0.0,
                "price_unit": 0.0,
            },
        ]).order_line
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            section_line.planned_sale_price = 100.0

    def test_discount_tax_and_purchase_uom(self):
        tax = self.env["account.tax"].create({
            "name": "Purchase Tax 20%",
            "amount": 20.0,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "company_id": self.company.id,
        })
        line = self._create_order([self._line_values(
            price_unit=120.0,
            discount=10.0,
            tax_ids=[Command.set(tax.ids)],
            product_uom_id=self.env.ref("uom.product_uom_dozen").id,
        )]).order_line
        self.assertAlmostEqual(line.effective_purchase_price, 10.8)

    def test_currency_conversion_uses_order_date(self):
        currency = self.env["res.currency"].create({
            "name": "XPC",
            "symbol": "XPC",
            "rounding": 0.01,
            "rate_ids": [
                Command.create({
                    "name": fields.Date.from_string("2026-01-01"),
                    "rate": 2.0,
                    "company_id": self.company.id,
                }),
                Command.create({
                    "name": fields.Date.from_string("2026-02-01"),
                    "rate": 4.0,
                    "company_id": self.company.id,
                }),
            ],
        })
        order = self._create_order([self._line_values(price_unit=200.0)])
        order.write({
            "currency_id": currency.id,
            "date_order": fields.Datetime.from_string("2026-01-15 12:00:00"),
        })
        expected = currency._convert(
            200.0,
            self.company.currency_id,
            self.company,
            order.date_order,
            round=False,
        )
        self.assertAlmostEqual(order.order_line.effective_purchase_price, expected)
        self.assertAlmostEqual(order.order_line.valuation_purchase_price, expected)

    def test_line_update_retry_and_confirm_no_side_effect(self):
        order = self._create_order()
        order.action_fill_current_prices()
        order.order_line.action_update_product_prices()
        self.assertAlmostEqual(self.product.with_company(self.company).last_purchase_price, 100.0)
        self.assertAlmostEqual(self.product.lst_price, 100.0)
        self.assertAlmostEqual(self.product.standard_price, 100.0)
        self.assertFalse(order.has_price_updates)
        order.order_line.action_update_product_prices()
        order.order_line.price_unit = 125.0
        order.button_confirm()
        self.assertAlmostEqual(self.product.with_company(self.company).last_purchase_price, 100.0)

    def test_valuation_cost_excludes_recoverable_tax(self):
        tax_account = self.env["account.account"].create({
            "name": "Recoverable Purchase Tax",
            "code": "PCREC",
            "account_type": "asset_current",
        })
        repartition_lines = [
            Command.create({"repartition_type": "base"}),
            Command.create({
                "repartition_type": "tax",
                "account_id": tax_account.id,
            }),
        ]
        tax = self.env["account.tax"].create({
            "name": "Recoverable Purchase Tax 20%",
            "amount": 20.0,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "company_id": self.company.id,
            "invoice_repartition_line_ids": repartition_lines,
            "refund_repartition_line_ids": repartition_lines,
        })
        line = self._create_order([self._line_values(
            price_unit=120.0,
            discount=10.0,
            tax_ids=[Command.set(tax.ids)],
            product_uom_id=self.env.ref("uom.product_uom_dozen").id,
        )]).order_line
        self.assertAlmostEqual(line.effective_purchase_price, 10.8)
        self.assertAlmostEqual(line.valuation_purchase_price, 9.0)

    def test_valuation_cost_includes_cost_bearing_tax(self):
        tax = self.env["account.tax"].create({
            "name": "Cost-bearing Purchase Tax 20%",
            "amount": 20.0,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "company_id": self.company.id,
        })
        line = self._create_order([self._line_values(
            price_unit=120.0,
            discount=10.0,
            tax_ids=[Command.set(tax.ids)],
            product_uom_id=self.env.ref("uom.product_uom_dozen").id,
        )]).order_line
        self.assertAlmostEqual(line.valuation_purchase_price, 10.8)

    def test_avco_does_not_update_cost(self):
        category = self.env["product.category"].create({
            "name": "AVCO Price Control",
            "property_cost_method": "average",
        })
        product = self.env["product.product"].create({
            "name": "AVCO Product",
            "is_storable": True,
            "categ_id": category.id,
            "tracking": "lot",
            "lot_valuated": True,
            "list_price": 150.0,
            "standard_price": 80.0,
            "supplier_taxes_id": [Command.clear()],
        })
        lot = self.env["stock.lot"].create({
            "name": "AVCO-PRICE-CONTROL-LOT",
            "product_id": product.id,
        })
        cost_before = product.standard_price
        lot_cost_before = lot.standard_price
        order = self._create_order([self._line_values(product=product)])
        order.action_fill_current_prices()
        order.order_line.action_update_product_prices()
        self.assertAlmostEqual(product.standard_price, cost_before)
        self.assertAlmostEqual(lot.standard_price, lot_cost_before)
        self.assertAlmostEqual(product.with_company(self.company).last_purchase_price, 100.0)

        product.categ_id.property_cost_method = "fifo"
        cost_before = product.standard_price
        lot_cost_before = lot.standard_price
        order.action_fill_current_prices()
        order.order_line.price_unit = 130.0
        order.order_line.action_update_product_prices()
        self.assertAlmostEqual(product.standard_price, cost_before)
        self.assertAlmostEqual(lot.standard_price, lot_cost_before)

    def test_cost_method_change_before_update_uses_current_method(self):
        order = self._create_order()
        order.action_fill_current_prices()
        category = self.env["product.category"].create({
            "name": "Changed to AVCO",
            "property_cost_method": "average",
        })
        self.product.categ_id = category
        cost_before = self.product.standard_price
        order.order_line.action_update_product_prices()
        self.assertAlmostEqual(self.product.standard_price, cost_before)

    def test_standard_cost_propagates_to_lot_valuation(self):
        product = self.env["product.product"].create({
            "name": "Lot-valuated Standard Product",
            "is_storable": True,
            "tracking": "lot",
            "lot_valuated": True,
            "standard_price": 55.0,
            "supplier_taxes_id": [Command.clear()],
        })
        lot = self.env["stock.lot"].create({
            "name": "PRICE-CONTROL-LOT",
            "product_id": product.id,
        })
        order = self._create_order([self._line_values(product=product)])
        order.action_fill_current_prices()
        order.order_line.action_update_product_prices()
        self.assertAlmostEqual(product.standard_price, 100.0)
        self.assertAlmostEqual(lot.standard_price, 100.0)

    def test_cost_only_discrepancy_and_noop_retry(self):
        self.product.with_company(self.company).write({
            "last_purchase_price": 100.0,
            "lst_price": 100.0,
            "standard_price": 80.0,
        })
        order = self._create_order()
        order.action_fill_current_prices()
        self.assertTrue(order.order_line.price_update_required)
        history_before = self.env["product.value"].search_count([
            ("product_id", "=", self.product.id),
        ])
        order.order_line.action_update_product_prices()
        history_after = self.env["product.value"].search_count([
            ("product_id", "=", self.product.id),
        ])
        self.assertAlmostEqual(self.product.standard_price, 100.0)
        self.assertGreater(history_after, history_before)
        order.order_line.action_update_product_prices()
        self.assertEqual(
            self.env["product.value"].search_count([
                ("product_id", "=", self.product.id),
            ]),
            history_after,
        )

    def test_bulk_repeated_product_creates_one_final_cost(self):
        self.product.standard_price = 80.0
        order = self._create_order([
            self._line_values(sequence=20, price_unit=200.0),
            self._line_values(sequence=10, price_unit=120.0),
        ])
        order.action_fill_current_prices()
        history_before = self.env["product.value"].search_count([
            ("product_id", "=", self.product.id),
        ])
        order.action_update_all_prices()
        history_after = self.env["product.value"].search_count([
            ("product_id", "=", self.product.id),
        ])
        self.assertAlmostEqual(self.product.standard_price, 200.0)
        self.assertEqual(history_after, history_before + 1)

    def test_bulk_failure_rolls_back_prices_cost_history_and_snapshots(self):
        other_product = self.env["product.product"].create({
            "name": "Failing Product",
            "is_storable": True,
            "list_price": 150.0,
            "standard_price": 70.0,
            "supplier_taxes_id": [Command.clear()],
        })
        order = self._create_order([
            self._line_values(price_unit=110.0),
            self._line_values(product=other_product, price_unit=120.0),
        ])
        order.action_fill_current_prices()
        snapshots_before = order.order_line.read([
            "current_purchase_price",
            "current_sale_price",
            "current_standard_price",
        ])
        history_before = self.env["product.value"].search_count([
            ("product_id", "in", (self.product | other_product).ids),
        ])
        original_write = type(self.product).write

        def failing_write(records, values):
            if other_product.id in records.ids:
                raise ValidationError("Expected bulk failure")
            return original_write(records, values)

        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            with patch.object(type(self.product), "write", failing_write):
                order.action_update_all_prices()

        self.assertAlmostEqual(self.product.standard_price, 80.0)
        self.assertAlmostEqual(other_product.standard_price, 70.0)
        self.assertEqual(
            self.env["product.value"].search_count([
                ("product_id", "in", (self.product | other_product).ids),
            ]),
            history_before,
        )
        self.assertEqual(
            order.order_line.read([
                "current_purchase_price",
                "current_sale_price",
                "current_standard_price",
            ]),
            snapshots_before,
        )

    def test_update_all_is_ordered_and_refreshes_final_values(self):
        self.product.with_company(self.company).last_purchase_price = 100.0
        order = self._create_order([
            self._line_values(sequence=20, price_unit=200.0),
            self._line_values(sequence=10, price_unit=120.0),
        ])
        order.action_fill_current_prices()
        order.action_update_all_prices()
        self.assertAlmostEqual(self.product.with_company(self.company).last_purchase_price, 200.0)
        self.assertAlmostEqual(self.product.lst_price, 300.0)
        self.assertTrue(order.order_line.sorted("sequence")[0].price_update_required)

    def test_actions_work_in_all_states(self):
        for state in ("draft", "sent", "to approve", "purchase", "cancel"):
            order = self._create_order()
            order.state = state
            order.action_fill_current_prices()
            order.order_line.action_update_product_prices()
            self.assertTrue(order.order_line.price_snapshot_initialized)

        order = self._create_order()
        order.write({"state": "purchase", "locked": True})
        order.action_fill_current_prices()
        order.order_line.action_update_product_prices()
        self.assertTrue(order.order_line.price_snapshot_initialized)

    def test_purchase_lifecycle_has_no_automatic_cost_side_effect(self):
        cost_before = self.product.standard_price
        order = self._create_order()
        duplicate = order.copy()
        self.assertFalse(duplicate.order_line.price_snapshot_initialized)

        order.button_confirm()
        self.assertAlmostEqual(self.product.standard_price, cost_before)
        order.button_lock()
        order.button_unlock()
        order.button_cancel()
        order.button_draft()
        order.order_line.price_unit = 140.0
        order.button_confirm()
        self.assertAlmostEqual(self.product.standard_price, cost_before)

        picking = order.picking_ids.filtered(lambda record: record.state != "cancel")[:1]
        if picking:
            picking.move_ids.quantity = picking.move_ids.product_uom_qty
            picking.button_validate()
            self.assertAlmostEqual(self.product.standard_price, cost_before)

    def test_company_specific_reference_price(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        product = self.product.with_context(allowed_company_ids=(self.company | other_company).ids)
        product.with_company(self.company).last_purchase_price = 100.0
        product.with_company(other_company).last_purchase_price = 250.0
        self.assertAlmostEqual(product.with_company(self.company).last_purchase_price, 100.0)
        self.assertAlmostEqual(product.with_company(other_company).last_purchase_price, 250.0)

    def test_purchase_user_cannot_bypass_product_access(self):
        user = self.env["res.users"].create({
            "name": "Restricted Purchase User",
            "login": "restricted_purchase_price_user",
            "company_id": self.company.id,
            "company_ids": [Command.set(self.company.ids)],
            "group_ids": [Command.set([
                self.env.ref("purchase.group_purchase_user").id,
            ])],
        })
        order = self._create_order()
        order.action_fill_current_prices()
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            order.order_line.with_user(user).action_update_product_prices()
        self.assertAlmostEqual(
            self.product.with_company(self.company).last_purchase_price,
            0.0,
        )
        self.assertAlmostEqual(self.product.standard_price, 80.0)
