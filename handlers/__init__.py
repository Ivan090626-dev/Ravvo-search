from . import admin, autosearch, premium, search, start, traps

routers = [admin.router, start.router, search.router, traps.router, autosearch.router, premium.router]
