import pytest

import testproj.registration as registration


@pytest.fixture
def setup_logger_extension():
    with registration.registration_context() as ctx:
        yield ctx
