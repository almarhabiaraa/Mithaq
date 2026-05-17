from django.urls import path
from . import views

app_name = "invitations"

urlpatterns = [
    path("contracts/<uuid:contract_id>/create/",views.create_signing_invitation,name="create_signing_invitation"),
    path("review/<uuid:invitation_id>/",views.review_signing_invitation,name="review_signing_invitation"),
]