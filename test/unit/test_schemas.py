import random

import pytest
from pydantic import SecretStr, ValidationError

from sovereign.configuration import (
    AuthConfiguration,
    ContextConfiguration,
    EncryptionConfig,
    SupervisordConfig,
    default_hash_rules,
)
from sovereign.utils.crypto.suites import EncryptionType
from sovereign.utils.mock import mock_discovery_request


class TestContextConfiguration:
    @pytest.mark.parametrize("input_rate", [1, 5000, 10000])
    def test_context_configuration_refresh_rate_valid(self, input_rate: int) -> None:
        context_configuration = ContextConfiguration(
            context={}, refresh=True, refresh_rate=input_rate
        )

        assert context_configuration.refresh_rate == input_rate

    @pytest.mark.parametrize(
        "input_cron_expression",
        [
            "* * * * *",
            "1 * 2 * 3",
            "*/5 * * * *",
        ],
    )
    def test_context_configuration_refresh_cron_valid(
        self, input_cron_expression: str
    ) -> None:
        context_configuration = ContextConfiguration(
            context={}, refresh=True, refresh_cron=input_cron_expression
        )
        assert context_configuration.refresh_cron == input_cron_expression

    @pytest.mark.parametrize(
        "input_cron_expression",
        [
            "* * */5 * * * *",
            "0 0 0 */10 *",
            "test",
        ],
    )
    def test_context_configuration_refresh_cron_raises_on_invalid_expression(
        self,
        input_cron_expression: str,
    ) -> None:
        with pytest.raises(ValidationError):
            ContextConfiguration(
                context={}, refresh=True, refresh_cron=input_cron_expression
            )

    def test_context_configuration_sets_default(self) -> None:
        context_configuration = ContextConfiguration(context={}, refresh=True)
        assert context_configuration.refresh_rate is not None

    def test_context_configuration_raises_on_multiple_refresh_methods(self) -> None:
        with pytest.raises(RuntimeError):
            ContextConfiguration(
                context={}, refresh=True, refresh_rate=5, refresh_cron="* * * * *"
            )


class TestAuthConfiguration:
    def test_encryption_config_is_created_on_single_key(self):
        input_encryption_key = "abc"

        auth_configuration = AuthConfiguration(
            enabled=True,
            auth_passwords=SecretStr("test"),
            encryption_key=SecretStr(input_encryption_key),
        )

        assert (
            auth_configuration.encryption_key.get_secret_value() == input_encryption_key
        )
        assert auth_configuration.encryption_configs == (
            EncryptionConfig(
                encryption_key=input_encryption_key,
                encryption_type=EncryptionType.FERNET,
            ),
        )

    def test_encryption_config_is_created_on_multiple_keys(self):
        input_encryption_key = "abc def xyz"

        auth_configuration = AuthConfiguration(
            enabled=True,
            auth_passwords=SecretStr("test"),
            encryption_key=SecretStr(input_encryption_key),
        )

        expected_encryption_configs = tuple(
            EncryptionConfig(
                encryption_key=encryption_key,
                encryption_type=EncryptionType.FERNET,
            )
            for encryption_key in input_encryption_key.split(" ")
        )

        assert (
            auth_configuration.encryption_key.get_secret_value() == input_encryption_key
        )
        assert auth_configuration.encryption_configs == expected_encryption_configs

    @pytest.mark.parametrize("encryption_type", ["fernet", "aesgcm"])
    def test_encryption_config_is_created_on_single_key_with_encryption_type(
        self, encryption_type
    ):
        input_encryption_key = "abc"

        auth_configuration = AuthConfiguration(
            enabled=True,
            auth_passwords=SecretStr("test"),
            encryption_key=SecretStr(f"{input_encryption_key}:{encryption_type}"),
        )

        assert (
            auth_configuration.encryption_key.get_secret_value()
            == f"{input_encryption_key}:{encryption_type}"
        )
        assert auth_configuration.encryption_configs == (
            EncryptionConfig(
                encryption_key=input_encryption_key,
                encryption_type=EncryptionType(encryption_type),
            ),
        )

    @pytest.mark.parametrize("encryption_type", ["fernet", "aesgcm"])
    def test_encryption_config_is_created_on_multiple_keys_with_same_encryption_type(
        self, encryption_type
    ):
        encryption_key_prefix = ["abc", "def", "xyz"]
        encryption_keys = [f"{key}:{encryption_type}" for key in encryption_key_prefix]
        input_encryption_key = " ".join(encryption_keys)

        auth_configuration = AuthConfiguration(
            enabled=True,
            auth_passwords=SecretStr("test"),
            encryption_key=SecretStr(input_encryption_key),
        )

        expected_encryption_configs = tuple(
            EncryptionConfig(
                encryption_key=encryption_key,
                encryption_type=EncryptionType(encryption_type),
            )
            for encryption_key in encryption_key_prefix
        )

        assert (
            auth_configuration.encryption_key.get_secret_value() == input_encryption_key
        )
        assert auth_configuration.encryption_configs == expected_encryption_configs

    def test_encryption_config_is_created_on_multiple_keys_with_mixed_encryption_types(
        self,
    ):
        input_encryption_key = "abc:fernet def xyz:aesgcm"

        auth_configuration = AuthConfiguration(
            enabled=True,
            auth_passwords=SecretStr("test"),
            encryption_key=SecretStr(input_encryption_key),
        )

        assert (
            auth_configuration.encryption_key.get_secret_value() == input_encryption_key
        )
        assert auth_configuration.encryption_configs == (
            EncryptionConfig(
                encryption_key="abc",
                encryption_type=EncryptionType.FERNET,
            ),
            EncryptionConfig(
                encryption_key="def",
                encryption_type=EncryptionType.FERNET,
            ),
            EncryptionConfig(
                encryption_key="xyz",
                encryption_type=EncryptionType.AESGCM,
            ),
        )

    def test_encryption_config_is_read_from_environment_variables(self, monkeypatch):
        input_encryption_key = "abc"

        monkeypatch.setenv("SOVEREIGN_AUTH_ENABLED", "true")
        monkeypatch.setenv("SOVEREIGN_AUTH_PASSWORDS", "test")
        monkeypatch.setenv("SOVEREIGN_ENCRYPTION_KEY", input_encryption_key)

        auth_configuration = AuthConfiguration()

        assert auth_configuration.enabled is True
        assert auth_configuration.auth_passwords.get_secret_value() == "test"
        assert (
            auth_configuration.encryption_key.get_secret_value() == input_encryption_key
        )
        assert auth_configuration.encryption_configs == (
            EncryptionConfig(
                encryption_key=input_encryption_key,
                encryption_type=EncryptionType.FERNET,
            ),
        )


