import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime, timedelta
import time
import pytz

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Solar Energy Tracker",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

IST = pytz.timezone('Asia/Kolkata')
datetime.now(IST)

# --- 1. MOCK DATA GENERATION (REPLACE THIS) ---
def generate_mock_data():
    """Generates a mock DataFrame representing historical solar data."""
    
    # Generate 48 hours of data, one row per hour
    num_hours = 48
    end_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    timestamps = [end_time - timedelta(hours=i) for i in range(num_hours)][::-1]

    # Cumulative energy starts at 1000 and increases
    cumulative_base = 1000
    cumulative_series = cumulative_base + np.cumsum(np.random.rand(num_hours) * 10)
    
    # Energy generated in last hour (random during the day, 0 at night)
    hourly_energy = np.where(
        (np.array([t.hour for t in timestamps]) > 7) & 
        (np.array([t.hour for t in timestamps]) < 19), 
        np.random.rand(num_hours) * 500 + 200, 
        np.random.rand(num_hours) * 50
    )
    
    df = pd.DataFrame({
        'Timestamp': timestamps,
        'Cumulative Energy (kWh)': cumulative_series,
        'Energy Generated in Last Hour (Wh)': hourly_energy
    })
    
    return df.sort_values('Timestamp').reset_index(drop=True)


# --- 2. DATA LOADING & CACHING (THIS IS WHERE YOU CONNECT TO GOOGLE SHEETS) ---
@st.cache_data(ttl=60)  # Refresh data every 60 seconds
def load_data():
    """
    Loads data from your source. Replace the contents of this function 
    with your actual Google Sheet reading logic.

    We use st.cache_data(ttl=60) to ensure the data refreshes automatically 
    every minute without blocking the app.
    """
    
    # =========================================================================
    # !!! IMPORTANT: REPLACE THIS MOCK CALL WITH YOUR REAL GOOGLE SHEET LOGIC !!!
    # e.g., using st.experimental_connection('gsheets', type='sheets') or gspread.
    # The output MUST be a Pandas DataFrame with the columns:
    # 'Timestamp', 'Cumulative Energy (kWh)', 'Energy Generated in Last Hour (Wh)'
    # =========================================================================
    
    data = generate_mock_data()
    
    # Ensure Timestamp is datetime object
    data['Timestamp'] = pd.to_datetime(data['Timestamp'])
    
    # Sort and return the data
    return data.sort_values(by='Timestamp', ascending=True).reset_index(drop=True)


