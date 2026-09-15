from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged("post_install", "-at_install")
class TestPosOrderReportCost(TestPoSCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cost_product = cls.create_product("Report cost product", cls.categ_basic, 60, 40)
        cls.other_cost_product = cls.create_product("Other report product", cls.categ_basic, 50, 30)

    def setUp(self):
        super().setUp()
        self.config = self.basic_config
        self.open_new_session()
        self.Report = self.env["report.pos.order"]

    def _order(self, items, **values):
        """Create report sources without triggering cost calculation or stock moves."""
        total = sum(product.lst_price * qty for product, qty, cost in items)
        return self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "amount_total": total,
            "amount_tax": 0,
            "amount_paid": 0,
            "amount_return": 0,
            "currency_rate": 1,
            "lines": [Command.create({
                "product_id": product.id,
                "qty": qty,
                "price_unit": product.lst_price,
                "price_subtotal": product.lst_price * qty,
                "price_subtotal_incl": product.lst_price * qty,
                "tax_ids": [Command.clear()],
                "total_cost": cost,
                "is_total_cost_computed": False,
            }) for product, qty, cost in items],
            **values,
        })

    def _report(self, orders):
        # The SQL view is not an ORM dependency of its source lines.
        self.env.flush_all()
        self.Report.invalidate_model()
        return self.Report.search([("order_id", "in", orders.ids)])

    def test_sum_grouping_filters_and_join_cardinality(self):
        categories = self.env["pos.category"].create([
            {"name": "Report category A"}, {"name": "Report category B"},
        ])
        self.cost_product.pos_categ_ids = categories
        order = self._order([
            (self.cost_product, 2, 80), (self.other_cost_product, 1, 30),
        ])
        methods = self.config.payment_method_ids[:2]
        self.assertEqual(len(methods), 2)
        self.env["pos.payment"].create([
            {"pos_order_id": order.id, "payment_method_id": method.id, "amount": amount}
            for method, amount in zip(methods, (100, 70))
        ])
        rows = self._report(order)
        self.assertEqual(len(rows), 2)
        domain = [("order_id", "=", order.id)]
        self.assertEqual(self.Report._read_group(domain, [], ["total_cost:sum"]), [(110,)])
        grouped = self.Report._read_group(domain, ["product_id"], ["total_cost:sum"])
        self.assertEqual(dict(grouped), {self.cost_product: 80, self.other_cost_product: 30})
        monthly = self.Report._read_group(domain, ["date:month"], ["total_cost:sum"])
        self.assertEqual([amount for date, amount in monthly], [110])
        filtered = domain + [("product_id", "=", self.cost_product.id)]
        self.assertEqual(self.Report._read_group(filtered, [], ["total_cost:sum"]), [(80,)])
        self.assertEqual(sum(rows.mapped("margin")), 60)
        self.assertEqual(sum(rows.mapped("price_total")), 170)
        self.assertEqual(sum(rows.mapped("product_qty")), 3)

    def test_partial_return_preserves_saved_sign(self):
        sale = self._order([(self.cost_product, 2, 80)])
        refund = self._order([(self.cost_product, -1, -40)])
        refund.lines.refunded_orderline_id = sale.lines
        rows = self._report(sale | refund)
        self.assertEqual(sum(rows.mapped("total_cost")), 40)
        self.assertEqual(sum(rows.mapped("margin")), 20)
        self.assertEqual(sum(rows.mapped("price_subtotal_excl")), 60)

    def test_currency_conversion_and_missing_values(self):
        order = self._order([(self.cost_product, 2, 160)])
        # Finish the order's computed fields before setting the historical rate.
        self.env.flush_all()
        order.currency_rate = 2
        row = self._report(order)
        self.assertEqual(row.total_cost, 80)
        self.assertEqual(row.margin, -20)
        order.currency_rate = 0
        self.assertEqual(self._report(order).total_cost, 160)
        # ORM floats normalize missing values to zero. Exercise legacy SQL NULL
        # only in this isolated transaction to verify the view's fallback.
        self.env.cr.execute("UPDATE pos_order SET currency_rate = NULL WHERE id = %s", [order.id])
        order.invalidate_recordset(["currency_rate"])
        self.assertEqual(self._report(order).total_cost, 160)
        order.lines.total_cost = 0
        self.assertEqual(self._report(order).total_cost, 0)
        self.env.cr.execute("UPDATE pos_order_line SET total_cost = NULL WHERE id = %s", [order.lines.id])
        order.lines.invalidate_recordset(["total_cost"])
        self.assertEqual(self._report(order).total_cost, 0)
        self.assertFalse(order.lines.is_total_cost_computed)

    def test_saved_cost_refresh_and_view_reinitialization(self):
        order = self._order([(self.cost_product, 2, 0)])
        self.assertEqual(self._report(order).total_cost, 0)
        order.lines.total_cost = 80
        source_fields = ["total_cost", "is_total_cost_computed", "qty", "price_unit", "write_date"]
        self.env.flush_all()
        before = order.lines.read(source_fields)
        for iteration in range(2):
            row = self._report(order)
            self.assertEqual(row.total_cost, 80)
            self.assertEqual(row.margin, 40)
        self.Report.init()
        self.assertEqual(self._report(order).total_cost, 80)
        self.assertEqual(order.lines.read(source_fields), before)
        self.assertEqual(order.state, "draft")
        self.assertFalse(order.payment_ids or order.picking_ids or order.account_move)

    def test_cancelled_order_follows_standard_filter(self):
        order = self._order([(self.cost_product, 2, 80)])
        cancelled = self._order([(self.cost_product, 1, 40)])
        cancelled.action_pos_order_cancel()
        self._report(order | cancelled)
        domain = [("order_id", "in", (order | cancelled).ids)]
        self.assertEqual(self.Report._read_group(domain, [], ["total_cost:sum"]), [(120,)])
        domain.append(("state", "!=", "cancel"))
        self.assertEqual(self.Report._read_group(domain, [], ["total_cost:sum"]), [(80,)])

    def test_report_access_and_company_isolation(self):
        order = self._order([(self.cost_product, 2, 80)])
        other_data = self.setup_other_company(name="Report cost second company")
        other_company = other_data["company"]
        self.env.user.company_ids |= other_company
        config = self.env["pos.config"].with_company(other_company).create({
            "name": "Report cost second POS",
            "company_id": other_company.id,
            "journal_id": other_data["default_journal_sale"].id,
            "invoice_journal_id": other_data["default_journal_sale"].id,
        })
        session = self.env["pos.session"].with_company(other_company).create({"config_id": config.id})
        other_order = self._order(
            [(self.cost_product, 1, 30)], session_id=session.id, company_id=other_company.id,
        )
        self._report(order | other_order)
        user = new_test_user(
            self.env, login="report_cost_reader", groups="point_of_sale.group_pos_user",
            company_id=order.company_id.id,
            company_ids=[Command.set((order.company_id | other_company).ids)],
        )
        domain = [("order_id", "in", (order | other_order).ids)]
        report = self.Report.with_user(user).with_context(allowed_company_ids=order.company_id.ids)
        self.assertEqual(report._read_group(domain, [], ["total_cost:sum"]), [(80,)])
        report = report.with_context(allowed_company_ids=(order.company_id | other_company).ids)
        self.assertEqual(report._read_group(domain, [], ["total_cost:sum"]), [(110,)])
        outsider = new_test_user(self.env, login="report_cost_outsider", groups="base.group_portal")
        with self.assertRaises(AccessError):
            self.Report.with_user(outsider)._read_group(domain, [], ["total_cost:sum"])

    def test_measure_metadata_and_default_views(self):
        metadata = self.Report.fields_get(["total_cost"])["total_cost"]
        self.assertEqual(metadata["type"], "float")
        self.assertEqual(metadata["aggregator"], "sum")
        self.assertTrue(metadata["readonly"])
        self.assertEqual(metadata["string"], "Cost")
        for view_type, xmlid, defaults in (
            ("pivot", "point_of_sale.view_report_pos_order_pivot", ["order_id", "product_qty", "price_total"]),
            ("graph", "point_of_sale.view_report_pos_order_graph", ["price_total"]),
        ):
            view = self.Report.get_view(self.env.ref(xmlid).id, view_type)
            arch = etree.fromstring(view["arch"])
            self.assertEqual(arch.xpath("//field[@type='measure']/@name"), defaults)
            self.assertFalse(arch.xpath("//field[@name='total_cost'][@invisible]"))
