import os
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import requests

# Redirect Streamlit’s home to a writable temp directory
os.environ["STREAMLIT_HOME"] = "/tmp/.streamlit"
os.makedirs("/tmp/.streamlit", exist_ok=True)

st.set_page_config(
    page_title="California UOI Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("California Urban Opportunity Index (UOI) by County")

# Load data
df = pd.read_csv("./src/california_counties_full.csv")

# Fetch GeoJSON counties
counties = requests.get("https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json").json()
counties["features"] = [feat for feat in counties["features"] if feat.get("id", "").startswith("06")]

# Ensure fips column
if "fips" not in df.columns:
    def fips_lookup(county_name):
        name = county_name.strip().upper()
        for feat in counties["features"]:
            if feat["properties"]["NAME"].upper() == name:
                return feat["properties"]["STATEFP"] + feat["properties"]["COUNTYFP"]
        return None
    df["fips"] = df["County"].apply(fips_lookup)
df["fips"] = df["fips"].astype(str).str.zfill(5)
df["fips"] = df["fips"].apply(lambda x: x if x.startswith("06") else "06" + x[-3:])

# ---- UOI WEIGHTS SIDEBAR ----
st.sidebar.header("⚙️ UOI Weights")
preset = st.sidebar.selectbox("Choose preset…", [
    "Even", "Income-heavy", "Education-heavy", "Equity-focused", "Stability-focused", "Custom"
])

if preset == "Even":
    w = [1/9] * 9
elif preset == "Income-heavy":
    w = [0.4, 0.1, 0.1, 0.1, 0.1, 0.05, 0.05, 0.05, 0.05]
elif preset == "Education-heavy":
    w = [0.1, 0.4, 0.1, 0.1, 0.1, 0.05, 0.05, 0.05, 0.05]
elif preset == "Equity-focused":
    w = [0.05, 0.05, 0.3, 0.05, 0.1, 0.05, 0.2, 0.1, 0.1]
elif preset == "Stability-focused":
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
    "**Normalized weights:**  " +
    f"Income {w_inc:.2f},  " +
    f"Edu {w_bach:.2f},  " +
    f"Unemp {w_unemp:.2f},  " +
    f"Health {w_health:.2f},  " +
    f"Rent {w_rent:.2f},  " +
    f"Broadband {w_bb:.2f},  " +
    f"HS Grad {w_school:.2f},  " +
    f"Mobility {w_mob:.2f},  " +
    f"Gini {w_gini:.2f}"
)

# Add Z-score columns for six variables
for col in [
    "Median_Household_Income",
    "Bachelors_Degree_Pct",
    "Unemployment_Rate",
    "No_Health_Insurance_Pct",
    "Median_Gross_Rent",
    "Broadband_Pct"
]:
    if col not in df.columns:
        continue
    zcol = "Z_" + col
    if col in ["Unemployment_Rate", "No_Health_Insurance_Pct", "Median_Gross_Rent"]:
        df[zcol] = -((df[col] - df[col].mean()) / df[col].std())
    else:
        df[zcol] = (df[col] - df[col].mean()) / df[col].std()

# Add Z-score columns for three additional variables
for col in [
    "High_School_Grad_Pct",
    "Upward_Mobility",
    "Gini_Index"
]:
    if col not in df.columns:
        continue
    zcol = "Z_" + col
    if col in ["Gini_Index"]:
        # For Gini Index, higher values indicate more inequality, so invert
        df[zcol] = -((df[col] - df[col].mean()) / df[col].std())
    else:
        df[zcol] = (df[col] - df[col].mean()) / df[col].std()

# Calculate the weighted UOI
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

# Plot the choropleth map
fig = px.choropleth(
    df,
    geojson=counties,
    locations="fips",
    featureidkey="id",
    color="UOI_custom",
    hover_name="County",
    color_continuous_scale=px.colors.sequential.Viridis,
    color_continuous_midpoint=df["UOI_custom"].mean(),
    scope="usa",
    labels={"UOI_custom": "Urban Opportunity Index"},
    title="California Urban Opportunity Index by County"
)
fig.update_layout(
    margin=dict(l=0, r=0, t=50, b=0),
    font=dict(family='Segoe UI', size=12, color='#000000'),
    title_font=dict(size=24, color='#1f77b4')
)
fig.update_geos(fitbounds="locations", visible=False)
st.plotly_chart(fig, use_container_width=True)

# County details selector
st.header("County Details")
selected = st.selectbox("Select a county:", df["County"].sort_values())
if selected:
    details_df = df[df["County"] == selected][[
        "County",
        "UOI_custom",
        "Median_Household_Income",
        "Bachelors_Degree_Pct",
        "Unemployment_Rate",
        "No_Health_Insurance_Pct",
        "Median_Gross_Rent",
        "Broadband_Pct"
    ]].rename(columns={"UOI_custom": "UOI (custom)"})
    st.table(details_df)

