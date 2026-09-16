from odoo import _, api, Command, fields, models
from odoo.exceptions import UserError


class ProductConsolidationWizard(models.TransientModel):
    _name = "product.consolidation.wizard"
    _description = "Product Card Consolidation"

    mode = fields.Selection([("stock", "Current Stock Transfer"), ("history", "Full History Consolidation")],
                            required=True, default="stock", string="Consolidation Mode")
    confirmed_mode = fields.Selection(selection=[("stock", "Current Stock Transfer"),
        ("history", "Full History Consolidation")], readonly=True, copy=False)

    state = fields.Selection(
        [("preview", "Preview"), ("confirm", "Confirmation")],
        default="preview",
        required=True,
    )
    product_template_ids = fields.Many2many(
        "product.template",
        string="Selected Product Cards",
        required=True,
    )
    canonical_template_id = fields.Many2one(
        "product.template",
        string="Canonical Product Card",
        required=True,
    )
    duplicate_template_id = fields.Many2one(
        "product.template",
        string="Duplicate Product Card",
        compute="_compute_duplicate_template_id",
    )
    preview_line_ids = fields.One2many(
        "product.consolidation.preview.line",
        "wizard_id",
        string="Preview",
        readonly=True,
    )
    has_blockers = fields.Boolean(compute="_compute_has_blockers")
    analysis_fingerprint = fields.Char(readonly=True, copy=False)

    @api.model
    def default_get(self, field_names):
        values = super().default_get(field_names)
        active_ids = self.env.context.get("active_ids", [])
        if (self.env.context.get("active_model") == "product.template"
                and "default_product_template_ids" not in self.env.context):
            selected = self.env["product.template"].browse(active_ids).exists()
            values["product_template_ids"] = [(6, 0, selected.ids)]
            if selected:
                values["canonical_template_id"] = selected[0].id
        return values

    @api.depends("product_template_ids", "canonical_template_id")
    def _compute_duplicate_template_id(self):
        for wizard in self:
            wizard.duplicate_template_id = (
                wizard.product_template_ids - wizard.canonical_template_id
            )[:1]

    @api.depends("preview_line_ids.severity")
    def _compute_has_blockers(self):
        for wizard in self:
            wizard.has_blockers = any(
                line.severity == "blocker" for line in wizard.preview_line_ids
            )

    def _service(self):
        return self.env["product.card.consolidation.service"]

    @api.onchange("mode", "canonical_template_id")
    def _onchange_history_mode(self):
        self.state = "preview"
        self.analysis_fingerprint = False
        self.confirmed_mode = False
        self.preview_line_ids = [Command.clear()]

    def write(self, vals):
        if {"mode", "canonical_template_id", "product_template_ids"}.intersection(vals):
            vals = {**vals, "state": "preview", "analysis_fingerprint": False, "confirmed_mode": False}
        return super().write(vals)

    def _validate_selection(self):
        self.ensure_one()
        if len(self.product_template_ids) != 2:
            raise UserError(_("Select exactly two product cards."))
        if self.canonical_template_id not in self.product_template_ids:
            raise UserError(_("The canonical card must be one of the selected product cards."))
        duplicate = self.product_template_ids - self.canonical_template_id
        duplicate.ensure_one()
        return duplicate

    def _reload_action(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Consolidate Product Cards"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_preview(self):
        self.ensure_one()
        duplicate = self._validate_selection()
        analysis = self._service().analyze(self.canonical_template_id, duplicate, mode=self.mode)
        self.preview_line_ids.unlink()
        self.env["product.consolidation.preview.line"].create([
            {**line, "wizard_id": self.id} for line in analysis["lines"]
        ])
        self.analysis_fingerprint = analysis["fingerprint"]
        self.state = "preview"
        return self._reload_action()

    def action_request_confirmation(self):
        self.ensure_one()
        self.action_preview()
        if self.has_blockers:
            raise UserError(_("Resolve every blocker before consolidation."))
        self.state = "confirm"
        self.confirmed_mode = self.mode
        return self._reload_action()

    def action_back_to_preview(self):
        self.ensure_one()
        self.state = "preview"
        return self._reload_action()

    def action_confirm(self):
        self.ensure_one()
        if self.state != "confirm":
            raise UserError(_("Use the final confirmation step before consolidation."))
        if self.mode != self.confirmed_mode:
            raise UserError(_("Review the selected consolidation mode again."))
        duplicate = self._validate_selection()
        canonical = self._service().consolidate(
            self.canonical_template_id,
            duplicate,
            expected_fingerprint=self.analysis_fingerprint,
            mode=self.mode,
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "product.template",
            "res_id": canonical.id,
            "view_mode": "form",
            "target": "current",
        }


class ProductConsolidationPreviewLine(models.TransientModel):
    _name = "product.consolidation.preview.line"
    _description = "Product Consolidation Preview Line"
    _order = "severity, category, id"

    wizard_id = fields.Many2one(
        "product.consolidation.wizard",
        required=True,
        ondelete="cascade",
    )
    severity = fields.Selection(
        [
            ("blocker", "Blocker"),
            ("warning", "Warning"),
            ("transfer", "Transfer"),
            ("preserve", "Preserve"),
        ],
        required=True,
    )
    category = fields.Char(required=True)
    count = fields.Integer(required=True)
    message = fields.Char(required=True)
    quantity = fields.Float(readonly=True, digits="Product Unit")
    value = fields.Monetary(readonly=True, currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", readonly=True)
    location_id = fields.Many2one("stock.location", readonly=True)
    package_id = fields.Many2one("stock.package", readonly=True)
    source_move_id = fields.Many2one("stock.move", readonly=True)
    source_date = fields.Datetime(readonly=True)
