from unittest.mock import patch

from src.config import ENVIRONMENT_SETTINGS, is_prod


def test_is_prod_only_for_production_environment():
    with patch.object(ENVIRONMENT_SETTINGS, "APP_ENV", " production "):
        assert is_prod() is True

    with patch.object(ENVIRONMENT_SETTINGS, "APP_ENV", "staging"):
        assert is_prod() is False
