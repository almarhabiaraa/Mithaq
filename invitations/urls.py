from django.urls import path
from . import views

app_name = "invitations"

urlpatterns = [
    path("access/<str:secret>/", views.access_invitation, name="access_invitation"),
    path("my-contracts/",views.my_contracts,name="my_contracts"),
    path("my-contracts/<uuid:invitation_id>/",views.invitation_contract_detail,name="invitation_contract_detail"),
    path("my-contracts/<uuid:invitation_id>/reject/",views.reject_invitation_contract,name="reject_invitation_contract"),
    path("my-contracts/<uuid:invitation_id>/sign/",views.sign_invitation_contract,name="sign_invitation_contract"),
    path("contracts/<uuid:invitation_id>/cancel/",views.cancel_contract,name="cancel_contract"),
    path("contracts/<uuid:contract_id>/submit-modification/",views.submit_contract_modification,name="submit_contract_modification"),
    path("modifications/<uuid:modification_id>/reject/",views.reject_contract_modification,name="reject_contract_modification"),
    path("contracts/<uuid:contract_id>/add-invitation/",views.add_contract_invitation,name="add_contract_invitation"),
    path("my-contracts/<uuid:invitation_id>/accept/",views.accept_invitation_contract,name="accept_invitation_contract"),
    path("modifications/<uuid:modification_id>/approve/",views.approve_contract_modification,name="approve_contract_modification"),
]