from math import isfinite
from uuid import uuid4

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare

from .utils import CORRECTION_INTERNAL_TOKEN, is_internal_correction_call


class PosOrderCorrection(models.Model):
    _name = "pos.order.correction"
    _description = "POS Order Correction"
    _inherit = ["mail.thread"]
    _order = "root_order_id, revision desc, id desc"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", store=True)
    root_order_id = fields.Many2one(
        "pos.order",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
        tracking=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        related="root_order_id.company_id", store=True, index=True
    )
    currency_id = fields.Many2one(related="root_order_id.currency_id")
    revision = fields.Integer(required=True, readonly=True, copy=False)
    base_revision = fields.Integer(required=True, readonly=True)
    request_key = fields.Char(
        required=True, readonly=True, copy=False, default=lambda self: str(uuid4())
    )
    reason = fields.Text(tracking=True)
    state = fields.Selection(
        [("draft", "Draft"), ("applied", "Applied"), ("cancelled", "Cancelled")],
        required=True,
        readonly=True,
        copy=False,
        default="draft",
        index=True,
        tracking=True,
    )
    target_session_id = fields.Many2one(
        "pos.session",
        domain="[('config_id', '=', config_id), ('state', '=', 'opened')]",
        tracking=True,
        check_company=True,
    )
    config_id = fields.Many2one(related="root_order_id.config_id")
    partner_id = fields.Many2one(related="root_order_id.partner_id")
    line_ids = fields.One2many(
        "pos.order.correction.line", "correction_id", string="Corrected Lines", copy=True
    )
    payment_ids = fields.One2many(
        "pos.order.correction.payment",
        "correction_id",
        string="Corrected Payments",
        copy=True,
    )
    applied_order_id = fields.Many2one(
        "pos.order", readonly=True, copy=False, ondelete="restrict", tracking=True,
        check_company=True,
    )
    applied_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    applied_at = fields.Datetime(readonly=True, copy=False)
    before_snapshot = fields.Json(readonly=True, copy=False)
    after_snapshot = fields.Json(readonly=True, copy=False)
    source_snapshot = fields.Json(readonly=True, copy=False)
    pending_processing = fields.Boolean(compute="_compute_pending_processing")
    internal_partial_reconcile_ids = fields.Many2many(
        "account.partial.reconcile",
        "pos_correction_partial_reconcile_rel",
        "correction_id",
        "partial_id",
        readonly=True,
        copy=False,
    )

    _unique_request_key = models.Constraint(
        "unique (request_key)", "The correction request key must be unique."
    )
    _unique_root_revision = models.Constraint(
        "unique (root_order_id, revision)",
        "The correction revision must be unique for the POS order.",
    )

    @api.depends("root_order_id.name", "revision")
    def _compute_name(self):
        for correction in self:
            correction.name = "%s / %s" % (
                correction.root_order_id.name or "POS",
                correction.revision,
            )

    @api.depends("state", "applied_order_id.session_id.state")
    def _compute_pending_processing(self):
        for correction in self:
            correction.pending_processing = (
                correction.state == "applied"
                and correction.applied_order_id.session_id.state != "closed"
            )

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("default_state", "draft") != "draft":
            raise UserError(self.env._("A correction must be created as a draft."))
        if any(vals.get("state", "draft") != "draft" for vals in vals_list):
            raise UserError(self.env._("A correction must be created as a draft."))
        protected = {
            "applied_order_id", "applied_by_id", "applied_at", "before_snapshot",
            "after_snapshot", "source_snapshot", "internal_partial_reconcile_ids",
        }
        if any(protected.intersection(vals) for vals in vals_list) or any(
            self.env.context.get("default_" + field) for field in protected
        ):
            raise UserError(self.env._("Correction results can only be assigned by application."))
        roots = self.env["pos.order"].browse(
            [vals["root_order_id"] for vals in vals_list if vals.get("root_order_id")]
        )
        roots.check_access("read")
        roots._lock_correction_chain()
        roots._check_correction_eligibility()
        corrections = super().create(vals_list)
        for correction in corrections:
            if correction.revision <= correction.base_revision or correction.base_revision < 0:
                raise ValidationError(self.env._("Correction revision numbers are invalid."))
            correction.with_context(
                pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN
            ).write({"source_snapshot": correction._get_source_snapshot()})
        return corrections

    def _lock_for_edit(self):
        self.check_access("write")
        for correction in self.sorted("id"):
            if correction.try_lock_for_update() != correction:
                raise UserError(self.env._("The POS correction is being processed. Try again."))
        self.invalidate_recordset()

    def _get_source_snapshot(self):
        self.ensure_one()
        chain = self.root_order_id._get_correction_chain()
        return {
            "orders": [
                {
                    "id": order.id,
                    "company_id": order.company_id.id,
                    "session_id": order.session_id.id,
                    "currency_id": order.currency_id.id,
                    "partner_id": order.partner_id.id,
                    "pricelist_id": order.pricelist_id.id,
                    "fiscal_position_id": order.fiscal_position_id.id,
                    "date_order": fields.Datetime.to_string(order.date_order),
                }
                for order in chain.sorted("id")
            ],
            "lines": [
                {
                    "id": line.id, "order_id": line.order_id.id,
                    "product_id": line.product_id.id, "qty": line.qty,
                    "price_unit": line.price_unit, "discount": line.discount,
                    "tax_ids": sorted(line.tax_ids.ids),
                    "lots": sorted(line.pack_lot_ids.mapped("lot_name")),
                    "attribute_value_ids": sorted(line.attribute_value_ids.ids),
                    "custom_attribute_values": [
                        [value.custom_product_template_attribute_value_id.id, value.custom_value]
                        for value in line.custom_attribute_value_ids.sorted("id")
                    ],
                }
                for line in chain.lines.sorted("id")
            ],
            "payments": [
                {
                    "id": payment.id, "order_id": payment.pos_order_id.id,
                    "method_id": payment.payment_method_id.id, "amount": payment.amount,
                    "is_change": payment.is_change,
                    "transaction_id": payment.transaction_id,
                    "payment_status": payment.payment_status,
                }
                for payment in chain.payment_ids.sorted("id")
            ],
        }

    def write(self, vals):
        protected = {
            "root_order_id",
            "revision",
            "base_revision",
            "request_key",
            "state",
            "applied_order_id",
            "applied_by_id",
            "applied_at",
            "before_snapshot",
            "after_snapshot",
            "source_snapshot",
            "internal_partial_reconcile_ids",
        }
        if protected.intersection(vals) and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Correction system fields cannot be edited."))
        if not is_internal_correction_call(self.env):
            self._lock_for_edit()
        if self.filtered(lambda correction: correction.state != "draft") and set(
            vals
        ).intersection({"reason", "target_session_id", "line_ids", "payment_ids"}):
            raise UserError(self.env._("Only draft corrections can be edited."))
        return super().write(vals)

    def unlink(self):
        self._lock_for_edit()
        if self.filtered(lambda correction: correction.state != "draft"):
            raise UserError(self.env._("Only draft corrections can be deleted."))
        return super().unlink()

    def copy(self, default=None):
        if self.filtered(lambda correction: correction.state != "draft"):
            raise UserError(self.env._("Applied corrections cannot be copied."))
        return super().copy(default)

    def action_cancel(self):
        self._lock_for_edit()
        drafts = self.filtered(lambda correction: correction.state == "draft")
        if len(drafts) != len(self):
            raise UserError(self.env._("Only draft corrections can be cancelled."))
        drafts.with_context(
            pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN
        ).write(
            {"state": "cancelled"}
        )
        return True

    def _line_snapshot(self, lines=None):
        self.ensure_one()
        lines = self.line_ids if lines is None else lines
        return [
            {
                "source_order_line_id": line.source_order_line_id.id,
                "result_order_line_id": line.result_order_line_id.id,
                "product_id": line.product_id.id,
                "qty": line.qty,
                "price_unit": line.price_unit,
                "discount": line.discount,
                "tax_ids": line.tax_ids.ids,
                "lot_names": line.lot_names or "",
                "attribute_value_ids": line.attribute_value_ids.ids,
                "custom_attribute_values": line.custom_attribute_values or [],
            }
            for line in lines.sorted("id")
        ]

    def _payment_snapshot(self, payments=None):
        self.ensure_one()
        payments = self.payment_ids if payments is None else payments
        return [
            {
                "payment_method_id": payment.payment_method_id.id,
                "amount": payment.amount,
            }
            for payment in payments.sorted("payment_method_id")
        ]

    def _snapshot(self):
        self.ensure_one()
        return {
            "lines": self._line_snapshot(),
            "payments": self._payment_snapshot(),
        }

    def _previous_projection(self):
        self.ensure_one()
        previous = self.root_order_id.correction_ids.filtered(
            lambda correction: correction.state == "applied"
            and correction.revision < self.revision
        ).sorted("revision")[-1:]
        if previous:
            return previous.line_ids, previous.payment_ids
        return self.root_order_id._get_initial_correction_lines(), False

    @api.model
    def _projection_source_line(self, line):
        if line._name == "pos.order.line":
            return line
        return line.result_order_line_id or line.source_order_line_id

    @api.model
    def _projection_lot_names(self, line):
        if line._name == "pos.order.line":
            return "\n".join(line.pack_lot_ids.mapped("lot_name"))
        return line.lot_names or ""

    def _values_changed(self, previous, desired):
        currency = self.currency_id
        return (
            previous.product_id != desired.product_id
            or float_compare(previous.qty, desired.qty, precision_rounding=desired.product_uom_id.rounding)
            != 0
            or currency.compare_amounts(previous.price_unit, desired.price_unit) != 0
            or float_compare(previous.discount, desired.discount, precision_digits=4) != 0
            or previous.tax_ids != desired.tax_ids
            or self._projection_lot_names(previous) != (desired.lot_names or "")
        )

    def _prepare_operational_line_values(
        self,
        line,
        qty,
        stock_qty,
        refunded_line=False,
        projection_line=False,
        stock_origin_line=False,
    ):
        self.ensure_one()
        lot_names = [
            name.strip()
            for name in self._projection_lot_names(line).splitlines()
            if name.strip()
        ]
        provisional_subtotal = qty * line.price_unit * (1.0 - line.discount / 100.0)
        custom_values = line.custom_attribute_values if line._name == "pos.order.correction.line" else [
            {
                "custom_product_template_attribute_value_id": value.custom_product_template_attribute_value_id.id,
                "custom_value": value.custom_value,
            }
            for value in line.custom_attribute_value_ids
        ]
        return {
            "product_id": line.product_id.id,
            "qty": qty,
            "price_unit": line.price_unit,
            "discount": line.discount,
            "price_subtotal": provisional_subtotal,
            "price_subtotal_incl": provisional_subtotal,
            "tax_ids": [Command.set(line.tax_ids.ids)],
            "full_product_name": line.product_id.display_name,
            "refunded_orderline_id": refunded_line.id if refunded_line else False,
            "correction_stock_qty": stock_qty,
            "correction_origin_line_id": (
                stock_origin_line or refunded_line
            ).id if (stock_origin_line or refunded_line) else False,
            "correction_projection_line_id": projection_line.id if projection_line else False,
            "pack_lot_ids": [Command.create({"lot_name": name}) for name in lot_names],
            "attribute_value_ids": [Command.set(line.attribute_value_ids.ids)],
            "custom_attribute_value_ids": [Command.create(value) for value in custom_values or []],
        }

    def _prepare_line_difference(self):
        self.ensure_one()
        previous_lines, _previous_payments = self._previous_projection()
        previous_by_source = {
            self._projection_source_line(line).id: line
            for line in previous_lines
        }
        desired_by_source = {
            line.source_order_line_id.id: line
            for line in self.line_ids
            if line.source_order_line_id
        }
        commands = []
        desired_results = {}
        for source_id, previous in previous_by_source.items():
            desired = desired_by_source.get(source_id)
            source_line = self._projection_source_line(previous)
            if desired and not self._values_changed(previous, desired):
                desired_results[desired.id] = source_line
                continue
            desired_qty = desired.qty if desired and desired.product_id == previous.product_id else 0.0
            negative_stock_qty = min(desired_qty - previous.qty, 0.0)
            if desired and desired.product_id != previous.product_id:
                negative_stock_qty = -previous.qty
            commands.append(
                Command.create(
                    self._prepare_operational_line_values(
                        previous, -previous.qty, negative_stock_qty, source_line
                    )
                )
            )
            if desired:
                positive_stock_qty = max(desired.qty - previous.qty, 0.0)
                if desired.product_id != previous.product_id:
                    positive_stock_qty = desired.qty
                commands.append(
                    Command.create(
                        self._prepare_operational_line_values(
                            desired,
                            desired.qty,
                            positive_stock_qty,
                            projection_line=desired,
                            stock_origin_line=(
                                source_line
                                if desired.product_id == previous.product_id
                                else False
                            ),
                        )
                    )
                )
                desired_results[desired.id] = None
        for desired in self.line_ids.filtered(lambda line: not line.source_order_line_id):
            commands.append(
                Command.create(
                    self._prepare_operational_line_values(
                        desired, desired.qty, desired.qty, projection_line=desired
                    )
                )
            )
            desired_results[desired.id] = None
        return commands, desired_results

    def _previous_payment_amounts(self):
        self.ensure_one()
        _previous_lines, previous_payments = self._previous_projection()
        if previous_payments is not False:
            return {
                payment.payment_method_id: payment.amount
                for payment in previous_payments
            }
        amounts = {}
        for payment in self.root_order_id.payment_ids:
            amounts[payment.payment_method_id] = (
                amounts.get(payment.payment_method_id, 0.0) + payment.amount
            )
        return amounts

    def _prepare_payment_difference(self):
        self.ensure_one()
        previous = self._previous_payment_amounts()
        desired = {
            payment.payment_method_id: payment.amount for payment in self.payment_ids
        }
        values = []
        for method in previous.keys() | desired.keys():
            difference = desired.get(method, 0.0) - previous.get(method, 0.0)
            if self.currency_id.is_zero(difference):
                continue
            if method.use_payment_terminal:
                raise UserError(
                    self.env._(
                        "Payment method %(method)s uses a terminal and cannot be corrected automatically.",
                        method=method.display_name,
                    )
                )
            values.append(
                Command.create(
                    {
                        "payment_method_id": method.id,
                        "amount": difference,
                        "payment_date": fields.Datetime.now(),
                        "name": self.env._("Correction %(revision)s", revision=self.revision),
                    }
                )
            )
        return values

    def _validate_draft(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(self.env._("Only a draft correction can be applied."))
        if not (self.reason or "").strip():
            raise ValidationError(self.env._("A correction reason is required."))
        if not self.target_session_id or self.target_session_id.state != "opened":
            raise UserError(self.env._("Open a session for the original point of sale before applying the correction."))
        if self.target_session_id.config_id != self.root_order_id.config_id:
            raise UserError(self.env._("The target session must use the original point of sale."))
        if self.target_session_id.company_id != self.company_id:
            raise UserError(self.env._("The target session must use the original company."))
        if self.target_session_id.currency_id != self.currency_id:
            raise UserError(self.env._("The target session must use the original currency."))
        self._check_company()
        self.line_ids._check_company()
        self.payment_ids._check_company()
        if any(
            not isfinite(value)
            for line in self.line_ids
            for value in (line.qty, line.price_unit, line.discount)
        ) or any(not isfinite(payment.amount) for payment in self.payment_ids):
            raise ValidationError(self.env._("Correction quantities and amounts must be finite numbers."))
        if any(line.qty <= 0.0 for line in self.line_ids):
            raise ValidationError(self.env._("Corrected line quantities must be positive."))
        if any(line.price_unit < 0.0 for line in self.line_ids):
            raise ValidationError(self.env._("Corrected prices cannot be negative."))
        if any(payment.amount < 0.0 for payment in self.payment_ids):
            raise ValidationError(self.env._("The effective payment distribution cannot contain negative amounts."))
        if any(line.discount < 0.0 or line.discount > 100.0 for line in self.line_ids):
            raise ValidationError(self.env._("Corrected discounts must be between 0 and 100."))
        unavailable_products = self.line_ids.product_id.filtered(
            lambda product: not product.active
            or not product.sale_ok
            or not product.available_in_pos
            or (product.company_id and product.company_id != self.company_id)
        )
        if unavailable_products:
            raise ValidationError(
                self.env._("All corrected products must be available for this point of sale.")
            )
        for line in self.line_ids.filtered(lambda item: item.product_id.tracking != "none"):
            lot_names = [name.strip() for name in (line.lot_names or "").splitlines() if name.strip()]
            if not lot_names or (
                line.product_id.tracking == "serial"
                and (not line.qty.is_integer() or len(lot_names) != line.qty
                     or len(set(lot_names)) != len(lot_names))
            ):
                raise ValidationError(
                    self.env._(
                        "Valid lot or serial numbers are required for %(product)s.",
                        product=line.product_id.display_name,
                    )
                )
        if len(self.payment_ids.payment_method_id) != len(self.payment_ids):
            raise ValidationError(self.env._("Each payment method can occur only once."))
        invalid_methods = self.payment_ids.payment_method_id - self.target_session_id.payment_method_ids
        if invalid_methods:
            raise ValidationError(
                self.env._("All payment methods must be available in the target session.")
            )
        previous_lines, _previous_payments = self._previous_projection()
        valid_sources = {
            self._projection_source_line(line).id for line in previous_lines
        }
        supplied_sources = [
            line.source_order_line_id.id
            for line in self.line_ids if line.source_order_line_id
        ]
        if len(supplied_sources) != len(set(supplied_sources)) or not set(
            supplied_sources
        ).issubset(valid_sources):
            raise ValidationError(
                self.env._("Corrected lines must use unique sources from the current revision.")
            )
        self._check_effective_payment_total()

    def _check_effective_payment_total(self):
        self.ensure_one()
        # Standard tax and cash rounding methods also accept virtual records.
        # Validate the complete sale: rounding the difference is not equivalent.
        projected = self.env["pos.order"].with_company(self.company_id).new({
            "session_id": self.target_session_id.id,
            "company_id": self.company_id.id,
            "partner_id": self.root_order_id.partner_id.id,
            "pricelist_id": self.root_order_id.pricelist_id.id,
            "fiscal_position_id": self.root_order_id.fiscal_position_id.id,
            "lines": [Command.create({
                "product_id": line.product_id.id, "qty": line.qty,
                "price_unit": line.price_unit, "discount": line.discount,
                "tax_ids": [Command.set(line.tax_ids.ids)],
            }) for line in self.line_ids],
            "payment_ids": [Command.create({
                "payment_method_id": payment.payment_method_id.id,
                "amount": payment.amount,
            }) for payment in self.payment_ids],
        })
        # Virtual x2many values use NewId wrappers. Fiscal-position maps are
        # keyed by persistent tax ids, so resolve those before the standard
        # POS amount computation consumes the virtual lines' effective taxes.
        for line in projected.lines:
            line.tax_ids_after_fiscal_position = projected.fiscal_position_id.map_tax(
                line.tax_ids._origin
            )
        projected._compute_prices()
        expected = projected._get_rounded_amount(projected.amount_total)
        if self.currency_id.compare_amounts(expected, projected.amount_paid):
            raise ValidationError(self.env._(
                "The effective payment distribution must equal %(expected)s; allocate the remaining %(remaining)s.",
                expected=self.currency_id.format(expected),
                remaining=self.currency_id.format(expected - projected.amount_paid),
            ))

    def action_apply(self):
        if not self.env.user.has_group(
            "pos_order_correction.group_pos_order_correction"
        ):
            raise AccessError(self.env._("You are not allowed to correct POS orders."))
        self.check_access("write")
        # Keep batch atomicity even when an ORM caller catches the exception.
        with self.env.cr.savepoint():
            return self._apply_corrections()

    def _apply_corrections(self):
        ordered = self.sorted(lambda item: (item.root_order_id.id, item.revision))
        drafts = ordered.filtered(lambda correction: correction.state != "applied")
        if not drafts:
            return ordered[-1].action_open_current_receipt() if ordered else True
        if len(drafts.root_order_id) != len(drafts):
            raise UserError(
                self.env._("Apply only one pending revision per source order at a time.")
            )
        for correction in drafts:
            correction._validate_draft()
        sessions = drafts.target_session_id.sorted("id")
        for session in sessions:
            session.check_access("read")
            if session.try_lock_for_update() != session:
                raise UserError(
                    self.env._("A target POS session is being processed. Try again.")
                )
        sessions.invalidate_recordset()
        drafts.root_order_id._lock_correction_chain()
        drafts.invalidate_recordset()
        for model_name, records in (
            ("pos.order.correction.line", drafts.line_ids),
            ("pos.order.correction.payment", drafts.payment_ids),
        ):
            for record in records.sorted("id"):
                if record.try_lock_for_update() != record:
                    raise UserError(self.env._("Correction data is being edited. Try again."))
            self.env[model_name].invalidate_model()
        for correction in drafts:
            correction._validate_draft()
            correction.root_order_id._check_correction_eligibility()
            current_revision = max(
                correction.root_order_id.correction_ids.filtered(
                    lambda item: item.state == "applied"
                ).mapped("revision"),
                default=0,
            )
            if correction.base_revision != current_revision:
                raise UserError(
                    self.env._("This correction is stale. Create a new correction from the current result.")
                )
            if correction.source_snapshot != correction._get_source_snapshot():
                raise UserError(self.env._(
                    "The source sale changed after preparation. Create a new correction from the current result."
                ))

        result = True
        for correction in ordered:
            if correction.state == "applied":
                result = correction.action_open_current_receipt()
                continue
            line_commands, desired_results = correction._prepare_line_difference()
            payment_commands = correction._prepare_payment_difference()
            if not line_commands and not payment_commands:
                raise UserError(self.env._("The correction does not contain any changes."))
            if any(command[2].get("correction_stock_qty") for command in line_commands):
                for model_name in ("stock.picking", "stock.move", "stock.move.line"):
                    self.env[model_name].check_access("create")
                    self.env[model_name].check_access("write")
            before = correction.root_order_id._get_effective_correction_snapshot()
            order = self.env["pos.order"].with_company(correction.company_id).with_context(
                pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN
            ).create(
                {
                    "session_id": correction.target_session_id.id,
                    "company_id": correction.company_id.id,
                    "partner_id": correction.root_order_id.partner_id.id,
                    "pricelist_id": correction.root_order_id.pricelist_id.id,
                    "fiscal_position_id": correction.root_order_id.fiscal_position_id.id,
                    "user_id": self.env.user.id,
                    "amount_paid": 0.0,
                    "amount_tax": 0.0,
                    "amount_total": 0.0,
                    "amount_return": 0.0,
                    "lines": line_commands,
                    "payment_ids": payment_commands,
                    "correction_root_id": correction.root_order_id.id,
                    "correction_id": correction.id,
                    "is_correction_order": True,
                }
            )
            order.lines._onchange_amount_line_all()
            order._compute_prices()
            order.action_pos_order_paid()
            order._create_order_picking()
            order._compute_total_cost_in_real_time()
            for desired_id, existing_line in desired_results.items():
                desired_line = correction.line_ids.browse(desired_id)
                result_line = existing_line
                if not result_line:
                    result_line = order.lines.filtered(
                        lambda line: line.correction_projection_line_id == desired_line
                    )
                if not result_line:
                    raise UserError(self.env._("The corrected order line could not be identified."))
                desired_line.with_context(
                    pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN
                ).write(
                    {"result_order_line_id": result_line.id}
                )
            after = correction._snapshot()
            correction.with_context(
                pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN
            ).write(
                {
                    "state": "applied",
                    "applied_order_id": order.id,
                    "applied_by_id": self.env.user.id,
                    "applied_at": fields.Datetime.now(),
                    "before_snapshot": before,
                    "after_snapshot": after,
                }
            )
            correction.message_post(
                body=self.env._("Correction applied as POS order %s.", order.name)
            )
            result = correction.action_open_current_receipt()
        return result

    def action_open_current_receipt(self):
        self.ensure_one()
        self.check_access("read")
        return self.root_order_id.action_open_current_receipt()

    def action_open_applied_order(self):
        self.ensure_one()
        self.check_access("read")
        self.applied_order_id.check_access("read")
        return {
            "type": "ir.actions.act_window",
            "res_model": "pos.order",
            "view_mode": "form",
            "res_id": self.applied_order_id.id,
        }


class PosOrderCorrectionLine(models.Model):
    _name = "pos.order.correction.line"
    _description = "POS Order Correction Line"
    _order = "id"
    _check_company_auto = True

    correction_id = fields.Many2one(
        "pos.order.correction", required=True, ondelete="cascade", index=True,
        check_company=True,
    )
    company_id = fields.Many2one(related="correction_id.company_id", store=True)
    currency_id = fields.Many2one(related="correction_id.currency_id")
    source_order_line_id = fields.Many2one(
        "pos.order.line", readonly=True, copy=True, ondelete="restrict", check_company=True
    )
    result_order_line_id = fields.Many2one(
        "pos.order.line", readonly=True, copy=False, ondelete="restrict", check_company=True
    )
    product_id = fields.Many2one("product.product", required=True, check_company=True)
    product_uom_id = fields.Many2one(related="product_id.uom_id")
    qty = fields.Float(required=True, default=1.0)
    price_unit = fields.Float(required=True)
    discount = fields.Float(default=0.0)
    tax_ids = fields.Many2many(
        "account.tax", string="Taxes", compute="_compute_tax_ids", store=True,
        readonly=True, check_company=True,
    )
    lot_names = fields.Text(help="One lot or serial number per line.")
    attribute_value_ids = fields.Many2many(
        "product.template.attribute.value", readonly=True,
        compute="_compute_source_attributes", store=True,
    )
    custom_attribute_values = fields.Json(
        readonly=True, compute="_compute_source_attributes", store=True,
    )

    @api.depends("product_id", "source_order_line_id", "correction_id.root_order_id.fiscal_position_id")
    def _compute_tax_ids(self):
        for line in self:
            source = line.source_order_line_id
            if source and source.product_id == line.product_id:
                line.tax_ids = source.tax_ids
            else:
                taxes = line.product_id.taxes_id.filtered_domain(
                    self.env["account.tax"]._check_company_domain(line.company_id)
                )
                # POS maps fiscal-position taxes when computing its tax base;
                # keep the product taxes here so the mapping runs exactly once.
                line.tax_ids = taxes

    @api.depends("product_id", "source_order_line_id")
    def _compute_source_attributes(self):
        for line in self:
            source = line.source_order_line_id
            if source.product_id == line.product_id:
                line.attribute_value_ids = source.attribute_value_ids
                line.custom_attribute_values = [
                    {
                        "custom_product_template_attribute_value_id": value.custom_product_template_attribute_value_id.id,
                        "custom_value": value.custom_value,
                    }
                    for value in source.custom_attribute_value_ids
                ]
            else:
                line.attribute_value_ids = False
                line.custom_attribute_values = False

    @api.model_create_multi
    def create(self, vals_list):
        if (any(vals.get("result_order_line_id") for vals in vals_list) or self.env.context.get("default_result_order_line_id")) and not is_internal_correction_call(
            self.env
        ):
            raise UserError(self.env._("A result line can only be assigned by correction application."))
        corrections = self.env["pos.order.correction"].browse(
            [vals.get("correction_id", self.env.context.get("default_correction_id"))
             for vals in vals_list
             if vals.get("correction_id", self.env.context.get("default_correction_id"))]
        )
        corrections._lock_for_edit()
        if any(correction.state != "draft" for correction in corrections):
            raise UserError(self.env._("Lines can only be added to draft corrections."))
        clean_values = [
            {key: value for key, value in vals.items()
             if key not in {"tax_ids", "attribute_value_ids", "custom_attribute_values"}}
            for vals in vals_list
        ]
        lines = super().create(clean_values)
        # Discard imported/default tax and attribute values in favour of the
        # source identity and standard product/fiscal-position rules.
        internal_lines = lines.with_context(pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN)
        internal_lines._compute_tax_ids()
        internal_lines._compute_source_attributes()
        return lines

    def write(self, vals):
        internal = is_internal_correction_call(self.env)
        if {"result_order_line_id", "attribute_value_ids", "custom_attribute_values", "tax_ids"}.intersection(vals) and not internal:
            raise UserError(self.env._("Correction result and tax fields cannot be edited."))
        corrections = self.correction_id | self.env["pos.order.correction"].browse(
            vals.get("correction_id", [])
        )
        if not internal:
            corrections._lock_for_edit()
        if self.filtered(
            lambda line: line.correction_id.state != "draft"
        ) and not internal:
            raise UserError(self.env._("Applied correction lines cannot be edited."))
        if not internal and any(correction.state != "draft" for correction in corrections):
            raise UserError(self.env._("Lines can only belong to draft corrections."))
        return super().write(vals)

    def unlink(self):
        self.correction_id._lock_for_edit()
        if self.filtered(lambda line: line.correction_id.state != "draft"):
            raise UserError(self.env._("Applied correction lines cannot be deleted."))
        return super().unlink()


class PosOrderCorrectionPayment(models.Model):
    _name = "pos.order.correction.payment"
    _description = "POS Order Correction Payment"
    _order = "payment_method_id"
    _check_company_auto = True

    correction_id = fields.Many2one(
        "pos.order.correction", required=True, ondelete="cascade", index=True,
        check_company=True,
    )
    company_id = fields.Many2one(related="correction_id.company_id", store=True)
    currency_id = fields.Many2one(related="correction_id.currency_id")
    payment_method_id = fields.Many2one(
        "pos.payment.method", required=True, check_company=True
    )
    amount = fields.Monetary(required=True, currency_field="currency_id")

    _unique_method = models.Constraint(
        "unique (correction_id, payment_method_id)",
        "Each payment method can occur only once in a correction.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        corrections = self.env["pos.order.correction"].browse(
            [vals.get("correction_id", self.env.context.get("default_correction_id"))
             for vals in vals_list
             if vals.get("correction_id", self.env.context.get("default_correction_id"))]
        )
        corrections._lock_for_edit()
        if any(correction.state != "draft" for correction in corrections):
            raise UserError(self.env._("Payments can only be added to draft corrections."))
        return super().create(vals_list)

    def write(self, vals):
        corrections = self.correction_id | self.env["pos.order.correction"].browse(
            vals.get("correction_id", [])
        )
        corrections._lock_for_edit()
        if any(correction.state != "draft" for correction in corrections):
            raise UserError(self.env._("Applied correction payments cannot be edited."))
        return super().write(vals)

    def unlink(self):
        self.correction_id._lock_for_edit()
        if self.filtered(lambda payment: payment.correction_id.state != "draft"):
            raise UserError(self.env._("Applied correction payments cannot be deleted."))
        return super().unlink()