class TestSupervisordConfig:
    def test_supervisord_config_defaults(self):
        supervisord_config = SupervisordConfig()

        assert supervisord_config.nodaemon is True
        assert supervisord_config.loglevel == "error"
        assert supervisord_config.pidfile == "/tmp/supervisord.pid"
        assert supervisord_config.logfile == "/tmp/supervisord.log"
        assert supervisord_config.directory == "%(here)s"

    def test_supervisord_config_from_environment(self, monkeypatch):
        monkeypatch.setenv("SOVEREIGN_SUPERVISORD_NODAEMON", "false")
        monkeypatch.setenv("SOVEREIGN_SUPERVISORD_LOGLEVEL", "info")
        monkeypatch.setenv("SOVEREIGN_SUPERVISORD_PIDFILE", "/var/tmp/supervisord.pid")
        monkeypatch.setenv("SOVEREIGN_SUPERVISORD_LOGFILE", "/var/tmp/supervisord.log")
        monkeypatch.setenv("SOVEREIGN_SUPERVISORD_DIRECTORY", "/var")

        supervisord_config = SupervisordConfig()

        assert supervisord_config.nodaemon is False
        assert supervisord_config.loglevel == "info"
        assert supervisord_config.pidfile == "/var/tmp/supervisord.pid"
        assert supervisord_config.logfile == "/var/tmp/supervisord.log"
        assert supervisord_config.directory == "/var"

    def test_output_supervisord_config(self, monkeypatch):
        monkeypatch.setenv("SOVEREIGN_SUPERVISORD_NODAEMON", "false")
        monkeypatch.setenv("SOVEREIGN_SUPERVISORD_LOGLEVEL", "info")
        monkeypatch.setenv("SOVEREIGN_SUPERVISORD_PIDFILE", "/var/tmp/supervisord.pid")
        monkeypatch.setenv("SOVEREIGN_SUPERVISORD_LOGFILE", "/var/tmp/supervisord.log")
        monkeypatch.setenv("SOVEREIGN_SUPERVISORD_DIRECTORY", "/var/tmp")

        # Mock NamedTemporaryFile to capture the written content
        from io import StringIO
        from unittest.mock import MagicMock, patch

        from sovereign.server import write_supervisor_conf

        # Create a mock file object that behaves like a real file
        mock_file = StringIO()
        mock_file.name = "/tmp/test_supervisord.conf"

        # Create a context manager mock for NamedTemporaryFile
        mock_temp_file = MagicMock()
        mock_temp_file.return_value.__enter__ = MagicMock(return_value=mock_file)
        mock_temp_file.return_value.__exit__ = MagicMock(return_value=None)

        with patch("tempfile.NamedTemporaryFile", mock_temp_file):
            result_path = write_supervisor_conf()

        # Get the written content
        written_content = mock_file.getvalue()

        # Validate the supervisord configuration content
        assert "nodaemon = false" in written_content
        assert "loglevel = info" in written_content
        assert "pidfile = /var/tmp/supervisord.pid" in written_content
        assert "logfile = /var/tmp/supervisord.log" in written_content
        assert "directory = /var/tmp" in written_content

        # Validate that NamedTemporaryFile was called with correct parameters
        mock_temp_file.assert_called_once_with("w", delete=False)

        # Validate that the function returns the mock file name
        assert str(result_path) == "/tmp/test_supervisord.conf"


def test_discovery_request_cache_key_is_deterministic():
    req = mock_discovery_request(
        api_version="V3",
        resource_type="listeners",
        resource_names=["fake", "abc"],
        metadata={
            "foo": "baz",
            "bar": "foo",
            "version": str(random.randint(100, 1000)),
        },
        expressions=["cluster=T1"],
    )
    key = req.cache_key(default_hash_rules())

    for _ in range(30):
        req = mock_discovery_request(
            api_version="V3",
            resource_type="listeners",
            resource_names=["fake", "abc"],
            metadata={
                "foo": "baz",
                "bar": "foo",
                "version": str(random.randint(100, 1000)),
            },
            expressions=["cluster=T1"],
        )
        new = req.cache_key(default_hash_rules())
        assert new == key
