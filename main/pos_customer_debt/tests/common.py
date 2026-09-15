from odoo import Command, fields
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


class PosCustomerDebtCommon(TestPoSCommon):
    def setUp(self):
        super().setUp()
        self.env.user.write(
            {
                "group_ids": [
                    Command.link(
                        self.env.ref(
                            "pos_customer_debt.group_pos_customer_debt_settler"
                        ).id
                    )
                ]
            }
        )
        self.config = self.basic_config
        self.product100 = self.create_product(
            "Debt Product 100", self.categ_basic, 100, 50
        )

    def _close_orders(self, order_parameters, payment_methods=None):
        session = self._start_pos_session(
            payment_methods or (self.cash_pm1 | self.bank_pm1 | self.pay_later_pm), 0
        )
        orders = self._create_orders(order_parameters)
        cash_method = session.payment_method_ids.filtered("is_cash_count")[:1]
        cash_total = sum(
            session.order_ids.payment_ids.filtered(
                lambda payment: payment.payment_method_id == cash_method
            ).mapped("amount")
        )
        if cash_method:
            session.post_closing_cash_details(cash_total)
        session.close_session_from_ui()
        return session, orders

    def _pay_later_order_values(self, uuid, cash=0.0, debt=100.0, **extra):
        payments = []
        if cash:
            payments.append((self.cash_pm1, cash))
        payments.append((self.pay_later_pm, debt))
        return {
            "pos_order_lines_ui_args": [(self.product100, 1)],
            "payments": payments,
            "customer": self.customer,
            "is_invoiced": False,
            "uuid": uuid,
            **extra,
        }

    def _create_incoming_payment(self, amount, currency=None):
        journal = self.company_data["default_journal_bank"]
        payment = self.env["account.payment"].create(
            {
                "amount": amount,
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.customer.id,
                "journal_id": journal.id,
                "currency_id": (currency or self.company.currency_id).id,
                "payment_method_line_id": journal.inbound_payment_method_line_ids[:1].id,
                "destination_account_id": self.customer.with_company(
                    self.company
                ).property_account_receivable_id.id,
                "date": fields.Date.today(),
            }
        )
        return payment
