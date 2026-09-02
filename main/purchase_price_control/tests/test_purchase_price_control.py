from unittest.mock import patch

from lxml import etree

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.modules.module import load_script
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_path


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

    def _create_order(self, lines=None, company=None):
        company = company or self.company
        orders = self.env["purchase.order"].with_company(company).with_context(
            allowed_company_ids=(self.company | company).ids,
        )
        return orders.create({
            "partner_id": self.vendor.id,
            "company_id": company.id,
            "currency_id": company.currency_id.id,
            "date_order": fields.Datetime.now(),
            "order_line": [
                Command.create(values)
                for values in (lines or [self._line_values()])
            ],
        })

    def _create_purchase_tax(self):
        return self.env["account.tax"].create({
            "name": "Purchase Tax 20%",
            "amount": 20.0,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "company_id": self.company.id,
        })

    def test_purchase_order_view_price_column_order_and_labels(self):
        view = self.env.ref("purchase_price_control.purchase_order_view_form")
        arch = etree.fromstring(view.arch_db.encode())
        insertion = arch.xpath(
            "//xpath[contains(@expr, \"field[@name='price_unit']\")]"
        )[0]
        self.assertEqual(
            insertion.xpath("./field/@name"),
            [
                "current_standard_price",
                "current_markup",
                "current_sale_price",
                "planned_sale_price",
            ],
        )
        fields_by_name = self.env["purchase.order.line"]._fields
        self.assertEqual(fields_by_name["price_unit"].string, "Unit Price")
        self.assertEqual(fields_by_name["current_standard_price"].string, "Current Cost")
        self.assertEqual(fields_by_name["current_markup"].string, "Markup")
        self.assertEqual(fields_by_name["current_sale_price"].string, "Current Sale")
        self.assertEqual(fields_by_name["planned_sale_price"].string, "New Sale")
        self.assertFalse({
            "current_purchase_price",
            "effective_purchase_price",
            "valuation_purchase_price",
            "effective_cost_method",
        } & fields_by_name.keys())
        self.assertNotIn("last_purchase_price", self.env["product.product"]._fields)

    def test_fill_refill_snapshot_and_copy(self):
        order = self._create_order()
        line = order.order_line
        self.assertFalse(line.price_snapshot_initialized)
        self.assertFalse(line.planned_sale_price)

        order.action_fill_current_prices()
        self.assertTrue(line.price_snapshot_initialized)
        self.assertAlmostEqual(line.current_standard_price, 80.0)
        self.assertAlmostEqual(line.current_sale_price, 150.0)
        self.assertAlmostEqual(line.current_markup, 87.5)
        self.assertAlmostEqual(line.planned_sale_price, 187.5)

        self.product.with_company(self.company).write({
            "standard_price": 100.0,
            "lst_price": 160.0,
        })
        self.assertAlmostEqual(line.current_standard_price, 80.0)
        self.assertAlmostEqual(line.current_sale_price, 150.0)
        order.action_fill_current_prices()
        self.assertAlmostEqual(line.current_standard_price, 100.0)
        self.assertAlmostEqual(line.current_sale_price, 160.0)
        self.assertAlmostEqual(line.current_markup, 60.0)
        self.assertFalse(order.copy().order_line.price_snapshot_initialized)

    def test_default_markup_and_rounding(self):
        self.product.standard_price = 0.0
        self.company.purchase_default_markup = 30.0
        self.company.purchase_price_rounding = 10.0
        order = self._create_order()
        order.action_fill_current_prices()
        self.assertAlmostEqual(order.order_line.current_markup, 30.0)
        self.assertAlmostEqual(order.order_line.planned_sale_price, 130.0)
        with self.assertRaises(ValidationError):
            self.company.purchase_price_rounding = 0.0

    def test_manual_new_sale_is_exact_and_has_no_side_effects(self):
        order = self._create_order()
        order.action_fill_current_prices()
        line = order.order_line
        initial_markup = line.current_markup
        product_prices = (self.product.lst_price, self.product.standard_price)

        line.planned_sale_price = 12.0
        self.env.flush_all()
        line.invalidate_recordset(["planned_sale_price"])
        self.assertAlmostEqual(line.current_markup, initial_markup)
        self.assertAlmostEqual(line.planned_sale_price, 12.0)
        self.assertTrue(line.planned_sale_price_manually_set)
        self.assertEqual(
            (self.product.lst_price, self.product.standard_price),
            product_prices,
        )

    def test_manual_new_sale_survives_basis_and_tax_change(self):
        tax = self._create_purchase_tax()
        order = self._create_order()
        order.action_fill_current_prices()
        line = order.order_line
        initial_markup = line.current_markup
        line.planned_sale_price = 12.0

        line.write({
            "price_unit": 120.0,
            "tax_ids": [Command.set(tax.ids)],
        })
        self.assertAlmostEqual(line._get_purchase_price_basis(), 120.0)
        self.assertAlmostEqual(line.current_markup, initial_markup)
        self.assertAlmostEqual(line.planned_sale_price, 12.0)
        self.assertAlmostEqual(line.price_total, 144.0)

        order.action_fill_current_prices()
        self.assertFalse(line.planned_sale_price_manually_set)
        self.assertAlmostEqual(line.planned_sale_price, 225.0)

    def test_manual_new_sale_requires_initialized_product_line(self):
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

        downpayment_line = self._create_order().order_line
        downpayment_line.is_downpayment = True
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            downpayment_line.planned_sale_price = 100.0

    def test_tax_is_independent_from_discounted_purchase_uom_basis(self):
        tax = self._create_purchase_tax()
        dozen = self.env.ref("uom.product_uom_dozen")
        order = self._create_order([
            self._line_values(
                price_unit=120.0,
                discount=10.0,
                tax_ids=[Command.set(tax.ids)],
                product_uom_id=dozen.id,
            ),
            self._line_values(
                price_unit=120.0,
                discount=10.0,
                product_uom_id=dozen.id,
            ),
        ])
        order.action_fill_current_prices()
        taxed_line, untaxed_line = order.order_line
        self.assertAlmostEqual(taxed_line._get_purchase_price_basis(), 9.0)
        self.assertAlmostEqual(untaxed_line._get_purchase_price_basis(), 9.0)
        self.assertAlmostEqual(taxed_line.planned_sale_price, 16.88)
        self.assertAlmostEqual(untaxed_line.planned_sale_price, 16.88)
        self.assertAlmostEqual(taxed_line.price_subtotal, 108.0)
        self.assertAlmostEqual(taxed_line.price_tax, 21.6)
        self.assertAlmostEqual(taxed_line.price_total, 129.6)

        taxed_line.tax_ids = [Command.clear()]
        self.assertAlmostEqual(taxed_line.planned_sale_price, 16.88)
        self.assertAlmostEqual(taxed_line.price_total, 108.0)

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
        self.assertAlmostEqual(order.order_line._get_purchase_price_basis(), expected)

    def test_line_update_retry_and_confirm_have_explicit_side_effects_only(self):
        order = self._create_order()
        order.action_fill_current_prices()
        order.order_line.action_update_product_prices()
        self.assertAlmostEqual(self.product.lst_price, 187.5)
        self.assertAlmostEqual(self.product.standard_price, 100.0)
        self.assertFalse(order.has_price_updates)

        history_after_update = self.env["product.value"].search_count([
            ("product_id", "=", self.product.id),
        ])
        order.order_line.action_update_product_prices()
        self.assertEqual(
            self.env["product.value"].search_count([
                ("product_id", "=", self.product.id),
            ]),
            history_after_update,
        )

        order.order_line.price_unit = 125.0
        prices_before_confirm = (self.product.lst_price, self.product.standard_price)
        order.button_confirm()
        self.assertEqual(
            (self.product.lst_price, self.product.standard_price),
            prices_before_confirm,
        )

    def test_avco_and_fifo_do_not_update_cost(self):
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
        order = self._create_order([self._line_values(product=product)])
        order.action_fill_current_prices()
        cost_before = product.standard_price
        lot_cost_before = lot.standard_price
        order.order_line.action_update_product_prices()
        self.assertAlmostEqual(product.standard_price, cost_before)
        self.assertAlmostEqual(lot.standard_price, lot_cost_before)
        self.assertAlmostEqual(product.lst_price, 187.5)

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
            "lst_price": 100.0,
            "standard_price": 80.0,
        })
        order = self._create_order()
        order.action_fill_current_prices()
        order.order_line.planned_sale_price = 100.0
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

    def test_bulk_repeated_product_is_ordered_and_creates_one_final_cost(self):
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
        self.assertAlmostEqual(self.product.lst_price, 375.0)
        self.assertEqual(history_after, history_before + 1)
        self.assertTrue(order.order_line.sorted("sequence")[0].price_update_required)

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
            "current_sale_price",
            "current_standard_price",
            "current_markup",
        ])
        product_values_before = {
            product.id: (product.lst_price, product.standard_price)
            for product in self.product | other_product
        }
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

        for product in self.product | other_product:
            self.assertEqual(
                (product.lst_price, product.standard_price),
                product_values_before[product.id],
            )
        self.assertEqual(
            self.env["product.value"].search_count([
                ("product_id", "in", (self.product | other_product).ids),
            ]),
            history_before,
        )
        self.assertEqual(
            order.order_line.read([
                "current_sale_price",
                "current_standard_price",
                "current_markup",
            ]),
            snapshots_before,
        )

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

    def test_purchase_lifecycle_has_no_automatic_price_side_effect(self):
        values_before = (self.product.lst_price, self.product.standard_price)
        order = self._create_order()
        duplicate = order.copy()
        self.assertFalse(duplicate.order_line.price_snapshot_initialized)

        order.button_confirm()
        self.assertEqual(
            (self.product.lst_price, self.product.standard_price),
            values_before,
        )
        order.button_lock()
        order.button_unlock()
        order.button_cancel()
        order.button_draft()
        order.order_line.price_unit = 140.0
        order.button_confirm()
        self.assertEqual(
            (self.product.lst_price, self.product.standard_price),
            values_before,
        )

    def test_double_validation_has_no_automatic_price_side_effect(self):
        self.company.write({
            "po_double_validation": "two_step",
            "po_double_validation_amount": 0.0,
        })
        user = self.env["res.users"].create({
            "name": "Purchase Approval Requester",
            "login": "purchase_price_approval_requester",
            "company_id": self.company.id,
            "company_ids": [Command.set(self.company.ids)],
            "group_ids": [Command.set([
                self.env.ref("purchase.group_purchase_user").id,
            ])],
        })
        order = self._create_order()
        order.action_fill_current_prices()
        values_before = (self.product.lst_price, self.product.standard_price)
        snapshot_before = order.order_line.read([
            "current_sale_price",
            "current_standard_price",
            "current_markup",
        ])

        order.with_user(user).button_confirm()
        self.assertEqual(order.state, "to approve")
        self.assertEqual(
            (self.product.lst_price, self.product.standard_price),
            values_before,
        )
        order.button_approve()
        self.assertEqual(order.state, "purchase")
        self.assertEqual(
            (self.product.lst_price, self.product.standard_price),
            values_before,
        )
        self.assertEqual(
            order.order_line.read([
                "current_sale_price",
                "current_standard_price",
                "current_markup",
            ]),
            snapshot_before,
        )

    def test_current_cost_is_company_specific(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        product = self.product.with_context(
            allowed_company_ids=(self.company | other_company).ids,
        )
        product.with_company(self.company).standard_price = 100.0
        product.with_company(other_company).standard_price = 250.0

        own_order = self._create_order(company=self.company)
        other_order = self._create_order(company=other_company)
        own_order.action_fill_current_prices()
        other_order.action_fill_current_prices()
        self.assertAlmostEqual(own_order.order_line.current_standard_price, 100.0)
        self.assertAlmostEqual(other_order.order_line.current_standard_price, 250.0)

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
        self.assertAlmostEqual(self.product.lst_price, 150.0)
        self.assertAlmostEqual(self.product.standard_price, 80.0)

    def test_snapshot_markup_migration_is_company_safe_and_idempotent(self):
        self.company.purchase_default_markup = 30.0
        first_order = self._create_order()
        first_order.action_fill_current_prices()
        first_line = first_order.order_line
        first_line.write({
            "current_standard_price": 100.0,
            "current_sale_price": 150.0,
            "current_markup": 999.0,
        })
        first_line.planned_sale_price = 12.0

        other_company = self.env["res.company"].create({
            "name": "Migration Company",
            "purchase_default_markup": 40.0,
        })
        second_order = self._create_order(company=other_company)
        second_order.action_fill_current_prices()
        second_line = second_order.order_line
        second_line.write({
            "current_standard_price": 0.0,
            "current_sale_price": 200.0,
            "current_markup": 999.0,
        })
        state_before = first_order.state
        product_values_before = (self.product.lst_price, self.product.standard_price)
        self.env.flush_all()

        migration = load_script(
            file_path(
                "purchase_price_control/migrations/19.0.4.0.0/post-migrate.py"
            ),
            "test_purchase_price_control_post_migrate",
        )
        migration.migrate(self.env.cr, "19.0.3.1.0")
        migration.migrate(self.env.cr, "19.0.3.1.0")
        first_line.invalidate_recordset()
        second_line.invalidate_recordset()

        self.assertAlmostEqual(first_line.current_markup, 50.0)
        self.assertAlmostEqual(first_line.planned_sale_price, 12.0)
        self.assertAlmostEqual(second_line.current_markup, 40.0)
        self.assertEqual(first_order.state, state_before)
        self.assertEqual(
            (self.product.lst_price, self.product.standard_price),
            product_values_before,
        )