# Regional indicator comparison
st.header("Regional Indicator Comparison")

region_options = {
    "Bay Area": [
        "06001", "06013", "06041", "06055", "06075", "06081", "06085", "06095", "06097"
    ],  # Alameda, Contra Costa, Marin, Napa, San Francisco, San Mateo, Santa Clara, Solano, Sonoma
    "Central Valley": [
        "06007", "06019", "06029", "06031", "06039", "06047", "06053", "06059", "06061", "06063", "06069", "06071", "06073", "06077", "06079"
    ],  # Butte, Fresno, Kern, Kings, Madera, Merced, Placer, Sacramento, San Joaquin, Stanislaus, Sutter, Tulare, Tuolumne, Yolo, Yuba
    "Southern California": [
        "06037", "06065", "06071", "06073", "06079", "06083", "06099", "06107", "06111"
    ],  # Los Angeles, Orange, Riverside, San Bernardino, San Diego, Santa Barbara, Ventura, San Luis Obispo, Imperial
    "Northern California": [
        "06003", "06005", "06009", "06011", "06015", "06017", "06021", "06023", "06025", "06027", "06033", "06035", "06043", "06045", "06049", "06051", "06057", "06067", "06087", "06089", "06091", "06093", "06099", "06101", "06103", "06105"
    ],  # Alpine, Amador, Calaveras, Colusa, Del Norte, El Dorado, Glenn, Humboldt, Imperial, Inyo, Lake, Lassen, Mendocino, Modoc, Mono, Monterey, Nevada, Plumas, San Benito, Shasta, Sierra, Siskiyou, Solano, Sonoma, Stanislaus, Sutter, Tehama
    "Los Angeles Region": ["06037", "06059", "06065", "06071"],
}

indicator_options = [
    "Median_Household_Income",
    "Bachelors_Degree_Pct",
    "Unemployment_Rate",
    "No_Health_Insurance_Pct",
    "Median_Gross_Rent",
    "Broadband_Pct",
    "High_School_Grad_Pct",
    "Upward_Mobility",
    "Gini_Index",
    "UOI_custom"
]

region1 = st.selectbox("Select first region:", list(region_options.keys()), index=0)
region2 = st.selectbox("Select second region:", list(region_options.keys()), index=1)
indicator = st.selectbox("Select indicator:", indicator_options)

def region_mean(region_name, indicator):
    fips_list = region_options[region_name]
    region_df = df[df["fips"].isin(fips_list)]
    return region_df[indicator].mean()

comp_df = pd.DataFrame({
    "Region": [region1, region2],
    indicator: [region_mean(region1, indicator), region_mean(region2, indicator)]
})

fig2 = px.bar(
    comp_df,
    x="Region",
    y=indicator,
    title=f"{indicator} Comparison: {region1} vs {region2}",
    color="Region",
    color_discrete_sequence=px.colors.qualitative.Vivid
)
st.plotly_chart(fig2, use_container_width=True)

# County-to-county comparison
st.header("County-to-County Comparison")

county1 = st.selectbox("Select first county:", df["County"].sort_values(), key="county1")
county2 = st.selectbox("Select second county:", df["County"].sort_values(), key="county2")
# Explicitly use the same full indicator list for county-to-county comparison
indicator_options_county = [
    "Median_Household_Income",
    "Bachelors_Degree_Pct",
    "Unemployment_Rate",
    "No_Health_Insurance_Pct",
    "Median_Gross_Rent",
    "Broadband_Pct",
    "High_School_Grad_Pct",
    "Upward_Mobility",
    "Gini_Index",
    "UOI_custom"
]
indicator2 = st.selectbox("Select indicator for comparison:", indicator_options_county, key="indicator2")

comp_county_df = pd.DataFrame({
    "County": [county1, county2],
    indicator2: [
        df.loc[df["County"] == county1, indicator2].values[0],
        df.loc[df["County"] == county2, indicator2].values[0]
    ]
})

fig3 = px.bar(
    comp_county_df,
    x="County",
    y=indicator2,
    title=f"{indicator2} Comparison: {county1} vs {county2}",
    color="County",
    color_discrete_sequence=px.colors.qualitative.Vivid
)
st.plotly_chart(fig3, use_container_width=True)

# Show raw data table
with st.expander("Show raw data table"):
    st.dataframe(df[[
        "County",
        "Median_Household_Income",
        "Bachelors_Degree_Pct",
        "Unemployment_Rate",
        "No_Health_Insurance_Pct",
        "Median_Gross_Rent",
        "Broadband_Pct",
        "UOI_custom"
    ]])
