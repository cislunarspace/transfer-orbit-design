import matplotlib

matplotlib.use("Agg", force=True)

import pytest


@pytest.fixture(autouse=True)
def _reset_matplotlib_backend():
    """Force Agg backend before each test to prevent TkAgg interference."""
    try:
        import matplotlib.pyplot as plt
        plt.switch_backend("Agg")
    except Exception:
        pass
    yield
