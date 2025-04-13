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

    def _get_float_param(self) -> float:
        param_key = inspect.currentframe().f_back.f_code.co_name  # the calling function name
        if not self._settings_dict:
            raise RuntimeError(f'_settings_dict is not initialized yet')

        try:
            value = float(str(self._settings_dict[param_key]))
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

    def _get_str_list_param(self) -> list[str]:
        param_key = inspect.currentframe().f_back.f_code.co_name  # the calling function name
        if not self._settings_dict:
            raise RuntimeError(f'_settings_dict is not initialized yet')

        try:
            raw_value = self._settings_dict[param_key]
            value = [x.strip() for x in raw_value.strip().split('\n')] if raw_value and raw_value.strip() else []
            return value
        except Exception as e:
            raise ValueError(f'invalid or misconfigured list of string parameter "{param_key}": {e}')

    @property
    def xui_name(self) -> str:
        """Local 3X-UI server name"""
        return self._get_str_param()

    @property
    def max_allowable_time_drift(self) -> float:
        """Maximum non-fatal local time drift with respect to NTP, seconds"""
        return self._get_float_param()

    @property
    def xui_url(self) -> str:
        """Local 3X-UI server URL"""
        return self._get_str_param()

    @property
    def xui_username(self) -> str:
        """Local 3X-UI username"""
        return self._get_str_param()

    @property
    def xui_password(self) -> str:
        """Local 3X-UI password"""
        return self._get_str_param()

    @property
    def dir_snapshots(self) -> str:
        """Directory for saving traffic snapshots"""
        return self._get_str_param()

    @property
    def dir_report(self) -> str:
        """Directory for saving the report"""
        return self._get_str_param()

    @property
    def urls_traffic_snapshots(self) -> list[str]:
        """List of URLs for VPN server traffic statistics"""
        return self._get_str_list_param()

    @property
    def snapshot_dict_datetime_key(self) -> str:
        """key name datetime value saved in snapshot json"""
        return self._get_str_param()

    @property
    def snapshot_dict_comment_key(self) -> str:
        """Key name for comment saved in snapshot json"""
        return self._get_str_param()

    @property
    def aiohttp_limit_per_host(self) -> int:
        """Maximum number of simultaneous HTTP connections"""
        return self._get_int_param()

    @property
    def aiohttp_tries(self) -> int:
        """The number of attempts to execute an HTTP request before failure"""
        return self._get_int_param()

    @property
    def aiohttp_retry_pause_initial(self) -> float:
        """Pause after the first failed HTTP request, seconds"""
        return self._get_float_param()

    @property
    def aiohttp_retry_pause_multiplier(self) -> float:
        """Multiplier for the next pause in case of unsuccessful repeated HTTP request"""
        return self._get_float_param()

    @property
    def snapshot_filename_suffix_format(self) -> str:
        """File name suffix format for saving a snapshot"""
        return self._get_str_param()

    @property
    def snapshot_filename_suffix_length(self) -> int:
        """The length of the file name suffix according to the format"""
        return self._get_int_param()


settings = Settings()


def includeme(config: pyramid.config.Configurator):
    """This function is called by the Pyramid configurator.
    """
    settings.init(config.registry.settings)
