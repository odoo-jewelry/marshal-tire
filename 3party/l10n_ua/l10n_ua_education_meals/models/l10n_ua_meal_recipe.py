from odoo import api, fields, models


MEAL_KIND = [
    ('breakfast', 'Сніданок'),
    ('lunch', 'Обід'),
    ('afternoon', 'Полуденок'),
    ('dinner', 'Вечеря'),
    ('snack', 'Перекус'),
]

AGE_GROUP = [
    ('zdo_1_3', 'ЗДО 1-3 роки'),
    ('zdo_3_6', 'ЗДО 3-6 років'),
    ('school_1_4', 'Школа 1-4 класи'),
    ('school_5_11', 'Школа 5-11 класи'),
    ('other', 'Інше'),
]


class L10nUaMealRecipe(models.Model):
    """Технологічна картка страви."""
    _name = 'l10n_ua.meal.recipe'
    _description = 'Технологічна картка страви'
    _order = 'name'

    name = fields.Char(string='Назва страви', required=True)
    code = fields.Char(string='Код')
    meal_kind = fields.Selection(MEAL_KIND, string='Тип прийому', default='lunch')
    age_group = fields.Selection(AGE_GROUP, string='Вікова група', default='zdo_3_6')
    yield_grams = fields.Float(string='Вихід порції, г', help='Маса готової порції')
    calories_kcal = fields.Float(string='Калорійність, ккал')
    protein_g = fields.Float(string='Білки, г')
    fat_g = fields.Float(string='Жири, г')
    carbohydrate_g = fields.Float(string='Вуглеводи, г')
    cooking_instructions = fields.Html(string='Технологія приготування')
    ingredient_ids = fields.One2many('l10n_ua.meal.recipe.ingredient', 'recipe_id',
                                       string='Інгредієнти')
    active = fields.Boolean(default=True)


class L10nUaMealRecipeIngredient(models.Model):
    _name = 'l10n_ua.meal.recipe.ingredient'
    _description = 'Інгредієнт страви'
    _order = 'recipe_id, sequence'

    recipe_id = fields.Many2one('l10n_ua.meal.recipe', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Продукт', required=True)
    quantity_g = fields.Float(string='Закладка нетто, г', required=True)
    gross_g = fields.Float(string='Брутто, г',
                            help='Маса до обробки/чистки. Корисно для розрахунку '
                                 'потреби у продуктах.')
    note = fields.Char(string='Примітка')
