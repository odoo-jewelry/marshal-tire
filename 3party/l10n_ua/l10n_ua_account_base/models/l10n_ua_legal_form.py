from odoo import fields, models


class L10nUaLegalForm(models.Model):
    """Ukrainian Legal Forms (Організаційно-правові форми)."""
    _name = 'l10n_ua.legal.form'
    _description = 'Legal Form'
    _order = 'sequence, code'

    code = fields.Char(
        string='Code',
        required=True,
        index=True,
        help='Legal form code according to Ukrainian classification',
    )
    name = fields.Char(
        string='Name',
        required=True,
        translate=True,
    )
    short_name = fields.Char(
        string='Short Name',
        translate=True,
        help='Abbreviated form (e.g., ТОВ, ПП, ФОП)',
    )
    is_fop = fields.Boolean(
        string='Is FOP',
        default=False,
        help='Check if this is a sole proprietor (ФОП)',
    )
    is_legal_entity = fields.Boolean(
        string='Is Legal Entity',
        default=True,
        help='Check if this is a legal entity (юридична особа)',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    active = fields.Boolean(
        default=True,
    )

    _unique_code = models.Constraint(
        'UNIQUE(code)',
        'Legal form code must be unique!',
    )

    def name_get(self):
        return [(rec.id, f"{rec.short_name or rec.code} - {rec.name}") for rec in self]
