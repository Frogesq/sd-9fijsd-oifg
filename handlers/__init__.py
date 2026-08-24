from . import common, business, payment, admin

def get_handlers():
    return [
        common.router,
        payment.router,
        admin.router,
        business.router
    ]
