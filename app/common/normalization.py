import ipaddress


def normalized_text(value: str) -> str:
    return value.strip().casefold()


def normalized_ip(value: str) -> str:
    if "%" in value:
        raise ValueError("IP_ZONE_ID_UNSUPPORTED")
    address = ipaddress.ip_address(value.strip())
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return str(address.ipv4_mapped)
    return str(address)
