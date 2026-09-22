import json
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class TelegramBotResponse(models.Model):
    _name = 'telegram.bot.response'
    _description = 'Telegram Bot Response'
    _order = 'sequence, id'

    command_id = fields.Many2one(
        'telegram.bot.command',
        string='Command',
        required=True,
        ondelete='cascade',
    )
    bot_id = fields.Many2one(
        related='command_id.bot_id',
        store=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
    )

    response_type = fields.Selection([
        ('text', 'Text Message'),
        ('image', 'Image'),
        ('file', 'File/Document'),
        ('location', 'Location'),
    ], string='Response Type', default='text', required=True)

    # Text response
    text = fields.Text(
        string='Message Text',
        help='Message text with variables: {first_name}, {last_name}, {user_name}, {full_name}',
    )
    parse_mode = fields.Selection([
        ('HTML', 'HTML'),
        ('Markdown', 'Markdown'),
        ('MarkdownV2', 'MarkdownV2'),
    ], string='Parse Mode', default='HTML')

    # Image response
    image = fields.Binary(
        string='Image',
    )
    image_filename = fields.Char(
        string='Image Filename',
    )

    # File response
    file = fields.Binary(
        string='File',
    )
    file_filename = fields.Char(
        string='Filename',
    )

    # Location
    latitude = fields.Float(
        string='Latitude',
    )
    longitude = fields.Float(
        string='Longitude',
    )

    # Buttons
    button_ids = fields.One2many(
        'telegram.bot.button',
        'response_id',
        string='Buttons',
    )
    buttons_per_row = fields.Integer(
        string='Buttons Per Row',
        default=2,
        help='Number of buttons per row in inline keyboard',
    )

    # Input request
    input_field = fields.Char(
        string='Save Input As',
        help='Field name to save user input (e.g., "phone", "email")',
    )
    input_prompt = fields.Char(
        string='Input Prompt',
        help='Text shown when waiting for input',
    )

    # Next action
    next_command_id = fields.Many2one(
        'telegram.bot.command',
        string='Next Command',
        help='Command to execute after this response',
        domain="[('bot_id', '=', bot_id)]",
    )
    delay_seconds = fields.Integer(
        string='Delay (seconds)',
        default=0,
        help='Delay before sending this response',
    )

    @api.depends('response_type', 'text')
    def _compute_name(self):
        for rec in self:
            if rec.response_type == 'text' and rec.text:
                rec.name = rec.text[:50] + ('...' if len(rec.text) > 50 else '')
            else:
                rec.name = dict(rec._fields['response_type'].selection).get(rec.response_type, '')

    def _format_text(self, text, context_data):
        """Format text with context variables"""
        if not text:
            return ''

        try:
            return text.format(**context_data)
        except KeyError as e:
            _logger.warning(f"Missing variable in template: {e}")
            return text

    def _build_reply_markup(self):
        """Build inline keyboard markup"""
        self.ensure_one()

        if not self.button_ids:
            return None

        buttons = []
        current_row = []

        for button in self.button_ids.sorted('sequence'):
            btn_data = button._to_telegram_button()
            current_row.append(btn_data)

            if len(current_row) >= self.buttons_per_row:
                buttons.append(current_row)
                current_row = []

        if current_row:
            buttons.append(current_row)

        return {'inline_keyboard': buttons}

    def send(self, chat, context_data):
        """Send this response to the chat"""
        self.ensure_one()

        import time

        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)

        bot = self.command_id.bot_id
        telegram_chat_id = chat.telegram_chat_id
        reply_markup = self._build_reply_markup()

        result = None

        if self.response_type == 'text' and self.text:
            formatted_text = self._format_text(self.text, context_data)
            result = bot.send_message(
                telegram_chat_id,
                formatted_text,
                reply_markup=reply_markup,
                parse_mode=self.parse_mode,
            )

        elif self.response_type == 'image' and self.image:
            caption = self._format_text(self.text, context_data) if self.text else None
            result = bot.send_photo(
                telegram_chat_id,
                self.image,
                caption=caption,
                reply_markup=reply_markup,
            )

        elif self.response_type == 'file' and self.file:
            caption = self._format_text(self.text, context_data) if self.text else None
            result = bot.send_document(
                telegram_chat_id,
                self.file,
                self.file_filename or 'document',
                caption=caption,
                reply_markup=reply_markup,
            )

        elif self.response_type == 'location' and self.latitude and self.longitude:
            result = bot._call_telegram_api('sendLocation', {
                'chat_id': telegram_chat_id,
                'latitude': self.latitude,
                'longitude': self.longitude,
                'reply_markup': reply_markup,
            })

        # Log outgoing message
        if result:
            self.env['telegram.bot.message'].create({
                'chat_id': chat.id,
                'direction': 'outgoing',
                'telegram_message_id': str(result.get('message_id', '')),
                'message_type': self.response_type,
                'text': self.text,
            })

        # Handle next command
        if self.next_command_id and not self.input_field:
            self.next_command_id.execute(chat)

        return result
