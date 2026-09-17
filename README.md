# Kenya Population and Public Health Analysis

This project processes WorldPop 1 km age- and sex-structured GeoTIFFs for Kenya (2021-2025), aggregates them to all 47 GADM level-2 counties, calculates demographic indicators, and presents the results in a Streamlit dashboard.

The indicators support planning for immunization, pediatric and nutrition services, chronic disease management, geriatric care, and health-financing needs.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Place `gadm41_KEN_2.json` in `data/raw/`. The repository includes the boundary file; GeoTIFFs are cached locally by the pipeline and ignored by Git.

## Usage

Run from the repository root:

```powershell
python src/pipeline.py
streamlit run dashboard/app.py
```

The pipeline discovers available files from the WorldPop Kenya directory, caches downloads, validates filenames and CRS, logs missing combinations and non-positive values, aggregates each age-sex raster to counties, and writes:

- `data/processed/kenya_population_by_county.csv`
- `data/processed/validation_log.txt`
- `outputs/figures/2025_raster_age0_female.html`
- `outputs/figures/population_timeseries.html`
- `outputs/figures/children_vs_county_size.html`

The dashboard provides year, county, sex, and indicator filters; a county choropleth; summary cards; a county comparison chart; an age-pyramid chart; and public-health interpretation.

## Data and assumptions

The source is the WorldPop `Global_2015_2030/R2025A` release, using Kenya's `1km_ua/constrained` rasters. Age groups `00` and `01` represent the under-five population in this source. Missing age-sex combinations are logged and treated as zero for that combination so the pipeline can complete transparently; the validation log records the decision.

## Tests

```powershell
python -m pytest
```
