from pathlib import Path

import yaml


def test_container_boundaries():
    compose = yaml.safe_load(Path("compose.yaml").read_text())
    for name, service in compose["services"].items():
        assert service["user"] == "10001:10001"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert "no-new-privileges:true" in service["security_opt"]
        assert service["mem_limit"] and service["pids_limit"]
        assert service["logging"]["options"]["max-file"] == "3"
        assert not service.get("privileged")
        assert service.get("network_mode") != "host"
        assert all("docker.sock" not in v for v in service.get("volumes", []))
        if name != "proxy":
            assert not service.get("ports")
    assert compose["services"]["proxy"]["ports"] == ["80:8080", "443:8443"]
    assert "admin_password" not in compose["services"]["app"]["secrets"]
