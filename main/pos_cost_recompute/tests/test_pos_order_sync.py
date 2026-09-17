from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


_REVISION = "cost_recompute_revision"


@tagged("post_install", "-at_install")
class TestPosOrderSourceRevisionSync(TestPoSCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.create_product("POS source revision product", cls.categ_basic, 60, 40)
        cls.adjust_inventory((cls.product,), (10,))
        cls.cashier = new_test_user(
            cls.env, login="source-revision-cashier",
            groups="base.group_user,point_of_sale.group_pos_user",
            company_id=cls.env.company.id, lang="en_US",
        )

    def setUp(self):
        super().setUp()
        self.config = self.basic_config
        self._start_pos_session(self.cash_pm1 | self.bank_pm1, 0)
        self.cashier_orders = self.env["pos.order"].with_user(self.cashier).with_context(lang="en_US")

    def _order_data(self, state="paid", uuid=None, **values):
        payments = [] if state == "draft" else [
            (self.bank_pm1, self.pricelist._get_product_price(self.product, 1)),
        ]
        return self.create_ui_order_data(
            [(self.product, 1)], customer=self.customer, payments=payments, uuid=uuid,
            pos_order_ui_args={"state": state, "user_id": self.cashier.id, **values},
        )

    def _sync(self, values):
        result = self.cashier_orders.sync_from_ui([values])
        self.assertEqual(len(result["pos.order"]), 1)
        self.assertNotIn(_REVISION, result["pos.order"][0])
        return self.cashier_orders.browse(result["pos.order"][0]["id"])

    def test_cashier_paid_orders_ignore_client_revision(self):
        self.assertFalse(self.cashier.has_group("point_of_sale.group_pos_manager"))
        for revision in (False, 987654):
            with self.subTest(revision=revision):
                values = self._order_data(**{_REVISION: revision})
                order = self._sync(values)
                self.assertEqual(order.state, "paid")
                self.assertEqual(order.user_id, self.cashier)
                self.assertEqual(order.amount_paid, order.amount_total)
                self.assertEqual(order.lines.total_cost, 40)
                self.assertGreater(order.cost_recompute_revision, 0)
                self.assertLess(order.cost_recompute_revision, 987654)
                self.assertEqual(values[_REVISION], revision)

    def test_draft_retry_and_payment_preserve_server_revision(self):
        order = self._sync(self._order_data(state="draft", **{_REVISION: False}))
        self.assertEqual(order.state, "draft")
        stale_revision = order.cost_recompute_revision
        order.lines.write({"customer_note": "Changed after the first sync"})
        current_revision = order.cost_recompute_revision
        self.assertGreater(current_revision, stale_revision)

        resent = self._sync(self._order_data(
            state="draft", uuid=order.uuid,
            lines=[Command.update(order.lines.id, {"customer_note": "Updated in POS"})],
            **{_REVISION: stale_revision},
        ))
        self.assertEqual(resent, order)
        self.assertEqual(order.state, "draft")
        self.assertEqual(order.lines.customer_note, "Updated in POS")
        self.assertGreater(order.cost_recompute_revision, current_revision)
        current_revision = order.cost_recompute_revision

        paid = self._sync(self._order_data(
            uuid=order.uuid, lines=[], **{_REVISION: 987654},
        ))
        self.assertEqual(paid, order)
        self.assertEqual(order.state, "paid")
        self.assertEqual(len(order.lines), 1)
        self.assertEqual(order.amount_paid, order.amount_total)
        self.assertGreater(order.cost_recompute_revision, current_revision)
        self.assertLess(order.cost_recompute_revision, 987654)

    def test_revision_is_excluded_from_pos_loading(self):
        order = self._sync(self._order_data(state="draft"))
        session = self.pos_session.with_user(self.cashier)
        parameters = session.load_data_params()["pos.order"]
        self.assertNotIn(_REVISION, parameters["fields"])
        self.assertNotIn(_REVISION, parameters["relations"])
        self.assertTrue({"id", "uuid", "state", "lines", "payment_ids"}.issubset(
            parameters["fields"],
        ))
        loaded_orders = session.load_data(["pos.order"])["pos.order"]
        self.assertEqual([values["id"] for values in loaded_orders], order.ids)
        self.assertNotIn(_REVISION, loaded_orders[0])

    def test_direct_revision_changes_remain_forbidden(self):
        order = self._sync(self._order_data(state="draft"))
        revision_before = order.cost_recompute_revision
        for revision in (False, 987654):
            with self.subTest(revision=revision):
                with self.assertRaisesRegex(AccessError, "Source versions are server-managed"):
                    self.cashier_orders.create(self._order_data(
                        state="draft", **{_REVISION: revision},
                    ))
                with self.assertRaisesRegex(AccessError, "Source versions are server-managed"):
                    order.write({_REVISION: revision})
                with self.assertRaisesRegex(AccessError, "Source versions are server-managed"):
                    self.cashier_orders.with_context(**{
                        "default_" + _REVISION: revision,
                    }).create(self._order_data(state="draft"))
        self.assertEqual(order.cost_recompute_revision, revision_before)
