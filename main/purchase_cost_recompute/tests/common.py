from freezegun import freeze_time

from odoo import Command
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


class PurchaseCostRecomputeCommon(TestPoSCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.inventory_valuation = "periodic"
        cls.env.user.group_ids |= (
            cls.env.ref("purchase.group_purchase_manager")
            | cls.env.ref("stock.group_stock_manager")
        )
        cls.env["decimal.precision"].search([("name", "=", "Product Price")]).digits = 2
        cls.category = cls.categ_basic.copy({
            "name": "Purchase correction FIFO", "property_cost_method": "fifo",
        })
        cls.product = cls.create_product("Purchase correction product", cls.category, 200, 100)
        cls.vendor = cls.env["res.partner"].create({"name": "Purchase correction vendor"})
        cls.tax = cls.env["account.tax"].create({
            "name": "Purchase correction 20%", "type_tax_use": "purchase",
            "amount_type": "percent", "amount": 20,
            "company_id": cls.company.id,
            "invoice_repartition_line_ids": [
                Command.create({"repartition_type": "base"}),
                Command.create({
                    "repartition_type": "tax",
                    "account_id": cls.company_data["default_account_tax_purchase"].id,
                }),
            ],
            "refund_repartition_line_ids": [
                Command.create({"repartition_type": "base"}),
                Command.create({
                    "repartition_type": "tax",
                    "account_id": cls.company_data["default_account_tax_purchase"].id,
                }),
            ],
        })
        cls.stock_location = cls.basic_config.picking_type_id.default_location_src_id
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")

    def setUp(self):
        super().setUp()
        self.config = self.basic_config

    def _purchase(self, price=100, quantity=2, product=None, taxes=None, discount=0,
                  date="2026-01-01 10:00:00", receive=True, company=None):
        product = product if product is not None else self.product
        taxes = taxes if taxes is not None else self.tax
        company = company if company is not None else self.env.company
        Order = self.env["purchase.order"].with_company(company).with_context(allowed_company_ids=company.ids)
        with freeze_time(date):
            order = Order.create({
                "partner_id": self.vendor.id,
                "company_id": company.id,
                "currency_id": company.currency_id.id,
                "date_order": date,
                "order_line": [Command.create({
                    "product_id": product.id, "product_qty": quantity,
                    "product_uom_id": product.uom_id.id,
                    "price_unit": price, "discount": discount,
                    "tax_ids": [Command.set(taxes.ids)], "date_planned": date,
                })],
            })
            order.button_confirm()
            if order.locked:
                order.button_unlock()
            if receive:
                moves = order.order_line.move_ids
                for move in moves:
                    move.quantity = move.product_uom_qty
                moves.picked = True
                moves._action_done()
            return order

    def _move(self, quantity, date, product=None, origin=None, incoming=False):
        product = product if product is not None else self.product
        source = self.customer_location if origin else self.supplier_location
        if not incoming and not origin:
            source = self.stock_location
        destination = self.stock_location if incoming or origin else self.customer_location
        with freeze_time(date):
            move = self.env["stock.move"].create({
                "product_id": product.id, "product_uom": product.uom_id.id,
                "product_uom_qty": quantity, "location_id": source.id,
                "location_dest_id": destination.id, "company_id": self.env.company.id,
                "origin_returned_move_id": origin.id if origin else False,
            })
            move._action_confirm(merge=False)
            move.quantity = quantity
            move.picked = True
            move._action_done()
            return move

    def _pos_order(self, quantity=1, date="2026-01-02 10:00:00", refund_line=None,
                   invoiced=False):
        with freeze_time(date):
            if not self.config.current_session_id:
                self._start_pos_session(self.cash_pm1 | self.bank_pm1, 0)
            line = {"product": self.product, "quantity": quantity}
            if refund_line:
                line["refunded_orderline_id"] = refund_line.id
            values = self.create_ui_order_data(
                [line], customer=self.customer, is_invoiced=invoiced,
                payments=[(self.bank_pm1, self.product.lst_price * quantity)],
            )
            result = self.env["pos.order"].with_context(generate_pdf=False).sync_from_ui([values])
            # Refund synchronization also returns the original sale for refresh.
            return self.env["pos.order"].browse([
                order["id"] for order in result["pos.order"] if order["uuid"] == values["uuid"]
            ])

    def _close_pos_session(self, date="2026-01-03 10:00:00"):
        with freeze_time(date):
            self.pos_session.post_closing_cash_details(0)
            self.pos_session.close_session_from_ui()
        self.assertEqual(self.pos_session.state, "closed")
