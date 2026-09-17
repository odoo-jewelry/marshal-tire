from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError

from .utils import CORRECTION_INTERNAL_TOKEN, is_internal_correction_call


class PosOrder(models.Model):
    _inherit = "pos.order"

    correction_root_id = fields.Many2one(
        "pos.order", readonly=True, copy=False, index=True, ondelete="restrict", check_company=True
    )
    correction_id = fields.Many2one(
        "pos.order.correction", readonly=True, copy=False, index=True, ondelete="restrict", check_company=True
    )
    correction_ids = fields.One2many(
        "pos.order.correction", "root_order_id", string="Corrections", readonly=True
    )
    correction_order_ids = fields.One2many(
        "pos.order", "correction_root_id", string="Correction Orders", readonly=True
    )
    is_correction_order = fields.Boolean(readonly=True, copy=False, index=True)
    correction_has_external_settlement = fields.Boolean(readonly=True, copy=False)
    correction_return_root_id = fields.Many2one(
        "pos.order", readonly=True, copy=False, index=True, ondelete="restrict", check_company=True
    )
    correction_pending = fields.Boolean(compute="_compute_correction_pending")
    effective_correction_order_ids = fields.Many2many(
        "pos.order", compute="_compute_effective_correction_order_ids"
    )

    @api.depends("correction_ids.state", "correction_ids.applied_order_id.session_id.state")
    def _compute_correction_pending(self):
        for order in self:
            root = order.correction_root_id or order
            order.correction_pending = any(
                correction.pending_processing
                for correction in root.correction_ids
                if correction.state == "applied"
            )

    @api.depends("correction_ids.state", "correction_ids.applied_order_id")
    def _compute_effective_correction_order_ids(self):
        for order in self:
            root = order.correction_root_id or order
            order.effective_correction_order_ids = root | root.correction_ids.filtered(
                lambda correction: correction.state == "applied"
            ).applied_order_id

    def _get_correction_root(self):
        if not self:
            return self
        self.ensure_one()
        return self.correction_root_id or self

    def _lock_correction_chain(self):
        if not self:
            return self
        roots = self.mapped(lambda order: order._get_correction_root()).sorted("id")
        if roots:
            roots.check_access("read")
            for root in roots:
                if root.try_lock_for_update() != root:
                    raise UserError(self.env._("The POS order is being processed. Try again."))
            roots.invalidate_recordset()
            corrections = roots.mapped("correction_ids").sorted("id")
            for correction in corrections:
                if correction.try_lock_for_update() != correction:
                    raise UserError(self.env._("The POS correction is being processed. Try again."))
            corrections.invalidate_recordset()
            chain = roots | corrections.applied_order_id
            for order in (chain - roots).sorted("id"):
                if order.try_lock_for_update() != order:
                    raise UserError(self.env._("The POS order is being processed. Try again."))
            chain.invalidate_recordset()
            chain.lines.invalidate_recordset()
            chain.payment_ids.invalidate_recordset()
            chain.payment_ids.debt_move_line_ids.invalidate_recordset()
        return roots

    def _get_correction_chain(self):
        if not self:
            return self
        self.ensure_one()
        root = self._get_correction_root()
        return root | root.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        ).sorted("revision").applied_order_id

    def _get_effective_correction_lines(self):
        if not self:
            return self.env["pos.order.line"]
        self.ensure_one()
        root = self._get_correction_root()
        latest = root.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        ).sorted("revision")[-1:]
        return latest.line_ids.result_order_line_id if latest else root.lines.filtered(
            lambda line: line.qty > 0.0 and not line.refunded_orderline_id
        )

    def _get_initial_correction_lines(self):
        self.ensure_one()
        return self.lines.filtered(
            lambda line: line.qty > 0.0 and not line.refunded_orderline_id
        )

    def _get_effective_correction_snapshot(self):
        self.ensure_one()
        root = self._get_correction_root()
        latest = root.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        ).sorted("revision")[-1:]
        if latest:
            return latest._snapshot()
        return {
            "lines": [
                {
                    "source_order_line_id": line.id,
                    "result_order_line_id": line.id,
                    "product_id": line.product_id.id,
                    "qty": line.qty,
                    "price_unit": line.price_unit,
                    "discount": line.discount,
                    "tax_ids": line.tax_ids.ids,
                    "lot_names": "\n".join(line.pack_lot_ids.mapped("lot_name")),
                }
                for line in root._get_initial_correction_lines()
            ],
            "payments": [
                {
                    "payment_method_id": method.id,
                    "amount": sum(
                        root.payment_ids.filtered(
                            lambda payment: payment.payment_method_id == method
                        ).mapped("amount")
                    ),
                }
                for method in root.payment_ids.payment_method_id
            ],
        }

    def _get_external_debt_partials(self):
        self.ensure_one()
        root = self._get_correction_root()
        chain = root._get_correction_chain()
        source_lines = chain.mapped("payment_ids.debt_move_line_ids")
        partials = source_lines.matched_debit_ids | source_lines.matched_credit_ids
        internal = root.correction_ids.mapped("internal_partial_reconcile_ids")
        return partials - internal

    def _check_correction_eligibility(self):
        for order in self:
            root = order._get_correction_root()
            if order != root:
                raise UserError(self.env._("Start corrections from the original POS order."))
            chain = root._get_correction_chain()
            if root.state not in ("paid", "done"):
                raise UserError(self.env._("Only completed POS orders can be corrected."))
            if root.is_refund or root.lines.refunded_orderline_id:
                raise UserError(self.env._("Return POS orders cannot be corrected."))
            if chain.mapped("account_move"):
                raise UserError(self.env._("An invoiced POS order cannot be corrected."))
            ordinary_refunds = chain.mapped("lines.refund_orderline_ids.order_id").filtered(
                lambda refund: not refund.is_correction_order
            )
            if ordinary_refunds:
                raise UserError(
                    self.env._("A POS order with an ordinary return cannot be corrected.")
                )
            if any(chain.mapped("correction_has_external_settlement")) or chain.debt_allocation_ids.filtered(
                lambda allocation: allocation.state != "draft"
                or allocation.partial_reconcile_ids
            ) or root._get_external_debt_partials():
                raise UserError(
                    self.env._("A POS order with subsequent debt settlement cannot be corrected.")
                )
            if len(chain.company_id) != 1 or len(chain.config_id) != 1 or len(chain.currency_id) != 1:
                raise UserError(self.env._("The correction chain has incompatible company or POS data."))
        return True

    def action_prepare_correction(self):
        self.ensure_one()
        if not self.env.user.has_group(
            "pos_order_correction.group_pos_order_correction"
        ):
            raise AccessError(self.env._("You are not allowed to correct POS orders."))
        root = self._get_correction_root()
        root._lock_correction_chain()
        root._check_correction_eligibility()
        existing = root.correction_ids.filtered(lambda correction: correction.state == "draft")[:1]
        if existing:
            return existing.action_open_form()
        session = self.env["pos.session"].search(
            [
                ("state", "=", "opened"),
                ("config_id", "=", root.config_id.id),
                ("company_id", "=", root.company_id.id),
            ],
            order="id desc",
            limit=1,
        )
        applied = root.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        ).sorted("revision")
        base_revision = applied[-1:].revision or 0
        revision = max(root.correction_ids.mapped("revision"), default=0) + 1
        if applied:
            source_lines = applied[-1:].line_ids
            line_commands = [
                Command.create(
                    {
                        "source_order_line_id": (
                            line.result_order_line_id or line.source_order_line_id
                        ).id,
                        "product_id": line.product_id.id,
                        "qty": line.qty,
                        "price_unit": line.price_unit,
                        "discount": line.discount,
                        "tax_ids": [Command.set(line.tax_ids.ids)],
                        "lot_names": line.lot_names,
                    }
                )
                for line in source_lines
            ]
            payment_commands = [
                Command.create(
                    {
                        "payment_method_id": payment.payment_method_id.id,
                        "amount": payment.amount,
                    }
                )
                for payment in applied[-1:].payment_ids
            ]
        else:
            line_commands = [
                Command.create(
                    {
                        "source_order_line_id": line.id,
                        "product_id": line.product_id.id,
                        "qty": line.qty,
                        "price_unit": line.price_unit,
                        "discount": line.discount,
                        "tax_ids": [Command.set(line.tax_ids.ids)],
                        "lot_names": "\n".join(line.pack_lot_ids.mapped("lot_name")),
                    }
                )
                for line in root._get_initial_correction_lines()
            ]
            amounts = {}
            for payment in root.payment_ids:
                amounts[payment.payment_method_id] = amounts.get(
                    payment.payment_method_id, 0.0
                ) + payment.amount
            payment_commands = [
                Command.create(
                    {"payment_method_id": method.id, "amount": amount}
                )
                for method, amount in amounts.items()
            ]
        correction = self.env["pos.order.correction"].create(
            {
                "root_order_id": root.id,
                "revision": revision,
                "base_revision": base_revision,
                "target_session_id": session.id,
                "reason": False,
                "line_ids": line_commands,
                "payment_ids": payment_commands,
            }
        )
        return correction.action_open_form()

    def action_pos_order_invoice(self):
        self.ensure_one()
        if self.is_correction_order:
            return self._get_correction_root().action_pos_order_invoice()
        return super().action_pos_order_invoice()

    def _generate_pos_order_invoice(self):
        roots = self.mapped(lambda order: order._get_correction_root())
        corrected_roots = roots.filtered(
            lambda order: order.correction_ids.filtered(lambda correction: correction.state == "applied")
        )
        if not corrected_roots:
            return super()._generate_pos_order_invoice()
        orders = self
        for root in corrected_roots:
            orders |= root._get_correction_chain()
        if any(len(orders.mapped(field)) != 1 for field in ("company_id", "config_id", "currency_id", "partner_id")) or len(orders.fiscal_position_id) > 1:
            raise UserError(self.env._("Orders invoiced together must use one company, POS, currency, customer and fiscal position."))
        for session in orders.session_id.sorted("id"):
            if session.try_lock_for_update() != session:
                raise UserError(self.env._("The POS session is being processed. Try again."))
        roots._lock_correction_chain()
        for root in corrected_roots:
            root._check_no_pending_correction_processing(
                self.env._("Close all correction sessions before creating an invoice.")
            )
        invoices = orders.account_move
        if invoices:
            if len(invoices) == 1 and all(order.account_move == invoices for order in orders):
                return invoices
            raise UserError(self.env._("Some orders already have an invoice. Open the existing invoice."))
        invoice_orders = orders.with_context(
            pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN,
            pos_order_correction_invoice_roots=corrected_roots.ids,
            pos_order_correction_invoice_token=CORRECTION_INTERNAL_TOKEN,
        )
        invoice = super(PosOrder, invoice_orders)._generate_pos_order_invoice()
        invoice_orders._reconcile_correction_invoice_debt(invoice)
        return invoice

    def _prepare_invoice_vals(self):
        if self.env.context.get("pos_order_correction_invoice_token") is not CORRECTION_INTERNAL_TOKEN:
            return super()._prepare_invoice_vals()
        roots = self.mapped(lambda order: order._get_correction_root())
        # Corrections retain their actual author. Use the source author for the
        # invoice header, so another authorized corrector does not break it.
        values = super(PosOrder, roots[:1])._prepare_invoice_vals()
        amount_total = sum(self.mapped("amount_total"))
        move_type = "out_refund" if amount_total < 0.0 else "out_invoice"
        values.update({
            "pos_order_ids": self.ids,
            "invoice_origin": ", ".join(reference or "" for reference in self.mapped("pos_reference")),
            "ref": roots.name if len(roots) == 1 else False,
            "move_type": move_type,
            "invoice_line_ids": self._prepare_invoice_lines(move_type),
        })
        debt_amount = sum(self.payment_ids.filtered(
            lambda payment: payment.payment_method_id.type == "pay_later"
        ).mapped("amount"))
        values["invoice_payment_term_id"] = (
            self.partner_id.property_payment_term_id.id if debt_amount > 0.0 else False
        )
        cash_amount = sum(self.payment_ids.filtered(
            lambda payment: payment.payment_method_id.is_cash_count
        ).mapped("amount"))
        if self.config_id.only_round_cash_method and self.currency_id.is_zero(cash_amount):
            values["invoice_cash_rounding_id"] = False
        return values

    def _prepare_invoice_lines(self, move_type):
        if self.env.context.get("pos_order_correction_invoice_token") is CORRECTION_INTERNAL_TOKEN:
            roots = self.mapped(lambda order: order._get_correction_root())
            corrected_roots = roots.filtered(
                lambda root: root.correction_ids.filtered(lambda correction: correction.state == "applied")
            )
            invoice_lines = super(PosOrder, roots - corrected_roots)._prepare_invoice_lines(move_type)
            effective_lines = corrected_roots.mapped(lambda root: root._get_effective_correction_lines())
            for order in effective_lines.order_id:
                lines = effective_lines.filtered(lambda line: line.order_id == order)
                line_values_list = lines.with_context(invoicing=True)._prepare_tax_base_line_values()
                for values in line_values_list:
                    invoice_lines.append(
                        Command.create(order._get_invoice_lines_values(values, values["record"], move_type))
                    )
            return invoice_lines
        return super()._prepare_invoice_lines(move_type)

    def action_pos_order_paid(self):
        if self.is_correction_order and is_internal_correction_call(self.env):
            # The complete desired sale is validated before creating this order.
            # Rounding its difference again would round the same sale twice.
            self.ensure_one()
            self.write({"state": "paid"})
            return True
        return super().action_pos_order_paid()

    def _compute_has_refundable_lines(self):
        super()._compute_has_refundable_lines()
        for order in self.filtered(
            lambda item: not item.is_correction_order
            and item.correction_ids.filtered(lambda correction: correction.state == "applied")
        ):
            order.has_refundable_lines = any(
                line.refunded_qty < line.qty
                for line in order._get_effective_correction_lines()
            )

    def _refund(self):
        if self.filtered("is_correction_order"):
            return self.mapped(lambda order: order._get_correction_root())._refund()
        refund_orders = self.env["pos.order"]
        ordinary = self.filtered(
            lambda order: not order.correction_ids.filtered(lambda correction: correction.state == "applied")
        )
        if ordinary:
            refund_orders |= super(PosOrder, ordinary)._refund()
        for root in self - ordinary:
            current_session = root.config_id.current_session_id
            if not current_session or current_session.state != "opened":
                raise UserError(
                    self.env._(
                        "Open a session for point of sale %s before returning products.",
                        root.config_id.display_name,
                    )
                )
            if current_session.try_lock_for_update() != current_session:
                raise UserError(self.env._("The POS session is being processed. Try again."))
            root._lock_correction_chain()
            root._check_no_pending_correction_processing(
                self.env._("Close all correction sessions before returning products.")
            )
            refund_order = root.copy(root._prepare_refund_values(current_session))
            refund_order.with_context(
                pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN
            ).write(
                {"correction_return_root_id": root.id}
            )
            for line in root._get_effective_correction_lines().filtered(
                lambda item: item.refunded_qty < item.qty
            ):
                lots = self.env["pos.pack.operation.lot"]
                for lot in line.pack_lot_ids:
                    lots += lot.copy()
                refund_line = line.copy(line._prepare_refund_data(refund_order, lots))
                refund_line._onchange_amount_line_all()
            refund_order._compute_prices()
            refund_orders |= refund_order
            refund_order.config_id.notify_synchronisation(current_session.id, 0)
        return refund_orders

    def _check_no_pending_correction_processing(self, message):
        if any(
            correction.pending_processing
            for correction in self.mapped(lambda order: order._get_correction_root()).correction_ids
            if correction.state == "applied"
        ):
            raise UserError(message)

    @api.model
    def _process_order(self, order, existing_order):
        # POS serializes readonly fields too. Correction ownership is assigned
        # by the server and must survive draft synchronization unchanged.
        ownership_fields = {
            "correction_root_id", "correction_id", "is_correction_order",
            "correction_return_root_id", "correction_ids", "correction_order_ids",
            "correction_has_external_settlement",
        }
        order = {key: value for key, value in order.items() if key not in ownership_fields}
        return super()._process_order(order, existing_order)

    @api.model
    def _get_refunded_orders(self, order):
        sources = super()._get_refunded_orders(order)
        return sources.mapped(lambda source: source._get_correction_root())

    def _set_correction_return_root(self):
        for order in self.filtered(lambda item: not item.is_correction_order):
            sources = order.lines.refunded_orderline_id.order_id
            roots = sources.mapped(lambda source: source._get_correction_root())
            corrected = roots.filtered(
                lambda root: root.correction_ids.filtered(lambda correction: correction.state == "applied")
            )
            if not corrected:
                continue
            if len(roots) != 1 or roots.company_id != order.company_id or roots.config_id != order.config_id or roots.partner_id != order.partner_id:
                raise UserError(self.env._("A corrected sale must be returned for its original customer, company and POS."))
            if order.correction_return_root_id != roots:
                order.with_context(
                    pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN
                ).write({"correction_return_root_id": roots.id})

    @api.model_create_multi
    def create(self, vals_list):
        ownership_fields = {
            "correction_root_id", "correction_id", "is_correction_order",
            "correction_return_root_id", "correction_ids", "correction_order_ids",
            "correction_has_external_settlement",
        }
        if not is_internal_correction_call(self.env) and (
            any(any(values.get(field) for field in ownership_fields) for values in vals_list)
            or any(self.env.context.get("default_" + field) for field in ownership_fields)
        ):
            raise UserError(self.env._("Correction ownership is assigned only by the correction workflow."))
        orders = super().create(vals_list)
        if not is_internal_correction_call(self.env):
            orders._set_correction_return_root()
        return orders

    def copy_data(self, default=None):
        if self.filtered("is_correction_order") and not is_internal_correction_call(
            self.env
        ):
            raise UserError(self.env._("Applied correction orders cannot be copied."))
        values_list = super().copy_data(default=default)
        for values in values_list:
            values.update(
                {
                    "correction_root_id": False,
                    "correction_id": False,
                    "is_correction_order": False,
                    "correction_return_root_id": False,
                }
            )
        return values_list

    def write(self, vals):
        ownership_fields = {
            "correction_root_id", "correction_id", "is_correction_order",
            "correction_return_root_id", "correction_ids", "correction_order_ids",
            "correction_has_external_settlement",
        }
        if not is_internal_correction_call(self.env) and ownership_fields.intersection(vals):
            raise UserError(self.env._("Correction ownership is assigned only by the correction workflow."))
        protected = {
            "company_id",
            "session_id",
            "date_order",
            "partner_id",
            "pricelist_id",
            "fiscal_position_id",
            "user_id",
            "stock_reference_ids",
            "account_move",
            "state",
            "lines",
            "payment_ids",
            "amount_paid",
            "amount_tax",
            "amount_total",
            "amount_return",
            "correction_root_id",
            "correction_id",
            "is_correction_order",
            "correction_return_root_id",
        }
        if self.filtered(lambda order: order.is_correction_order or order.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        )) and protected.intersection(
            vals
        ) and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Applied correction orders cannot be edited."))
        if self.filtered("is_correction_order") and {"state", "account_move"}.intersection(vals) and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Correction posting is controlled by the standard session and invoice workflow."))
        result = super().write(vals)
        if "lines" in vals and not is_internal_correction_call(self.env):
            self._set_correction_return_root()
        return result

    def unlink(self):
        if self.filtered("is_correction_order"):
            raise UserError(self.env._("Applied correction orders cannot be deleted."))
        return super().unlink()

    def action_pos_order_cancel(self):
        if self.filtered("is_correction_order"):
            raise UserError(self.env._("Applied correction orders cannot be cancelled."))
        return super().action_pos_order_cancel()


class PosOrderCorrectionAction(models.Model):
    _inherit = "pos.order.correction"

    def action_open_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "pos.order.correction",
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }
