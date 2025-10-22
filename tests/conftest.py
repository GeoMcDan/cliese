def pytest_load_initial_conftests(args, early_config, parser):
    import os

    os.environ["NO_COLOR"] = "1"
    os.environ["PY_COLORS"] = "0"
