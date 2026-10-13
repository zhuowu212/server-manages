from __future__ import annotations

from typing import cast

from accounts.models import User
from common.authorization import require_roles
from common.errors import safe_error_code
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .models import Asset
from .selectors import asset_list
from .serializers import public_asset
from .services import create_asset


@require_http_methods(["GET"])
@require_roles("admin", "editor", "viewer")
def assets_page(request: HttpRequest) -> HttpResponse:
    user = cast(User, request.user)
    context: dict[str, object] = {"result": asset_list(request.GET), "can_write": user.role in {"admin", "editor"}}
    return render(request, "assets/list.html", context)


@csrf_protect
@require_http_methods(["GET", "POST"])
@require_roles("admin", "editor")
def asset_new_page(request: HttpRequest) -> HttpResponse:
    context: dict[str, object] = {"types": Asset.Type.choices, "statuses": Asset.Status.choices}
    if request.method == "POST":
        actor = cast(User, request.user)
        try:
            asset = create_asset(actor=actor, payload=_payload_from_post(request))
        except (TypeError, ValueError) as exc:
            context["error"] = safe_error_code(exc, "ASSET_FIELDS_INVALID")
        else:
            return HttpResponseRedirect(f"/assets/{asset.uuid}")
    return render(request, "assets/form.html", context)


@require_http_methods(["GET"])
@require_roles("admin", "editor", "viewer")
def asset_detail_page(request: HttpRequest, asset_id) -> HttpResponse:
    asset = Asset.objects.select_related("identity", "host", "host__identity").prefetch_related("addresses").filter(uuid=asset_id).first()
    if asset is None:
        return render(request, "assets/detail.html", {"missing": True}, status=404)
    user = cast(User, request.user)
    return render(request, "assets/detail.html", {"asset": public_asset(asset), "can_delete": user.role == "admin"})


def _payload_from_post(request: HttpRequest) -> dict[str, object]:
    def text(name: str) -> str:
        return request.POST.get(name, "")

    def ips(name: str) -> list[str]:
        value = request.POST.get(name, "")
        return [item.strip() for item in value.split(";") if item.strip()]

    return {
        "name": text("name"),
        "asset_no": text("asset_no"),
        "type": text("type"),
        "purpose": text("purpose"),
        "environment": text("environment"),
        "owner": text("owner"),
        "status": text("status"),
        "room": text("room"),
        "region": text("region"),
        "hardware_text": text("hardware_text"),
        "serial": text("serial"),
        "hostname": text("hostname"),
        "supplier": text("supplier"),
        "purchase_date": text("purchase_date"),
        "rack_date": text("rack_date"),
        "warranty_end": text("warranty_end"),
        "expires_on": text("expires_on"),
        "credential_ref": text("credential_ref"),
        "host_asset_no": text("host_asset_no"),
        "internal_ips": ips("internal_ips"),
        "external_ips": ips("external_ips"),
    }
