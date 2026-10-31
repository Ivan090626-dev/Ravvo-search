from . import admin, autosearch, premium, search, start, subs, traps

routers = [admin.router, subs.router, start.router, search.router, traps.router, autosearch.router, premium.router]
