import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import os

st.set_page_config(layout="wide", page_title="Kenya Demographics Dashboard")

@st.cache_data
def load_data():
    df = pd.read_csv("data/processed/kenya_population_by_county.csv")
    gdf = gpd.read_file("data/gadm41_KEN_2.json")
    return df, gdf

df, gdf = load_data()

# --- SIDEBAR FILTERS ---
st.sidebar.header("Filters")
year_filter = st.sidebar.selectbox("Year", sorted(df['year'].unique()), index=4)
indicator_filter = st.sidebar.selectbox(
    "Indicator", 
    ["total_population", "children_under_5", "elderly_65plus", "dependency_ratio", "sex_ratio"]
)
county_filter = st.sidebar.multiselect("Select Counties (Compare)", df['county'].unique())

# Filter data
filtered_df = df[df['year'] == year_filter]
if county_filter:
    filtered_df = filtered_df[filtered_df['county'].isin(county_filter)]

# --- HEADER METRICS ---
st.title(f"Kenya Population Health Indicators ({year_filter})")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Population", f"{filtered_df['total_population'].sum():,.0f}")
col2.metric("Avg Dependency Ratio", f"{filtered_df['dependency_ratio'].mean():.1f}")
col3.metric("Total Children <5", f"{filtered_df['children_under_5'].sum():,.0f}")
col4.metric("Total Elderly 65+", f"{filtered_df['elderly_65plus'].sum():,.0f}")

# --- VISUALIZATIONS ---
st.markdown("### Spatial Distribution")

# Merge for mapping
map_data = gdf.merge(filtered_df, left_on="NAME_2", right_on="county")

# Choropleth
fig_map = px.choropleth_mapbox(
    map_data, 
    geojson=map_data.geometry.__geo_interface__, 
    locations=map_data.index, 
    color=indicator_filter,
    hover_name="county",
    mapbox_style="carto-positron",
    center={"lat": 0.0236, "lon": 37.9062},
    zoom=4.5,
    color_continuous_scale="Viridis" if "ratio" not in indicator_filter else "RdBu"
)
fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
st.plotly_chart(fig_map, use_container_width=True)

# Layout for charts
c1, c2 = st.columns(2)

with c1:
    st.markdown("### County Comparison")
    # Bar chart for top/selected counties
    plot_df = filtered_df.sort_values(indicator_filter, ascending=False).head(10)
    fig_bar = px.bar(plot_df, x='county', y=indicator_filter, title=f"Top Counties by {indicator_filter}")
    st.plotly_chart(fig_bar, use_container_width=True)

with c2:
    st.markdown("### Public Health Interpretation")
    st.info("""
    **Understanding the Data for Policy Planning:**
    
    * **High Child Population (<5):** Counties highlighting deep concentrations of under-5s require prioritized funding for routine immunizations, pediatric facilities, and maternal health programs.
    * **High Elderly Population (65+):** Indicates a shift in disease burden toward non-communicable diseases (NCDs). These regions need investment in chronic disease management and geriatric care.
    * **Dependency Ratios:** High dependency ratios signal that the working-age population is carrying a heavy economic burden to support the youth and elderly. This directly impacts local health financing capacity and out-of-pocket expenditure vulnerability.
    """)