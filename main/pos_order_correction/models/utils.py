CORRECTION_INTERNAL_TOKEN = object()


def is_internal_correction_call(env):
    return env.context.get("pos_order_correction_internal") is CORRECTION_INTERNAL_TOKEN
