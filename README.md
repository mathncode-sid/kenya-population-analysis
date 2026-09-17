# Kenya Population and Public Health Analysis

This project downloads WorldPop 1 km age- and sex-structured GeoTIFFs for Kenya (2021-2025), dissolves the raw GADM constituency boundaries into Kenya's 47 counties, aggregates population counts to county level, calculates demographic indicators, and presents the results in a Streamlit dashboard.

The dashboard supports planning for immunization, pediatric and nutrition services, chronic disease management, geriatric care, and health-financing needs.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Place the Kenya boundary file at `data/raw/gadm41_KEN_2.json`. The repository includes the file; GeoTIFFs are cached locally by the pipeline and ignored by Git.

This project also forces rasterio to use its bundled PROJ/GDAL data before reading GeoTIFFs. This avoids conflicts with local PostGIS/PostgreSQL installations that may also provide a PROJ database on Windows.

## Run the pipeline

From the repository root:

```powershell
python src/pipeline.py
```

The pipeline:

- discovers available WorldPop GeoTIFF files by year
- downloads missing rasters to `data/raw/`
- validates the raster filenames and CRS
- dissolves constituency polygons into county boundaries
- aggregates every age/sex raster into county totals
- calculates county-level indicators
- writes output files to `data/processed/` and `outputs/figures/`

Generated outputs include:

- `data/processed/kenya_population_by_county.csv`
- `data/processed/validation_log.txt`
- `outputs/figures/2025_raster_age0_female.html`
- `outputs/figures/population_timeseries.html`
- `outputs/figures/children_vs_county_size.html`

## Run the dashboard

Start the dashboard from the `dashboard` folder so the repo root can be imported correctly:

```powershell
cd dashboard
streamlit run app.py
```

The dashboard includes:

- year and county filters
- sex filter
- indicator selector
- county choropleth map
- summary metric cards
- county comparison chart
- age-pyramid chart
- public-health interpretation text

## Data and assumptions

The source is the WorldPop `Global_2015_2030/R2025A` release, using Kenya's 1 km `1km_ua/constrained` rasters. Age groups `00` and `01` represent the under-five population in this source. Missing age-sex combinations are logged and treated as zero so the pipeline can complete transparently; the validation log records the decision.

The county boundaries are derived from the raw GADM Kenya Level 2 file and dissolved to the 47 Kenya counties used in the analysis.

## Tests

```powershell
python -m pytest
```

The current regression checks cover the filename parser, boundary-load behavior, and the indicator calculations used by the pipeline.
