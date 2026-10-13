from django.urls import path

from . import views

urlpatterns = [
    path("assets", views.assets_collection_view),
    path("assets/<uuid:asset_id>", views.asset_detail_view),
    path("assets/<uuid:asset_id>/delete-preview", views.asset_delete_preview_view),
]
