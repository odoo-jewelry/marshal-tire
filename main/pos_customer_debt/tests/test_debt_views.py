from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPosCustomerDebtViews(TransactionCase):
    def test_standard_orders_keep_default_views_and_columns(self):
        action = self.env.ref("point_of_sale.action_pos_pos_form")
        list_view_id = next(
            view_id for view_id, view_type in action.views if view_type == "list"
        )
        list_view = self.env["pos.order"].get_view(list_view_id, "list")
        self.assertEqual(
            list_view["id"], self.env.ref("point_of_sale.view_pos_order_tree").id
        )
        arch = etree.fromstring(list_view["arch"])
        columns = arch.xpath("./field/@name")
        required = ["pos_reference", "partner_id", "amount_total", "state"]
        for name in required:
            self.assertIn(name, columns)
        self.assertEqual([name for name in columns if name in required], required)
        self._assert_debt_columns_optional(arch, "hide")
        known = arch.xpath("./field[@name='debt_residual_known']")
        self.assertEqual(len(known), 1)
        self.assertIn(known[0].get("column_invisible"), ("1", "True"))

        search_view = self.env["pos.order"].get_view(
            action.search_view_id.id, "search"
        )
        self.assertEqual(
            search_view["id"], self.env.ref("point_of_sale.view_pos_order_filter").id
        )
        search_arch = etree.fromstring(search_view["arch"])
        self.assertTrue(search_arch.xpath("./field[@name='pos_reference']"))
        self.assertTrue(search_arch.xpath("./filter[@name='cancelled']"))

    def test_debt_action_keeps_dedicated_views_and_visible_debt_columns(self):
        action = self.env.ref("pos_customer_debt.action_pos_customer_debt")
        list_view = self.env.ref("pos_customer_debt.view_pos_customer_debt_list")
        search_view = self.env.ref("pos_customer_debt.view_pos_customer_debt_search")
        self.assertEqual(action.view_id, list_view)
        self.assertEqual(action.search_view_id, search_view)
        self.assertIn((list_view.id, "list"), action.views)

        view = self.env["pos.order"].get_view(list_view.id, "list")
        self.assertEqual(view["id"], list_view.id)
        self._assert_debt_columns_optional(etree.fromstring(view["arch"]), "show")
        view = self.env["pos.order"].get_view(search_view.id, "search")
        self.assertEqual(view["id"], search_view.id)
        arch = etree.fromstring(view["arch"])
        for name in ("outstanding", "settled", "review_required"):
            self.assertTrue(arch.xpath("./filter[@name=$name]", name=name))

    def _assert_debt_columns_optional(self, arch, visibility):
        for name in (
            "debt_original_amount",
            "debt_payment_amount",
            "debt_adjustment_amount",
            "debt_residual_amount",
            "debt_state",
            "debt_review_reason",
        ):
            with self.subTest(field=name, visibility=visibility):
                self.assertEqual(
                    arch.xpath("./field[@name=$name]/@optional", name=name),
                    [visibility],
                )
