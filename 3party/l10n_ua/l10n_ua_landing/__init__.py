from . import models
from . import controllers


def post_init_hook(env):
    """На install проставляємо назву/логотип website (many2one) замість
    дефолтних "My Website"/"Your Logo". Покриває сценарій перевстановлення
    демо (видалили старі модулі → встановили нові)."""
    env['website']._l10n_ua_apply_branding()
