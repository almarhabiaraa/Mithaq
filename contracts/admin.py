from django.contrib import admin
from .models import Contract, ContractVersion, ContractClause, ContractParty

# added by Remas — register contract models in admin panel
admin.site.register(Contract)
admin.site.register(ContractVersion)
admin.site.register(ContractClause)
admin.site.register(ContractParty)