# --- 3. MAIN APPLICATION ---
def app_main():
    # --- ADD STATIC BACKDROP & ACCENTS VIA CSS INJECTION ---
    # This block handles the background and some basic styling
    st.markdown("""
        <style>
        /* 1. Static Backdrop / Background Color */
        /* Change this URL to your image path or use a solid color like #f0f2f6 */
        .stApp {
            background-color: #f0f2f6; /* Light gray background color for a clean look */
            /* Optional: Uncomment below to use a background image */
            /*
            background-image: url("https://placehold.co/1920x1080/00FF7F/white?text=Solar+Panel+Background");
            background-size: cover;
            background-attachment: fixed;
            */
        }
        
        /* 2. Color Accents: Styling the main content block for better visibility */
        /* Targets the main content area */
        .main .block-container {
            padding-top: 2rem;
            padding-right: 3rem;
            padding-left: 3rem;
            padding-bottom: 2rem;
        }

        /* 3. Accent for Metrics (styling for clearer cards) */
        /* Adding a subtle border/shadow/accent border to st.metric containers */
        [data-testid="stMetric"] {
            background-color: white;
            padding: 15px 20px;
            border-radius: 10px;
            border-left: 5px solid #FFD700; /* Gold accent border matching 'Day' color */
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
            transition: all 0.3s ease;
        }
        
        [data-testid="stMetric"]:hover {
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
        }
        
        /* 4. Customizing Metric Values for accent color */
        /* Targets the main metric value */
        [data-testid="stMetricValue"] {
            color: #FFD700; /* Use Gold/Solar color as an accent */
            font-size: 2.5rem;
        }

        </style>
        """, unsafe_allow_html=True)
    # --- END CSS INJECTION ---
    
    # --- HEADER with Logo and Title ---
    header_col1, header_col2 = st.columns([1, 4]) # Adjust column ratios as needed for logo size
    
    with header_col1:
        # Assuming 'image.png' is in the same directory as your app.py
        # You might need to adjust width for your specific logo size
        st.image("futrbuilds logo-07.png", width=250) 
        
    with header_col2:
        st.title("☀️ Live Solar Panel Dashboard")

    st.markdown("---") # Separator

    # Load data using the cached function (refreshes every minute)
    df_raw = load_data()
    
    # Get the latest row for KPIs
    latest_row = df_raw.iloc[-1]
    
    # Calculate the time window for the chart
    time_24hrs_ago = datetime.now() - timedelta(hours=24)
    # Filter and create new columns needed for visualization
    df_24hrs = df_raw[df_raw['Timestamp'] >= time_24hrs_ago].copy()
    
    # --- ADD TIME OF DAY FOR HUE ---
    # Day is defined as 7 AM (hour 7) up to 7 PM (hour 18)
    df_24hrs['Hour'] = df_24hrs['Timestamp'].dt.hour
    df_24hrs['Time of Day'] = np.where(
        (df_24hrs['Hour'] >= 7) & (df_24hrs['Hour'] < 19),
        'Day (Generating)',
        'Night (Low/Zero)'
    )
    # --- END TIME OF DAY LOGIC ---
    
    # Calculate the current time string once for the caption
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    # --- Layout for Metrics and Chart ---
    # Create three columns: 1 for cumulative, 1 for hourly, and 2 for the chart
    # Adjust ratios: [1, 1, 2]
    col_cumulative, col_hourly, col_chart = st.columns([1, 1, 2])
    
    with col_cumulative:
        st.subheader("Current Metrics")
        # Display Cumulative Energy
        cumulative_energy = latest_row['Cumulative Energy (kWh)']
        st.metric(
            label="Cumulative Energy (Total)",
            value=f"{cumulative_energy:,.2f} kWh",
            delta=None
        )

    with col_hourly:
        st.subheader("") # Empty subheader to align vertically
        # Display Energy Generated in Last Hour
        hourly_energy = latest_row['Energy Generated in Last Hour (Wh)']
        # Calculate hourly delta based on previous hour's generation
        if len(df_raw) > 1:
            prev_hourly_energy = df_raw.iloc[-2]['Energy Generated in Last Hour (Wh)']
            delta = hourly_energy - prev_hourly_energy
            delta_str = f"{delta:,.0f} Wh"
        else:
            delta_str = None
            
        st.metric(
            label="Energy Generated in Last Hour",
            value=f"{hourly_energy:,.0f} Wh",
            delta=delta_str,
            delta_color="inverse" 
        )

    with col_chart:
        st.subheader("24-Hour Generation Trend")
        if df_24hrs.empty:
            st.warning("Not enough data to display the last 24 hours trend.")
            
        else:
            # Base chart definition
            base = alt.Chart(df_24hrs).encode(
                x=alt.X('Timestamp', axis=alt.Axis(title='Time', format='%H:%M')),
                y=alt.Y('Energy Generated in Last Hour (Wh)', title='Energy (Wh)'),
                tooltip=[
                    alt.Tooltip('Timestamp', format='%Y-%m-%d %H:%M'),
                    alt.Tooltip('Energy Generated in Last Hour (Wh)', format='.2f'),
                    'Time of Day'
                ]
            ).properties(
                height=300
            )
            
            # Layer 1: Continuous Line (Base layer, usually dark color)
            # This ensures the line never breaks
            continuous_line = base.mark_line(color='#A0A0A0', size=1.5).interactive()
            
            # Layer 2: Points with Conditional Color
            # This layer adds the colored dots and provides the legend
            color_points = base.mark_point(filled=True, size=50).encode(
                color=alt.Color('Time of Day', 
                                scale=alt.Scale(domain=['Day (Generating)', 'Night (Low/Zero)'], 
                                                range=['#FFD700', '#1E90FF']), # Gold for Day, Dodger Blue for Night
                                legend=alt.Legend(title="Period"))
            )
            
            chart = (continuous_line + color_points).resolve_scale(color='independent')
            
            st.altair_chart(chart, use_container_width=True)
            
            # ADDED: Last data update under the graph in small text
            st.caption(f"Last System Refresh: {current_time_str} (Data TTL: 60s)")




if __name__ == "__main__":
    app_main()

