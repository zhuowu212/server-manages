from django.urls import path

from . import ui_views

urlpatterns = [
    path("assets", ui_views.assets_page, name="assets_page"),
    path("assets/new", ui_views.asset_new_page, name="asset_new_page"),
    path("assets/<uuid:asset_id>", ui_views.asset_detail_page, name="asset_detail_page"),
]
