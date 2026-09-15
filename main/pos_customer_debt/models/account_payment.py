from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    pos_debt_accounting_partner_id = fields.Many2one(
        related="partner_id.commercial_partner_id",
        store=True,
        string="Accounting Customer",
    )
    pos_debt_allocation_ids = fields.One2many(
        "pos.customer.debt.allocation",
        "payment_id",
        string="POS Debt Allocations",
        copy=False,
    )
    pos_debt_allocated_amount = fields.Monetary(
        compute="_compute_pos_debt_amounts",
        string="Effective POS Debt Settlement",
        currency_field="currency_id",
    )
    pos_debt_available_amount = fields.Monetary(
        compute="_compute_pos_debt_amounts",
        string="Available for POS Debt",
        currency_field="currency_id",
    )
    has_draft_pos_debt_allocations = fields.Boolean(
        compute="_compute_pos_debt_amounts"
    )

    @api.depends(
        "pos_debt_allocation_ids.effective_amount",
        "move_id.line_ids.amount_residual_currency",
        "state",
    )
    def _compute_pos_debt_amounts(self):
        for payment in self:
            payment.pos_debt_allocated_amount = sum(
                payment.pos_debt_allocation_ids.mapped("effective_amount")
            )
            payment.pos_debt_available_amount = sum(
                max(-line.amount_residual_currency, 0.0)
                for line in payment._get_pos_debt_counterpart_lines()
            )
            payment.has_draft_pos_debt_allocations = any(
                allocation.state == "draft"
                for allocation in payment.pos_debt_allocation_ids
            )

    def _get_pos_debt_counterpart_lines(self):
        self.ensure_one()
        if not self.move_id:
            return self.env["account.move.line"]
        _liquidity, counterpart, writeoff = self._seek_for_lines()
        return (counterpart | writeoff).filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
            and line.partner_id.commercial_partner_id
            == self.partner_id.commercial_partner_id
            and line.currency_id == self.currency_id
            and line.amount_residual_currency < 0.0
        )

    def action_post(self):
        result = super().action_post()
        for payment in self:
            drafts = payment.pos_debt_allocation_ids.filtered(
                lambda allocation: allocation.state == "draft"
            )
            if drafts:
                drafts.action_apply()
        return result

    def action_apply_pos_debt_allocations(self):
        for payment in self:
            payment.pos_debt_allocation_ids.filtered(
                lambda allocation: allocation.state == "draft"
            ).action_apply()
        return True

    def unlink(self):
        allocations = self.pos_debt_allocation_ids
        if any(allocation.state != "draft" for allocation in allocations):
            raise UserError(
                self.env._(
                    "A payment with debt settlement history cannot be deleted."
                )
            )
        allocations.unlink()
        return super().unlink()
