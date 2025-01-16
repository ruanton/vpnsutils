"""
Convenient access to global application settings located in the ini-file.
PyCharm typing support, misconfiguration detection and error reporting.
"""

import inspect
import pyramid.config
import decimal


class Settings:
    """Global application configuration settings"""
    def __init__(self):
        self._settings_dict = None

    def init(self, settings_dict: dict[str, str]):
        if self._settings_dict:
            raise RuntimeError(f'_settings_dict is already initialized')
        self._settings_dict = settings_dict

    def _get_int_param(self) -> int:
        param_key = inspect.currentframe().f_back.f_code.co_name  # the calling function name
        if not self._settings_dict:
            raise RuntimeError(f'_settings_dict is not initialized yet')

        try:
            value = int(self._settings_dict[param_key])
            return value
        except Exception as e:
            raise ValueError(f'invalid or misconfigured integer parameter "{param_key}": {e}')

    def _get_decimal_param(self) -> decimal.Decimal:
        param_key = inspect.currentframe().f_back.f_code.co_name  # the calling function name
        if not self._settings_dict:
            raise RuntimeError(f'_settings_dict is not initialized yet')

        try:
            value = decimal.Decimal(str(self._settings_dict[param_key]))
            return value
        except Exception as e:
            raise ValueError(f'invalid or misconfigured decimal parameter "{param_key}": {e}')

    def _get_str_param(self) -> str:
        param_key = inspect.currentframe().f_back.f_code.co_name  # the calling function name
        if not self._settings_dict:
            raise RuntimeError(f'_settings_dict is not initialized yet')

        try:
            value = self._settings_dict[param_key]
            return value
        except Exception as e:
            raise ValueError(f'invalid or misconfigured string parameter "{param_key}": {e}')

    def _get_int_list_param(self) -> list[int]:
        param_key = inspect.currentframe().f_back.f_code.co_name  # the calling function name
        if not self._settings_dict:
            raise RuntimeError(f'_settings_dict is not initialized yet')

        try:
            raw_value = self._settings_dict[param_key]
            value = [int(x.strip()) for x in raw_value.split(',')] if raw_value and raw_value.strip() else []
            return value
        except Exception as e:
            raise ValueError(f'invalid or misconfigured list of integers parameter "{param_key}": {e}')

    @property
    def xui_name(self) -> str:
        """Custom parameter, rename or remove this property"""
        return self._get_str_param()

    @property
    def xui_url(self) -> str:
        """Custom parameter, rename or remove this property"""
        return self._get_str_param()

    @property
    def xui_username(self) -> str:
        """Custom parameter, rename or remove this property"""
        return self._get_str_param()

    @property
    def xui_password(self) -> str:
        """Custom parameter, rename or remove this property"""
        return self._get_str_param()

    @property
    def dir_snapshots(self) -> str:
        """Custom parameter, rename or remove this property"""
        return self._get_str_param()


settings = Settings()


def includeme(config: pyramid.config.Configurator):
    """This function is called by the Pyramid configurator.
    """
    settings.init(config.registry.settings)
