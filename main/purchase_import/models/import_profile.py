from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError


LOOKUP_SELECTION = [
    ("supplier_code", "Vendor Product Code"),
    ("default_code", "Internal Reference"),
    ("barcode", "Barcode"),
]

TARGET_SELECTION = [
    ("quantity", "Quantity"),
    ("price", "Unit Price"),
    ("uom", "Unit of Measure"),
    ("description", "Line Description"),
    ("product_name", "Product Name"),
    ("supplier_code", "Vendor Product Code"),
    ("supplier_name", "Vendor Product Name"),
    ("default_code", "Internal Reference"),
    ("barcode", "Barcode"),
    ("min_qty", "Vendor Minimum Quantity"),
    ("attribute", "Variant Attribute"),
]


class PurchaseImportProfile(models.Model):
    _name = "purchase.import.profile"
    _description = "Purchase Import Profile"
    _order = "company_id, name, id"
    _check_company_auto = True

    _name_company_unique = models.Constraint(
        "UNIQUE(name, company_id)",
        "The import profile name must be unique per company.",
    )
    _positive_rows = models.Constraint(
        "CHECK(header_row > 0 AND data_row > header_row)",
        "The first data row must be after the header row.",
    )
    _positive_limits = models.Constraint(
        "CHECK(max_rows > 0 AND max_file_size_mb > 0)",
        "File size and row limits must be positive.",
    )

    def _default_lookup_ids(self):
        return [
            Command.create({"sequence": sequence, "lookup_type": lookup_type})
            for sequence, lookup_type in enumerate(
                ("supplier_code", "default_code", "barcode"), start=10
            )
        ]

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    encoding = fields.Char(help="Leave empty to detect the CSV encoding automatically.")
    separator = fields.Char(help="Leave empty to detect the CSV separator automatically.")
    quoting = fields.Char(default='"', required=True)
    decimal_separator = fields.Selection(
        [("dot", "Dot"), ("comma", "Comma")], default="dot", required=True
    )
    thousand_separator = fields.Selection(
        [("none", "None"), ("comma", "Comma"), ("dot", "Dot"), ("space", "Space")],
        default="none",
        required=True,
    )
    sheet = fields.Char()
    header_row = fields.Integer(default=1, required=True)
    data_row = fields.Integer(default=2, required=True)
    max_rows = fields.Integer(default=5000, required=True)
    max_file_size_mb = fields.Integer(default=10, required=True)
    unmatched_policy = fields.Selection(
        [("reject", "Reject"), ("create", "Create Product")],
        default="reject",
        required=True,
    )
    creation_mode = fields.Selection(
        [("standalone", "Standalone Product"), ("variant", "Template Variant")],
        default="standalone",
        required=True,
    )
    variant_template_id = fields.Many2one(
        "product.template",
        check_company=True,
        domain="[('company_id', 'in', [False, company_id])]",
    )
    default_product_type = fields.Selection(
        [("consu", "Goods"), ("service", "Service")],
        default="consu",
        required=True,
    )
    default_is_storable = fields.Boolean()
    default_categ_id = fields.Many2one("product.category")
    default_uom_id = fields.Many2one("uom.uom")
    default_purchase_uom_id = fields.Many2one("uom.uom")
    default_supplier_tax_ids = fields.Many2many(
        "account.tax",
        "purchase_import_profile_supplier_tax_rel",
        "profile_id",
        "tax_id",
        domain="[('type_tax_use', '=', 'purchase'), ('company_id', '=', company_id)]",
        check_company=True,
    )
    default_tracking = fields.Selection(
        [("none", "By Quantity"), ("lot", "By Lots"), ("serial", "By Serial Number")],
        default="none",
        required=True,
    )
    default_purchase_ok = fields.Boolean(default=True)
    default_sale_ok = fields.Boolean(default=False)
    mapping_ids = fields.One2many(
        "purchase.import.profile.mapping", "profile_id", copy=True
    )
    lookup_ids = fields.One2many(
        "purchase.import.profile.lookup",
        "profile_id",
        copy=True,
        default=_default_lookup_ids,
    )

    @api.constrains(
        "unmatched_policy",
        "creation_mode",
        "variant_template_id",
        "company_id",
        "default_product_type",
        "default_is_storable",
        "default_tracking",
    )
    def _check_creation_configuration(self):
        for profile in self:
            if (
                profile.unmatched_policy == "create"
                and profile.creation_mode == "variant"
                and not profile.variant_template_id
            ):
                raise ValidationError(
                    self.env._("A product template is required for variant creation.")
                )
            if (
                profile.variant_template_id.company_id
                and profile.variant_template_id.company_id != profile.company_id
            ):
                raise ValidationError(
                    self.env._("The variant template must belong to the profile company.")
                )
            if profile.default_product_type == "service" and (
                profile.default_is_storable or profile.default_tracking != "none"
            ):
                raise ValidationError(
                    self.env._("A service product cannot be storable or tracked.")
                )
            if not profile.default_is_storable and profile.default_tracking != "none":
                raise ValidationError(
                    self.env._("Tracking requires a storable product.")
                )

    @api.constrains("separator", "quoting", "decimal_separator", "thousand_separator")
    def _check_format_characters(self):
        for profile in self:
            if profile.separator and len(profile.separator) != 1:
                raise ValidationError(self.env._("The CSV separator must be one character."))
            if len(profile.quoting) != 1:
                raise ValidationError(self.env._("The text delimiter must be one character."))
            if profile.thousand_separator != "none" and (
                profile.thousand_separator == profile.decimal_separator
            ):
                raise ValidationError(
                    self.env._("Decimal and thousand separators must be different.")
                )


class PurchaseImportProfileMapping(models.Model):
    _name = "purchase.import.profile.mapping"
    _description = "Purchase Import Profile Mapping"
    _order = "sequence, id"
    _check_company_auto = True

    _source_unique = models.Constraint(
        "UNIQUE(profile_id, source_column)",
        "A source column can only be mapped once per profile.",
    )

    sequence = fields.Integer(default=10)
    profile_id = fields.Many2one(
        "purchase.import.profile", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="profile_id.company_id", store=True, index=True)
    source_column = fields.Char(required=True)
    target = fields.Selection(TARGET_SELECTION, required=True)
    attribute_id = fields.Many2one("product.attribute", ondelete="restrict")

    @api.constrains("target", "attribute_id")
    def _check_attribute_target(self):
        for mapping in self:
            if (mapping.target == "attribute") != bool(mapping.attribute_id):
                raise ValidationError(
                    self.env._("An attribute is required only for an attribute mapping.")
                )

    @api.constrains("profile_id", "target", "attribute_id")
    def _check_target_unique(self):
        for mapping in self:
            domain = [
                ("profile_id", "=", mapping.profile_id.id),
                ("target", "=", mapping.target),
                ("id", "!=", mapping.id),
            ]
            if mapping.target == "attribute":
                domain.append(("attribute_id", "=", mapping.attribute_id.id))
            if self.search_count(domain, limit=1):
                raise ValidationError(
                    self.env._("A target can only be mapped once per profile.")
                )


class PurchaseImportProfileLookup(models.Model):
    _name = "purchase.import.profile.lookup"
    _description = "Purchase Import Profile Lookup"
    _order = "sequence, id"

    _lookup_unique = models.Constraint(
        "UNIQUE(profile_id, lookup_type)",
        "A lookup type can only be configured once per profile.",
    )

    sequence = fields.Integer(default=10)
    profile_id = fields.Many2one(
        "purchase.import.profile", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="profile_id.company_id", store=True, index=True)
    lookup_type = fields.Selection(LOOKUP_SELECTION, required=True)
