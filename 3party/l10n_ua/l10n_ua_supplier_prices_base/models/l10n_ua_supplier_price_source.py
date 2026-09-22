from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nUaSupplierPriceSource(models.Model):
    _name = 'l10n_ua.supplier.price.source'
    _description = 'Supplier Price Source Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Name', required=True, tracking=True)
    partner_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        domain=[('supplier_rank', '>', 0)],
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        help='Якщо вказано — імпортовані ціни прив\'язуються до цієї компанії. '
             'Якщо порожнє — ціни глобальні (для всіх компаній).',
        tracking=True,
    )
    active = fields.Boolean(default=True)

    fetcher_type = fields.Selection(
        selection=[('manual', 'Manual Upload')],
        string='Fetcher Type',
        required=True,
        default='manual',
        tracking=True,
        help='Розширюється модулями: api, sftp, email',
    )
    parser_type = fields.Selection(
        selection=[('json', 'JSON')],
        string='Parser Type',
        required=True,
        default='json',
        tracking=True,
        help='Розширюється модулями: xml, xlsx, csv',
    )

    mapping_id = fields.Many2one(
        'l10n_ua.supplier.price.mapping',
        string='Mapping',
        required=True,
        tracking=True,
    )
    currency_default_id = fields.Many2one(
        'res.currency',
        string='Default Currency',
        default=lambda self: self.env.company.currency_id,
        help='Використовується коли валюту не вказано в файлі',
    )
    unknown_sku_action = fields.Selection(
        selection=[
            ('skip', 'Skip silently'),
            ('log_only', 'Log without applying'),
            ('create_product', 'Create new product'),
            ('error_stop', 'Stop with error'),
        ],
        default='log_only',
        required=True,
        string='Unknown SKU Action',
        tracking=True,
    )

    auto_sync_active = fields.Boolean(
        string='Auto Sync',
        default=False,
        tracking=True,
    )
    sync_interval_hours = fields.Integer(
        string='Sync Interval (hours)',
        default=24,
    )
    last_sync_date = fields.Datetime(string='Last Sync', readonly=True)

    fetch_timeout = fields.Integer(
        string='Fetch Timeout (sec)',
        default=60,
        required=True,
        help='Connect + read timeout для API/SFTP/email',
    )
    parse_timeout = fields.Integer(
        string='Parse Timeout (sec)',
        default=300,
        required=True,
    )
    apply_timeout = fields.Integer(
        string='Apply Timeout (sec)',
        default=600,
        required=True,
    )
    watchdog_timeout_minutes = fields.Integer(
        string='Stuck Import Timeout (min)',
        default=30,
        required=True,
        help='Імпорти у проміжних станах довше цього часу = error',
    )

    connection_config = fields.Text(
        string='Connection Config',
        help='JSON з налаштуваннями fetcher (URL, credentials тощо). '
             'Структура залежить від fetcher_type.',
    )

    import_ids = fields.One2many(
        'l10n_ua.supplier.price.import',
        'source_id',
        string='Imports',
    )
    import_count = fields.Integer(
        string='Import Count',
        compute='_compute_import_stats',
    )
    last_import_state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('fetching', 'Fetching'),
            ('fetched', 'Fetched'),
            ('parsing', 'Parsing'),
            ('parsed', 'Parsed'),
            ('applying', 'Applying'),
            ('done', 'Done'),
            ('error', 'Error'),
        ],
        string='Last Import State',
        compute='_compute_import_stats',
    )

    @api.depends('import_ids', 'import_ids.state')
    def _compute_import_stats(self):
        for source in self:
            imports = source.import_ids.sorted('date_imported', reverse=True)
            source.import_count = len(imports)
            source.last_import_state = imports[0].state if imports else False

    @api.constrains('fetch_timeout', 'parse_timeout', 'apply_timeout', 'watchdog_timeout_minutes')
    def _check_timeouts(self):
        for source in self:
            if source.fetch_timeout < 1 or source.parse_timeout < 1 or source.apply_timeout < 1:
                raise ValidationError(_("Timeouts must be at least 1 second."))
            if source.watchdog_timeout_minutes < 1:
                raise ValidationError(_("Watchdog timeout must be at least 1 minute."))

    @api.constrains('sync_interval_hours', 'auto_sync_active')
    def _check_sync_interval(self):
        for source in self:
            if source.auto_sync_active and source.sync_interval_hours < 1:
                raise ValidationError(_("Auto-sync requires interval ≥ 1 hour."))

    def action_create_import(self):
        """Create a new draft import for this source."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Import'),
            'res_model': 'l10n_ua.supplier.price.import',
            'view_mode': 'form',
            'context': {
                'default_source_id': self.id,
            },
            'target': 'current',
        }

    def action_view_imports(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Imports'),
            'res_model': 'l10n_ua.supplier.price.import',
            'view_mode': 'list,form',
            'domain': [('source_id', '=', self.id)],
            'context': {'default_source_id': self.id},
        }
