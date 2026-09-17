from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged("post_install", "-at_install")
class TestPosCompanyAutoInvoice(TestPoSCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        cls.company_customer = cls.customer.copy({"is_company": True})

    def test_settings_persist_and_load_for_each_pos(self):
        other_config = self.config.copy({"name": "Independent invoice preference"})
        self.assertFalse(self.config.auto_invoice_company_customer)
        self.assertFalse(other_config.auto_invoice_company_customer)

        settings = self.env["res.config.settings"].create({
            "pos_config_id": self.config.id,
            "pos_auto_invoice_company_customer": True,
        })
        settings.set_values()
        reopened = self.env["res.config.settings"].create({
            "pos_config_id": self.config.id,
        })
        self.assertTrue(reopened.pos_auto_invoice_company_customer)
        self.assertFalse(other_config.auto_invoice_company_customer)

        for config, expected in ((self.config, True), (other_config, False)):
            with self.subTest(config=config.name):
                [data] = config._load_pos_data_read(config, config)
                self.assertEqual(data["auto_invoice_company_customer"], expected)
                self.assertEqual(data["id"], config.id)
                self.assertIn("payment_method_ids", data)
                self.assertIn("invoice_journal_id", data)

        reopened.pos_auto_invoice_company_customer = False
        reopened.set_values()
        self.assertFalse(self.config.auto_invoice_company_customer)

    def test_configuration_access_uses_standard_permissions(self):
        employee = new_test_user(
            self.env, login="invoice_preference_employee", groups="base.group_user",
            company_id=self.company.id, company_ids=[Command.set(self.company.ids)],
        )
        with self.assertRaises(AccessError):
            self.config.with_user(employee).write({"auto_invoice_company_customer": True})
        self.assertFalse(self.config.auto_invoice_company_customer)

        manager = new_test_user(
            self.env, login="invoice_preference_manager",
            groups="point_of_sale.group_pos_manager",
            company_id=self.company.id, company_ids=[Command.set(self.company.ids)],
        )
        self.config.with_user(manager).write({"auto_invoice_company_customer": True})
        self.assertTrue(self.config.auto_invoice_company_customer)

        other_company = self.env["res.company"].create({"name": "Other invoice company"})
        other_manager = new_test_user(
            self.env, login="invoice_preference_other_manager",
            groups="point_of_sale.group_pos_manager",
            company_id=other_company.id, company_ids=[Command.set(other_company.ids)],
        )
        with self.assertRaises(AccessError):
            self.config.with_user(other_manager).with_context(
                allowed_company_ids=other_company.ids
            ).write({"auto_invoice_company_customer": False})
        self.assertTrue(self.config.auto_invoice_company_customer)

    def test_checkout_honors_explicit_invoice_choice(self):
        self._start_pos_session(self.cash_pm1, 0)
        product = self.create_product("Invoice preference service", self.categ_basic, 100, 0)
        product.type = "service"

        for automatic in (False, True):
            self.config.auto_invoice_company_customer = automatic
            for invoice in (False, True):
                with self.subTest(automatic=automatic, invoice=invoice):
                    uuid = f"company-invoice-choice-{automatic}-{invoice}"
                    data = self.create_ui_order_data(
                        [(product, 1)], payments=[(self.cash_pm1, 100)],
                        customer=self.company_customer, is_invoiced=invoice, uuid=uuid,
                    )
                    self.env["pos.order"].with_context(generate_pdf=False).sync_from_ui([data])
                    order = self.env["pos.order"].search([("uuid", "=", uuid)])
                    self.assertEqual(bool(order.account_move), invoice)
                    self.assertEqual(order.to_invoice, invoice)
                    self.assertEqual(order.amount_total, 100)
                    self.assertEqual(order.amount_paid, 100)
                    self.assertEqual(order.partner_id, self.company_customer)
                    self.assertEqual(order.state, "done" if invoice else "paid")
                    if invoice:
                        self.assertEqual(order.account_move.state, "posted")
                        self.assertEqual(order.account_move.amount_total, 100)
