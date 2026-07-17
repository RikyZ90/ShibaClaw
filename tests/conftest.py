import warnings
import pytest

# Suppress warnings that happen at import time
warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated")
warnings.filterwarnings("ignore", category=Warning, module="starlette.testclient")


@pytest.fixture(autouse=True)
def clear_system_caches():
    """Clear caches on system helpers after each test to avoid cross-test pollution from mocks."""
    yield
    from shibaclaw.helpers.system import (
        get_os_type,
        is_running_in_docker,
        is_running_in_pip_env,
        is_running_as_exe,
        get_installation_method,
    )

    get_os_type.cache_clear()
    is_running_in_docker.cache_clear()
    is_running_in_pip_env.cache_clear()
    is_running_as_exe.cache_clear()
    get_installation_method.cache_clear()
