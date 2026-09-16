import pytest
from fastapi import HTTPException

from app.api.dependencies.auth import require_api_key
from app.core.config import get_settings
from app.repositories.submissions import _redact


def test_api_key_disabled_when_unset():
    get_settings.cache_clear()
    assert require_api_key(None) is None  # no key configured -> open


def test_api_key_enforced_when_set(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    get_settings.cache_clear()
    try:
        assert require_api_key("secret") is None
        with pytest.raises(HTTPException):
            require_api_key("wrong")
        with pytest.raises(HTTPException):
            require_api_key(None)
    finally:
        monkeypatch.delenv("API_KEY", raising=False)
        get_settings.cache_clear()


def test_redact_masks_ssn_before_persistence():
    state = {"extracted_data": {"ssn": "123-45-6789", "wages": "80000"}}
    redacted = _redact(state)
    assert redacted["extracted_data"]["ssn"] == "***-**-6789"
    # Original is untouched (no in-place mutation).
    assert state["extracted_data"]["ssn"] == "123-45-6789"


def test_redact_masks_pan_before_persistence():
    state = {"extracted_data": {"pan": "ABCPS1234F", "salary": "1500000"}}
    redacted = _redact(state)
    assert redacted["extracted_data"]["pan"] == "ABC****4F"
    assert state["extracted_data"]["pan"] == "ABCPS1234F"
