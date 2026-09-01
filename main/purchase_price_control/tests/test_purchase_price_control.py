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

    def _create_order(self, lines, **order_values):
        values = {
            "partner_id": self.vendor.id,
            "company_id": self.company.id,
            "currency_id": self.company.currency_id.id,
            "date_order": fields.Datetime.now(),
            "order_line": [Command.create(line_values) for line_values in lines],
        }
        values.update(order_values)
        return self.env["purchase.order"].create(values)

    def _product_line_values(self, **values):
        line_values = {
            "name": self.product.name,
            "product_id": self.product.id,
            "product_qty": 1.0,
            "product_uom_id": self.product.uom_id.id,
            "price_unit": 100.0,
            "tax_ids": [Command.clear()],
            "date_planned": fields.Datetime.now(),
        }
        line_values.update(values)
        return line_values

    def test_markup_and_default_markup(self):
        self.product.with_company(self.company).last_purchase_price = 100.0
        line = self._create_order([self._product_line_values()]).order_line
        self.assertAlmostEqual(line.current_purchase_price, 100.0)
        self.assertAlmostEqual(line.current_sale_price, 150.0)
        self.assertAlmostEqual(line.current_markup, 50.0)
        self.assertAlmostEqual(line.planned_sale_price, 150.0)

        self.product.with_company(self.company).last_purchase_price = 0.0
        self.company.purchase_default_markup = 30.0
        self.assertAlmostEqual(line.current_markup, 30.0)
        self.assertAlmostEqual(line.planned_sale_price, 130.0)

    def test_discount_tax_and_purchase_uom(self):
        tax = self.env["account.tax"].create({
            "name": "Purchase Tax 20%",
            "amount": 20.0,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "company_id": self.company.id,
        })
        dozen = self.env.ref("uom.product_uom_dozen")
        line = self._create_order([self._product_line_values(
            price_unit=120.0,
            discount=10.0,
            tax_ids=[Command.set(tax.ids)],
            product_uom_id=dozen.id,
        )]).order_line
        self.assertAlmostEqual(line.effective_purchase_price, 10.8)

        included_tax = tax.copy({
            "name": "Purchase Tax Included 20%",
            "price_include_override": "tax_included",
        })
        line.tax_ids = included_tax
        self.assertAlmostEqual(line.effective_purchase_price, 9.0)

    def test_currency_conversion_uses_order_currency(self):
        currency = self.env["res.currency"].create({
            "name": "XPC",
            "symbol": "XPC",
            "rounding": 0.01,
            "rate_ids": [Command.create({
                "name": fields.Date.today(),
                "rate": 2.0,
                "company_id": self.company.id,
            })],
        })
        line = self._create_order(
            [self._product_line_values(price_unit=200.0)],
            currency_id=currency.id,
        ).order_line
        expected = currency._convert(
            200.0,
            self.company.currency_id,
            self.company,
            line.date_order,
            round=False,
        )
        self.assertAlmostEqual(line.effective_purchase_price, expected)

    def test_rounding_boundaries(self):
        self.company.purchase_default_markup = 0.0
        line = self._create_order([self._product_line_values(price_unit=121.0)]).order_line

        self.company.purchase_price_rounding = 10.0
        self.assertAlmostEqual(line.planned_sale_price, 130.0)
        line.price_unit = 120.0
        self.assertAlmostEqual(line.planned_sale_price, 120.0)

        self.company.purchase_price_rounding = 0.1
        line.price_unit = 12.341
        self.assertAlmostEqual(line.planned_sale_price, 12.4)

    def test_rounding_step_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self.company.purchase_price_rounding = 0.0

    def test_save_selected_line_only_and_preserve_cost(self):
        selected_product = self.product
        unselected_product = self.env["product.product"].create({
            "name": "Unselected Product",
            "is_storable": True,
            "list_price": 75.0,
            "standard_price": 40.0,
            "supplier_taxes_id": [Command.clear()],
        })
        selected_cost = selected_product.standard_price
        unselected_sale_price = unselected_product.lst_price
        order = self._create_order([
            self._product_line_values(price_unit=110.0, save_prices=True),
            self._product_line_values(
                name=unselected_product.name,
                product_id=unselected_product.id,
                product_uom_id=unselected_product.uom_id.id,
                price_unit=60.0,
                save_prices=False,
            ),
            {
                "name": "Notes",
                "display_type": "line_note",
                "product_qty": 0.0,
                "save_prices": True,
            },
        ])

        order.button_confirm()

        self.assertEqual(order.state, "purchase")
        self.assertAlmostEqual(selected_product.with_company(self.company).last_purchase_price, 110.0)
        self.assertAlmostEqual(selected_product.standard_price, selected_cost)
        self.assertAlmostEqual(unselected_product.with_company(self.company).last_purchase_price, 0.0)
        self.assertAlmostEqual(unselected_product.lst_price, unselected_sale_price)

    def test_lines_are_applied_in_sequence_order(self):
        self.product.with_company(self.company).last_purchase_price = 100.0
        order = self._create_order([
            self._product_line_values(sequence=20, price_unit=200.0, save_prices=True),
            self._product_line_values(sequence=10, price_unit=120.0, save_prices=True),
        ])

        order.button_confirm()

        self.assertAlmostEqual(self.product.with_company(self.company).last_purchase_price, 200.0)
        self.assertAlmostEqual(self.product.lst_price, 300.0)

    def test_copy_cancel_and_reconfirm_lifecycle(self):
        order = self._create_order([self._product_line_values(price_unit=100.0, save_prices=True)])
        copied_order = order.copy()
        self.assertFalse(any(copied_order.order_line.mapped("save_prices")))

        order.button_confirm()
        saved_purchase_price = self.product.with_company(self.company).last_purchase_price
        saved_sale_price = self.product.lst_price
        order.button_cancel()
        self.assertAlmostEqual(self.product.with_company(self.company).last_purchase_price, saved_purchase_price)
        self.assertAlmostEqual(self.product.lst_price, saved_sale_price)

        order.button_draft()
        order.order_line.price_unit = 130.0
        order.button_confirm()
        self.assertAlmostEqual(self.product.with_company(self.company).last_purchase_price, 130.0)

    def test_double_validation_saves_on_confirm(self):
        self.company.write({
            "po_double_validation": "two_step",
            "po_double_validation_amount": 1.0,
        })
        user = self.env["res.users"].create({
            "name": "Purchase Price Controller",
            "login": "purchase_price_controller",
            "company_id": self.company.id,
            "company_ids": [Command.set(self.company.ids)],
            "group_ids": [Command.set([
                self.env.ref("purchase.group_purchase_user").id,
                self.env.ref("product.group_product_manager").id,
            ])],
        })
        order = self._create_order([self._product_line_values(price_unit=125.0, save_prices=True)])

        order.with_user(user).button_confirm()

        self.assertEqual(order.state, "to approve")
        self.assertAlmostEqual(self.product.with_company(self.company).last_purchase_price, 125.0)
        order.button_approve()
        self.assertAlmostEqual(self.product.with_company(self.company).last_purchase_price, 125.0)

    def test_company_dependent_reference_and_settings(self):
        other_company = self.env["res.company"].create({"name": "Other Price Control Company"})
        product = self.product.with_context(allowed_company_ids=(self.company | other_company).ids)
        product.with_company(self.company).last_purchase_price = 100.0
        product.with_company(other_company).last_purchase_price = 250.0
        self.company.purchase_default_markup = 10.0
        other_company.purchase_default_markup = 35.0

        self.assertAlmostEqual(product.with_company(self.company).last_purchase_price, 100.0)
        self.assertAlmostEqual(product.with_company(other_company).last_purchase_price, 250.0)
        self.assertAlmostEqual(self.company.purchase_default_markup, 10.0)
        self.assertAlmostEqual(other_company.purchase_default_markup, 35.0)

    def test_purchase_user_cannot_bypass_product_access(self):
        user = self.env["res.users"].create({
            "name": "Restricted Purchase User",
            "login": "restricted_purchase_price_user",
            "company_id": self.company.id,
            "company_ids": [Command.set(self.company.ids)],
            "group_ids": [Command.set([self.env.ref("purchase.group_purchase_user").id])],
        })
        order = self._create_order([self._product_line_values(price_unit=115.0, save_prices=True)])

        with self.assertRaises(AccessError):
            order.with_user(user).button_confirm()

        self.assertEqual(order.state, "draft")
        self.assertAlmostEqual(self.product.with_company(self.company).last_purchase_price, 0.0)

    def test_reference_price_does_not_change_any_cost_method(self):
        for cost_method in ("standard", "average", "fifo"):
            category = self.env["product.category"].create({
                "name": f"Price Control {cost_method}",
                "property_cost_method": cost_method,
            })
            product = self.env["product.product"].create({
                "name": f"Price Control {cost_method}",
                "is_storable": True,
                "categ_id": category.id,
                "standard_price": 42.0,
                "supplier_taxes_id": [Command.clear()],
            })
            cost_before = product.standard_price

            product.with_company(self.company).last_purchase_price = 99.0

            self.assertAlmostEqual(product.standard_price, cost_before)
            self.assertAlmostEqual(product.with_company(self.company).last_purchase_price, 99.0)

        lot_product = self.env["product.product"].create({
            "name": "Lot-valuated Price Control Product",
            "is_storable": True,
            "tracking": "lot",
            "lot_valuated": True,
            "standard_price": 55.0,
            "supplier_taxes_id": [Command.clear()],
        })
        lot = self.env["stock.lot"].create({
            "name": "PRICE-CONTROL-LOT",
            "product_id": lot_product.id,
        })
        lot_cost_before = lot.standard_price

        lot_product.with_company(self.company).last_purchase_price = 125.0

        self.assertAlmostEqual(lot.standard_price, lot_cost_before)
