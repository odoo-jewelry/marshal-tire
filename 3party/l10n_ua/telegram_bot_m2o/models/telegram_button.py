import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class TelegramBotButton(models.Model):
    _name = 'telegram.bot.button'
    _description = 'Telegram Bot Button'
    _order = 'sequence, id'

    response_id = fields.Many2one(
        'telegram.bot.response',
        string='Response',
        required=True,
        ondelete='cascade',
    )
    bot_id = fields.Many2one(
        related='response_id.bot_id',
        store=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    label = fields.Char(
        string='Label',
        required=True,
        help='Button text shown to user',
    )

    button_type = fields.Selection([
        ('url', 'URL'),
        ('callback', 'Callback'),
        ('command', 'Execute Command'),
        ('contact', 'Request Contact'),
        ('location', 'Request Location'),
    ], string='Button Type', default='callback', required=True)

    # URL button
    url = fields.Char(
        string='URL',
        help='URL to open when button is clicked',
    )

    # Callback button
    callback_data = fields.Char(
        string='Callback Data',
        help='Data sent when button is clicked (max 64 bytes)',
    )

    # Command button
    next_command_id = fields.Many2one(
        'telegram.bot.command',
        string='Execute Command',
        domain="[('bot_id', '=', bot_id)]",
        help='Command to execute when button is clicked',
    )

    # Styling
    new_row = fields.Boolean(
        string='New Row',
        default=False,
        help='Start a new row before this button',
    )

    @api.onchange('button_type')
    def _onchange_button_type(self):
        """Clear irrelevant fields when type changes"""
        if self.button_type != 'url':
            self.url = False
        if self.button_type not in ('callback', 'command'):
            self.callback_data = False
        if self.button_type != 'command':
            self.next_command_id = False

    @api.onchange('next_command_id')
    def _onchange_next_command_id(self):
        """Auto-set callback data for command buttons"""
        if self.next_command_id and not self.callback_data:
            self.callback_data = f"cmd:{self.next_command_id.name}"

    def _to_telegram_button(self):
        """Convert to Telegram button format"""
        self.ensure_one()

        button = {'text': self.label}

        if self.button_type == 'url':
            button['url'] = self.url

        elif self.button_type in ('callback', 'command'):
            if self.next_command_id:
                button['callback_data'] = f"cmd:{self.next_command_id.name}"
            else:
                button['callback_data'] = self.callback_data or self.label

        elif self.button_type == 'contact':
            # This requires reply keyboard, not inline
            button['request_contact'] = True

        elif self.button_type == 'location':
            # This requires reply keyboard, not inline
            button['request_location'] = True

        return button
