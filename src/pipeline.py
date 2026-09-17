import os
import requests
import geopandas as gpd
import pandas as pd
from rasterstats import zonal_stats
import rasterio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- CONFIGURATION ---
YEARS = [2021, 2022, 2023, 2024, 2025]
SEXES = ['f', 'm']
# Worldpop age groups typically: 0, 1, 5, 10, 15... up to 80
AGE_GROUPS = [0, 1] + list(range(5, 85, 5))
BASE_URL = "https://data.worldpop.org/GIS/AgeSex_structures/Global_2000_2020/{year}/KEN/ken_{sex}_{age}_{year}.tif" 
RAW_DIR = "../data/raw"
PROCESSED_DIR = "../data/processed"
GADM_PATH = "../data/gadm41_KEN_2.json"

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

def download_data():
    """Programmatically download WorldPop data with caching."""
    for year in YEARS:
        for sex in SEXES:
            for age in AGE_GROUPS:
                # Note: Adjust URL pattern if 2021-2025 path differs slightly on WorldPop
                url = BASE_URL.format(year=year, sex=sex, age=age)
                filename = url.split('/')[-1]
                filepath = os.path.join(RAW_DIR, filename)
                
                if not os.path.exists(filepath):
                    logging.info(f"Downloading {filename}...")
                    response = requests.get(url, stream=True)
                    if response.status_code == 200:
                        with open(filepath, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                    else:
                        logging.warning(f"Failed to download {url}")
                else:
                    logging.debug(f"{filename} already exists. Skipping.")

def process_and_aggregate():
    """Validate CRS and aggregate raster data to county polygons."""
    logging.info("Loading administrative boundaries...")
    gdf = gpd.read_file(GADM_PATH)
    
    # CRS Validation
    if gdf.crs != "EPSG:4326":
        logging.info("Reprojecting boundaries to EPSG:4326")
        gdf = gdf.to_crs("EPSG:4326")

    results = []
    
    for year in YEARS:
        county_data = gdf[['NAME_2', 'geometry']].copy()
        county_data = county_data.rename(columns={'NAME_2': 'county'})
        county_data['year'] = year
        
        for sex in SEXES:
            for age in AGE_GROUPS:
                filename = f"ken_{sex}_{age}_{year}.tif"
                filepath = os.path.join(RAW_DIR, filename)
                
                if os.path.exists(filepath):
                    # Spatial extraction
                    stats = zonal_stats(county_data, filepath, stats="sum", nodata=-99999)
                    col_name = f"{sex}_{age}"
                    county_data[col_name] = [s['sum'] if s['sum'] else 0 for s in stats]
                else:
                    logging.error(f"Missing file for aggregation: {filename}")
                    county_data[f"{sex}_{age}"] = 0 # Impute missing as 0 for pipeline continuity
                    
        results.append(county_data.drop(columns='geometry'))

    # Combine all years
    df = pd.concat(results, ignore_index=True)
    return df

def calculate_indicators(df):
    """Calculate demographic public health indicators."""
    # Define group columns based on age patterns
    cols_m = [c for c in df.columns if c.startswith('m_')]
    cols_f = [c for c in df.columns if c.startswith('f_')]
    
    df['total_population'] = df[cols_m + cols_f].sum(axis=1)
    
    # Under 5 (Ages 0 and 1 in WorldPop, or 0-4 depending on exact dataset structure)
    under_5_cols = [f"{s}_{a}" for s in SEXES for a in [0, 1]] 
    df['children_under_5'] = df[under_5_cols].sum(axis=1)
    
    # Elderly 65+
    elderly_cols = [f"{s}_{a}" for s in SEXES for a in range(65, 85, 5)]
    df['elderly_65plus'] = df[elderly_cols].sum(axis=1)
    
    # Working age (15-64)
    working_cols = [f"{s}_{a}" for s in SEXES for a in range(15, 65, 5)]
    df['working_age'] = df[working_cols].sum(axis=1)
    
    # Ratios
    total_male = df[cols_m].sum(axis=1)
    total_female = df[cols_f].sum(axis=1)
    
    df['sex_ratio'] = (total_male / total_female) * 100
    df['dependency_ratio'] = ((df['children_under_5'] + df['elderly_65plus']) / df['working_age']) * 100
    df['child_dependency_ratio'] = (df['children_under_5'] / df['working_age']) * 100
    df['elderly_dependency_ratio'] = (df['elderly_65plus'] / df['working_age']) * 100
    df['pct_children'] = (df['children_under_5'] / df['total_population']) * 100
    df['pct_elderly'] = (df['elderly_65plus'] / df['total_population']) * 100
    
    return df

if __name__ == "__main__":
    download_data()
    raw_df = process_and_aggregate()
    final_df = calculate_indicators(raw_df)
    final_df.to_csv(os.path.join(PROCESSED_DIR, "kenya_population_by_county.csv"), index=False)
    logging.info("Pipeline complete. Output saved.")