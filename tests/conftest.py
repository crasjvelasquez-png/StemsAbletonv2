import pytest

import stems.project


@pytest.fixture(autouse=True)
def _clear_project_cache() -> None:
    stems.project.clear_project_cache()
