"""Download, validate, aggregate, and summarize WorldPop Kenya rasters."""

import logging
import os
import re
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.express as px
import requests
from rasterstats import zonal_stats
import rasterio

PROJECT_DIR = Path(__file__).resolve().parents[1]
YEARS = list(range(2021, 2026))
SEXES = ["f", "m"]
AGE_GROUPS = [0, 1] + list(range(5, 95, 5))
EXPECTED_COMBINATIONS = {(sex, age) for sex in SEXES for age in AGE_GROUPS}
WORLDPOP_BASE_URL = (
    "https://data.worldpop.org/GIS/AgeSex_structures/"
    "Global_2015_2030/R2025A/{year}/KEN/v1/1km_ua/constrained"
)
RAW_DIR = PROJECT_DIR / "data" / "raw"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
FIGURES_DIR = PROJECT_DIR / "outputs" / "figures"
GADM_PATH = RAW_DIR / "gadm41_KEN_2.json"
OUTPUT_PATH = PROCESSED_DIR / "kenya_population_by_county.csv"
VALIDATION_LOG = PROCESSED_DIR / "validation_log.txt"

LOGGER = logging.getLogger("kenya_pipeline")
LOGGER.setLevel(logging.INFO)
if not LOGGER.handlers:
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    stream_handler = logging.StreamHandler()
    file_handler = logging.FileHandler(VALIDATION_LOG, encoding="utf-8")
    stream_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    LOGGER.addHandler(stream_handler)
    LOGGER.addHandler(file_handler)

for directory in (RAW_DIR, PROCESSED_DIR, FIGURES_DIR):
    directory.mkdir(parents=True, exist_ok=True)

def parse_raster_filename(filename):
    """Extract sex, age, and year from a WorldPop GeoTIFF filename."""
    pattern = r"ken_([fm])_(\d{2})_(\d{4})_CN_1km_R2025A_UA_v1\.tif$"
    match = re.match(pattern, filename)
    if not match:
        return None
    return match.group(1), int(match.group(2)), int(match.group(3))
