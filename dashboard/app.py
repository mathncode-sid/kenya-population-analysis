"""Streamlit dashboard for Kenya county population indicators."""

from pathlib import Path

import geopandas as gpd
import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_DIR / "data" / "processed" / "kenya_population_by_county.csv"
BOUNDARY_PATH = PROJECT_DIR / "data" / "raw" / "gadm41_KEN_2.json"

INDICATORS = {
    "Total Population": "total_population",
    "Children under 5": "children_under_5",
    "Elderly 65+": "elderly_65plus",
    "Dependency Ratio": "dependency_ratio",
    "Sex Ratio": "sex_ratio",
    "Child Dependency Ratio": "child_dependency_ratio",
    "Elderly Dependency Ratio": "elderly_dependency_ratio",
}


@st.cache_data
def load_data():
    """Load the processed county data and GADM boundaries."""
    if not DATA_PATH.exists():
        raise FileNotFoundError("Run the pipeline first to create the processed CSV.")
    return pd.read_csv(DATA_PATH), gpd.read_file(BOUNDARY_PATH)


def build_age_pyramid(data, counties, sex_filter):
    """Create an age distribution chart for the selected counties."""
    selected = data[data["county"].isin(counties)]
    age_columns = [column for column in data.columns if column.startswith(("f_", "m_"))]
    rows = []
    for column in age_columns:
        sex, age = column.split("_")
        if sex_filter != "Total" and sex != sex_filter:
            continue
        rows.append({"age": int(age), "sex": sex.upper(), "population": selected[column].sum()})
    age_data = pd.DataFrame(rows)
    return px.bar(age_data, x="population", y="age", color="sex", orientation="h",
                  barmode="group", title="Population by age group")


st.set_page_config(page_title="Kenya Population Health Dashboard", layout="wide")
st.title("Kenya Population Health Dashboard")
st.caption("County-level age and sex structure for public health planning")

try:
    df, boundaries = load_data()
except FileNotFoundError as error:
    st.error(str(error))
    st.stop()

st.sidebar.header("Filters")
year_filter = st.sidebar.selectbox("Year", sorted(df["year"].unique()), index=len(df["year"].unique()) - 1)
sex_filter = st.sidebar.radio("Sex", ["Total", "Male", "Female"])
indicator_label = st.sidebar.selectbox("Map indicator", list(INDICATORS))
county_options = sorted(df["county"].unique())
county_filter = st.sidebar.multiselect("Counties", county_options)

year_data = df[df["year"] == year_filter].copy()
selected_counties = county_filter or county_options
filtered_data = year_data[year_data["county"].isin(selected_counties)].copy()
indicator = INDICATORS[indicator_label]

total_population = filtered_data["total_population"].sum()
children = filtered_data["children_under_5"].sum()
elderly = filtered_data["elderly_65plus"].sum()
dependency = filtered_data["dependency_ratio"].mean()
sex_ratio = filtered_data["sex_ratio"].mean()
metric_columns = st.columns(5)
metric_columns[0].metric("Population", f"{total_population:,.0f}")
metric_columns[1].metric("Dependency ratio", f"{dependency:.1f}")
metric_columns[2].metric("Children under 5", f"{children:,.0f}")
metric_columns[3].metric("Elderly 65+", f"{elderly:,.0f}")
metric_columns[4].metric("Sex ratio", f"{sex_ratio:.1f}")

map_data = boundaries.merge(year_data, left_on="NAME_2", right_on="county", how="left")
map_data["display_value"] = map_data[indicator]
map_data["hover_text"] = map_data.apply(
    lambda row: f"{row['county']}<br>Population: {row['total_population']:,.0f}<br>Dependency ratio: {row['dependency_ratio']:.1f}",
    axis=1,
)
map_figure = px.choropleth_map(
    map_data,
    geojson=map_data.geometry.__geo_interface__,
    locations=map_data.index,
    color="display_value",
    hover_name="hover_text",
    center={"lat": 0.0236, "lon": 37.9062},
    zoom=4.8,
    color_continuous_scale="RdBu" if "Ratio" in indicator_label else "Viridis",
    labels={"display_value": indicator_label},
)
map_figure.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
st.subheader(f"{indicator_label} by county in {year_filter}")
st.plotly_chart(map_figure, use_container_width=True)

chart_left, chart_right = st.columns(2)
with chart_left:
    st.subheader("County comparison")
    comparison = filtered_data.sort_values(indicator, ascending=False).head(10)
    st.plotly_chart(px.bar(comparison, x="county", y=indicator, title=f"Top counties by {indicator_label}"),
                    use_container_width=True)
with chart_right:
    st.subheader("Age pyramid")
    pyramid = build_age_pyramid(year_data, selected_counties, sex_filter)
    st.plotly_chart(pyramid, use_container_width=True)

st.subheader("Public health interpretation")
st.info(
    "High child populations support prioritizing immunization, pediatric care, and nutrition services. "
    "Higher elderly populations increase demand for chronic disease management and geriatric care. "
    "A high dependency ratio means fewer working-age people support dependents, which can affect household "
    "resources and local health-financing capacity."
)