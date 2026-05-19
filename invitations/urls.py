from django.urls import path
from . import views

app_name = "invitations"

urlpatterns = [
    path("contracts/<uuid:contract_id>/create/",views.create_signing_invitation,name="create_signing_invitation"),
    path("review/<uuid:invitation_id>/",views.review_signing_invitation,name="review_signing_invitation"),
    path("access/<str:secret>/", views.access_invitation, name="access_invitation"),
    #path("my-contracts/", views.participant_contracts, name="participant_contracts"),
    path("my-contracts/",views.my_contracts,name="my_contracts"),
    path("my-contracts/<uuid:invitation_id>/",views.invitation_contract_detail,name="invitation_contract_detail"),
    path("my-contracts/<uuid:invitation_id>/reject/",views.reject_invitation_contract,name="reject_invitation_contract"),
    path("my-contracts/<uuid:invitation_id>/sign/",views.sign_invitation_contract,name="sign_invitation_contract"),
]