def discover_raster_urls(session=None):
    """Discover available GeoTIFF URLs from each WorldPop year directory."""
    session = session or requests.Session()
    discovered = {}
    for year in YEARS:
        directory_url = WORLDPOP_BASE_URL.format(year=year)
        try:
            response = session.get(directory_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as error:
            LOGGER.error("Could not inspect %s: %s", directory_url, error)
            continue
        files = {}
        for href in re.findall(r'href=["\']([^"\']+\.tif)["\']', response.text):
            parsed = parse_raster_filename(href.rsplit("/", 1)[-1])
            if parsed and parsed[2] == year:
                files[(parsed[0], parsed[1])] = f"{directory_url}/{href.rsplit('/', 1)[-1]}"
        discovered[year] = files
        missing = EXPECTED_COMBINATIONS - set(files)
        LOGGER.info("%s: discovered %d GeoTIFF files", year, len(files))
        if missing:
            LOGGER.warning("%s: missing combinations: %s", year, sorted(missing))
    return discovered

def download_data(discovered, session=None):
    """Download discovered rasters with caching and atomic temporary files."""
    session = session or requests.Session()
    local_files = {}
    for year, files in discovered.items():
        local_files[year] = {}
        for combination, url in files.items():
            filename = url.rsplit("/", 1)[-1]
            filepath = RAW_DIR / filename
            if not filepath.exists():
                temporary_path = filepath.with_suffix(".part")
                LOGGER.info("Downloading %s", filename)
                try:
                    with session.get(url, stream=True, timeout=120) as response:
                        response.raise_for_status()
                        with temporary_path.open("wb") as output:
                            for chunk in response.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    output.write(chunk)
                    temporary_path.replace(filepath)
                except requests.RequestException as error:
                    temporary_path.unlink(missing_ok=True)
                    LOGGER.error("Failed to download %s: %s", url, error)
                    continue
            local_files[year][combination] = filepath
    return local_files

def load_boundaries():
    """Load and validate Kenya GADM level-2 boundaries."""
    if not GADM_PATH.exists():
        raise FileNotFoundError(f"Missing boundary file: {GADM_PATH}")
    gdf = gpd.read_file(GADM_PATH)
    if len(gdf) != 47:
        LOGGER.warning("Expected 47 counties, found %d", len(gdf))
    if gdf.crs is None:
        raise ValueError("Boundary file has no CRS")
    LOGGER.info("Boundary CRS: %s; counties: %d", gdf.crs, len(gdf))
    return gdf

def aggregate_rasters(local_files, boundaries):
    """Aggregate every available age-sex raster to each county."""
    results = []
    for year, files in local_files.items():
        if not files:
            LOGGER.warning("Skipping year %s because no rasters were downloaded", year)
            continue
        sample_path = next(iter(files.values()))
        with rasterio.open(sample_path) as sample:
            raster_crs = sample.crs
        if raster_crs is None:
            raise ValueError(f"Raster has no CRS: {sample_path}")
        LOGGER.info("%s raster CRS: %s", year, raster_crs)
        year_boundaries = boundaries.to_crs(raster_crs)
        county_data = year_boundaries[["NAME_2", "geometry"]].copy()
        county_data = county_data.rename(columns={"NAME_2": "county"})
        county_data["year"] = year

        for (sex, age), filepath in sorted(files.items()):
            with rasterio.open(filepath) as raster:
                values = zonal_stats(
                    county_data.geometry,
                    filepath,
                    stats="sum",
                    nodata=raster.nodata,
                )
            totals = []
            for result in values:
                total = result.get("sum")
                totals.append(max(float(total), 0.0) if total is not None else 0.0)
            county_data[f"{sex}_{age}"] = totals
        results.append(county_data.drop(columns="geometry"))
    if not results:
        raise RuntimeError("No raster data was available for aggregation")
    return pd.concat(results, ignore_index=True)

def safe_divide(numerator, denominator):
    """Return a percentage-like ratio while avoiding division by zero."""
    return np.divide(numerator, denominator, out=np.zeros(len(numerator)), where=denominator != 0) * 100

def calculate_indicators(df):
    """Calculate the assessment's county-level demographic indicators."""
    male_columns = [f"m_{age}" for age in AGE_GROUPS]
    female_columns = [f"f_{age}" for age in AGE_GROUPS]
    child_columns = [f"{sex}_{age}" for sex in SEXES for age in (0, 1)]
    elderly_columns = [f"{sex}_{age}" for sex in SEXES for age in range(65, 95, 5)]
    working_columns = [f"{sex}_{age}" for sex in SEXES for age in range(15, 65, 5)]

    for column in male_columns + female_columns:
        if column not in df:
            df[column] = 0.0
    df["total_population"] = df[male_columns + female_columns].sum(axis=1)
    df["children_under_5"] = df[child_columns].sum(axis=1)
    df["working_age"] = df[working_columns].sum(axis=1)
    df["elderly_65plus"] = df[elderly_columns].sum(axis=1)
    male_total = df[male_columns].sum(axis=1)
    female_total = df[female_columns].sum(axis=1)
    df["sex_ratio"] = safe_divide(male_total, female_total)
    df["dependency_ratio"] = safe_divide(df["children_under_5"] + df["elderly_65plus"], df["working_age"])
    df["child_dependency_ratio"] = safe_divide(df["children_under_5"], df["working_age"])
    df["elderly_dependency_ratio"] = safe_divide(df["elderly_65plus"], df["working_age"])
    df["pct_children"] = safe_divide(df["children_under_5"], df["total_population"])
    df["pct_elderly"] = safe_divide(df["elderly_65plus"], df["total_population"])
    return df

def generate_figures(df, boundaries, local_files):
    """Write the required time-series and county-size figures."""
    country_totals = df.groupby("year", as_index=False)["total_population"].sum()
    px.line(country_totals, x="year", y="total_population", markers=True,
        title="Kenya Total Population, 2021-2025").write_html(FIGURES_DIR / "population_timeseries.html")
    county_sizes = boundaries.to_crs("EPSG:6933")[ ["NAME_2", "geometry"] ].copy()
    county_sizes["county_size_km2"] = county_sizes.geometry.area / 1_000_000
    latest = df[df["year"] == df["year"].max()].merge(
        county_sizes.drop(columns="geometry"), left_on="county", right_on="NAME_2", how="left"
    )
    px.scatter(latest, x="county_size_km2", y="children_under_5", hover_name="county",
               title="Children Under 5 vs County Size").write_html(FIGURES_DIR / "children_vs_county_size.html")
    raster_path = local_files.get(2025, {}).get(("f", 0))
    if raster_path:
        with rasterio.open(raster_path) as raster:
            scale = max(raster.height // 300, 1)
            raster_values = raster.read(1, out_shape=(1, max(raster.height // scale, 1), max(raster.width // scale, 1)))
        px.imshow(raster_values, title="2025 female age 0 population raster").write_html(
            FIGURES_DIR / "2025_raster_age0_female.html"
        )

def run_pipeline():
    """Execute discovery, download, validation, aggregation, and output generation."""
    boundaries = load_boundaries()
    discovered = discover_raster_urls()
    local_files = download_data(discovered)
    raw_data = aggregate_rasters(local_files, boundaries)
    final_data = calculate_indicators(raw_data)
    final_data.to_csv(OUTPUT_PATH, index=False)
    generate_figures(final_data, boundaries, local_files)
    LOGGER.info("Pipeline complete: %s", OUTPUT_PATH)
    return final_data

if __name__ == "__main__":
    run_pipeline()