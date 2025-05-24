import streamlit as st
import pandas as pd
import plotly.express as px
import json
import requests

st.set_page_config(
    page_title="California UOI Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <style>
    /* Global font & background */
    body { font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #f5f5f5; }
    /* Sidebar styling */
    .css-1d391kg { background-color: #ffffff !important; }
    .css-1d391kg .css-1v3fvcr p, .css-1d391kg .css-1v3fvcr h2 {
        color: #0d3b66;
    }
    /* Title styling */
    .css-10trblm e16nr0p31 { font-size: 2.5rem; color: #0d3b66; font-weight: bold; }
    </style>
    """,
    unsafe_allow_html=True
)
st.title("California Urban Opportunity Index (UOI) by County")

# Load up the main CSV for California
df = pd.read_csv("california_counties_full.csv")

# Fetch the official FIPS-based US counties GeoJSON and filter to California (prefix "06")
counties = requests.get(
    "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
).json()
counties["features"] = [
    feat for feat in counties["features"]
    if feat.get("id", "").startswith("06")
]


# Ensure a proper 5-digit FIPS column
if "GEOID" in df.columns:
    df["fips"] = df["GEOID"].astype(str).str.zfill(5)
elif "fips" in df.columns:
    df["fips"] = df["fips"].astype(str).str.zfill(5)
else:
    def fips_lookup(county_name):
        name = county_name.strip().upper()
        for feat in counties["features"]:
            if feat["properties"]["NAME"].upper() == name:
                return feat["properties"]["STATEFP"] + feat["properties"]["COUNTYFP"]
        return None
    df["fips"] = df["County"].apply(fips_lookup)
    df["fips"] = df["fips"].astype(str).str.zfill(5)

# Normalize county-only FIPS to full 5-digit by prepending state code
df["fips"] = df["fips"].apply(lambda x: x if x.startswith("06") else "06" + x[-3:])



# Sidebar: choose preset and set weights for nine factors
st.sidebar.header("⚙️ UOI Weights")
preset = st.sidebar.selectbox("Choose preset…", [
    "Even", "Income-heavy", "Education-heavy",
    "Equity-focused", "Stability-focused", "Custom"
])

if preset == "Even":
    w = [1/9] * 9
elif preset == "Income-heavy":
    w = [0.4, 0.1, 0.1, 0.1, 0.1, 0.05, 0.05, 0.05, 0.05]
elif preset == "Education-heavy":
    w = [0.1, 0.4, 0.1, 0.1, 0.1, 0.05, 0.05, 0.05, 0.05]
elif preset == "Equity-focused":
    # Emphasize low inequality and unemployment
    w = [0.05, 0.05, 0.3, 0.05, 0.1, 0.05, 0.2, 0.1, 0.1]
elif preset == "Stability-focused":
    # Emphasize home stability (rent, homeownership proxy: grad rate) and mobility
    w = [0.05, 0.05, 0.05, 0.05, 0.2, 0.05, 0.1, 0.3, 0.15]
else:
    labels = [
        "Income", "Bachelor’s %", "Unemployment Rate",
        "Uninsured %", "Median Rent", "Broadband %",
        "HS Grad %", "Upward Mobility", "Gini Index"
    ]
    w = [st.sidebar.slider(label, 0.0, 1.0, 1/9) for label in labels]

# Normalize weights
total_w = sum(w)
w = [wi/total_w for wi in w]
w_inc, w_bach, w_unemp, w_health, w_rent, w_bb, w_school, w_mob, w_gini = w

st.sidebar.markdown(
    "**Normalized:** " +
    f"Income {w_inc:.2f}, Edu {w_bach:.2f}, Unemp {w_unemp:.2f}, " +
    f"Health {w_health:.2f}, Rent {w_rent:.2f}, Broadband {w_bb:.2f}, " +
    f"HS Grad {w_school:.2f}, Mobility {w_mob:.2f}, Gini {w_gini:.2f}"
)

# Add Z-score columns if missing
for col in [
    "Median_Household_Income", "Bachelors_Degree_Pct",
    "Unemployment_Rate", "No_Health_Insurance_Pct",
    "Median_Gross_Rent", "Broadband_Pct",
    "High_School_Grad_Pct", "Upward_Mobility", "Gini_Index"
]:
    zcol = "Z_" + col
    if col not in df.columns: 
        continue
    if col in ["Unemployment_Rate", "No_Health_Insurance_Pct", "Median_Gross_Rent", "Gini_Index"]:
        df[zcol] = -((df[col] - df[col].mean()) / df[col].std())
    else:
        df[zcol] = (df[col] - df[col].mean()) / df[col].std()

# Calculate the weighted UOI
# Explicitly invert unemployment weight to ensure high unemployment always reduces UOI
df["UOI_custom"] = (
    df["Z_Median_Household_Income"] * w_inc +
    df["Z_Bachelors_Degree_Pct"]    * w_bach +
    df["Z_Unemployment_Rate"]       * w_unemp +
    df["Z_No_Health_Insurance_Pct"] * w_health +
    df["Z_Median_Gross_Rent"]       * w_rent +
    df["Z_Broadband_Pct"]           * w_bb +
    df["Z_High_School_Grad_Pct"]    * w_school +
    df["Z_Upward_Mobility"]         * w_mob +
    df["Z_Gini_Index"]              * w_gini
)

# Exclude Alpine County (FIPS 06003)
df = df[df["fips"] != "06003"]

# Plot the choropleth map
fig = px.choropleth(
    df,
    geojson=counties,
    locations="fips",
    featureidkey="id",
    color="UOI_custom",
    hover_name="County",
    color_continuous_scale="Viridis",
    labels={"UOI_custom": "Urban Opportunity Index"},
    title="California Urban Opportunity Index by County",
)
fig.update_layout(
    template='plotly_white',
    margin=dict(l=0, r=0, t=50, b=0),
    font=dict(family='Segoe UI', size=12, color='#000000'),
    title_font=dict(size=24, color='#1f77b4')
)
fig.update_geos(
    fitbounds="geojson",
    visible=False,
    projection_type="albers usa"
)
st.plotly_chart(fig, use_container_width=True)

# Dropdown to show selected county data
selected = st.selectbox("Highlight a county:", df["County"].sort_values())
if selected:
    st.write(df[df["County"] == selected][[
        "County",
        "UOI_custom",
        "Median_Household_Income",
        "Bachelors_Degree_Pct",
        "Unemployment_Rate",
        "No_Health_Insurance_Pct",
        "Median_Gross_Rent",
        "Broadband_Pct",
        "High_School_Grad_Pct",
        "Upward_Mobility",
        "Gini_Index"
    ]].rename(columns={"UOI_custom":"UOI (custom)"}))

# Show raw data table
with st.expander("Show raw data table"):
    st.dataframe(df[[
        "County",
        "UOI_custom",
        "Median_Household_Income",
        "Bachelors_Degree_Pct",
        "Unemployment_Rate",
        "No_Health_Insurance_Pct",
        "Median_Gross_Rent",
        "Broadband_Pct",
        "High_School_Grad_Pct",
        "Upward_Mobility",
        "Gini_Index"
    ]])
