from __future__ import annotations

from django.db.models import Min, Q, QuerySet

from .models import Asset
from .serializers import public_asset

FILTER_LIMITS = {"environment": 128, "region": 128, "owner": 128}
SORTS = {
    "asset_no": "identity__normalized_asset_no",
    "-asset_no": "-identity__normalized_asset_no",
    "name": "name",
    "-name": "-name",
    "type": "type",
    "-type": "-type",
    "status": "status",
    "-status": "-status",
    "environment": "environment",
    "-environment": "-environment",
    "region": "region",
    "-region": "-region",
    "owner": "owner",
    "-owner": "-owner",
    "ip": "min_ip",
    "-ip": "-min_ip",
}


def asset_list(params) -> dict[str, object]:
    queryset = Asset.objects.select_related("identity", "host", "host__identity").prefetch_related("addresses")
    queryset = _apply_filters(queryset, params)
    sort = params.get("sort") or "asset_no"
    if sort not in SORTS:
        raise ValueError("SORT_INVALID")
    page, page_size = _pagination(params)
    queryset = queryset.annotate(min_ip=Min("addresses__ip_key"))
    total = queryset.distinct().count()
    start = (page - 1) * page_size
    order = SORTS[sort]
    items = queryset.distinct().order_by(order, "uuid")[start:start + page_size]
    return {"items": [public_asset(item) for item in items], "total": total, "page": page, "page_size": page_size}


def _apply_filters(queryset: QuerySet[Asset], params) -> QuerySet[Asset]:
    q = params.get("q")
    if q:
        if len(q) > 256:
            raise ValueError("QUERY_TOO_LONG")
        query = q.strip()
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(asset_no__icontains=query)
            | Q(hostname__icontains=query)
            | Q(addresses__ip_key__icontains=query)
        )
    for field in ("type", "status", "environment", "region", "owner"):
        value = params.get(field)
        if not value:
            continue
        if field in FILTER_LIMITS and len(value) > FILTER_LIMITS[field]:
            raise ValueError(f"{field.upper()}_TOO_LONG")
        queryset = queryset.filter(**{field: value})
    return queryset


def _pagination(params) -> tuple[int, int]:
    try:
        page = int(params.get("page", "1"))
        page_size = int(params.get("page_size", "25"))
    except ValueError as exc:
        raise ValueError("PAGINATION_INVALID") from exc
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("PAGINATION_INVALID")
    return page, page_size
