import pytest
from pydantic import SecretStr, ValidationError

from sovereign.schemas import AuthConfiguration, ContextConfiguration, EncryptionConfig
from sovereign.utils.crypto.suites import EncryptionType


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
    def encryption_config_is_created_on_single_key(self):
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
            )
        )

    def encryption_config_is_created_on_multiple_keys(self):
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
    def encryption_config_is_created_on_single_key_with_encryption_type(
        self, encryption_type
    ):
        input_encryption_key = "abc"

        auth_configuration = AuthConfiguration(
            enabled=True,
            auth_passwords=SecretStr("test"),
            encryption_key=SecretStr(f"{input_encryption_key}:{encryption_type}"),
        )

        assert (
            auth_configuration.encryption_key.get_secret_value() == input_encryption_key
        )
        assert auth_configuration.encryption_configs == (
            EncryptionConfig(
                encryption_key=input_encryption_key,
                encryption_type=EncryptionType(encryption_type),
            ),
        )

    @pytest.mark.parametrize("encryption_type", ["fernet", "aesgcm"])
    def encryption_config_is_created_on_multiple_keys_with_same_encryption_type(
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
                encryption_type=EncryptionType.FERNET,
            )
            for encryption_key in encryption_keys
        )

        assert (
            auth_configuration.encryption_key.get_secret_value() == input_encryption_key
        )
        assert auth_configuration.encryption_configs == expected_encryption_configs

    def encryption_config_is_created_on_multiple_keys_with_mixed_encryption_types(self):
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
