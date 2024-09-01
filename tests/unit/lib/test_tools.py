import pytest

from src.lib.tools import get_tenant_id_from_event


class TestGetTenantIdFromEvent:
    def test_get_tenant_id_from_event(self):
        tenant_id = "tenant_id"
        event = {"requestContext": {"authorizer": {"tenant_id": tenant_id}}}
        assert get_tenant_id_from_event(event) == tenant_id

    def test_get_tenant_id_from_event_with_wrong_path(self):
        with pytest.raises(KeyError):
            get_tenant_id_from_event({})

    def test_get_tenant_id_from_event_with_wrong_type(self):
        with pytest.raises(KeyError):
            get_tenant_id_from_event({"requestContext": None})
