import os
from pathlib import Path

import pandas as pd

from src.pipeline import calculate_indicators, configure_raster_environment, parse_raster_filename


def test_configure_raster_environment_uses_bundled_data(monkeypatch):
    monkeypatch.delenv("PROJ_DATA", raising=False)
    monkeypatch.delenv("PROJ_LIB", raising=False)
    monkeypatch.delenv("GDAL_DATA", raising=False)

    configure_raster_environment()

    for key in ("PROJ_DATA", "PROJ_LIB", "GDAL_DATA"):
        assert key in os.environ
        assert Path(os.environ[key]).exists()


def test_parse_worldpop_filename():
    assert parse_raster_filename("ken_f_00_2025_CN_1km_R2025A_UA_v1.tif") == ("f", 0, 2025)
    assert parse_raster_filename("not-a-raster.tif") is None


def test_calculate_indicators():
    data = pd.DataFrame(
        {
            "county": ["Example"],
            "year": [2025],
            "f_0": [10], "m_0": [10],
            "f_1": [20], "m_1": [20],
            "f_15": [100], "m_15": [100],
            "f_65": [5], "m_65": [5],
        }
    )
    result = calculate_indicators(data).iloc[0]
    assert result["total_population"] == 270
    assert result["children_under_5"] == 60
    assert result["working_age"] == 200
    assert result["elderly_65plus"] == 10
    assert result["dependency_ratio"] == 35