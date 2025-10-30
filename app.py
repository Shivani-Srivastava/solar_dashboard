import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import timedelta
import time
import pytz 
import datetime

# --- 1. Constants and Configuration ---
IST = 'Asia/Kolkata'
CAPACITY_KWP = 1.3  # kWp Installed capacity
BATTERY_CAPACITY_KWH = 7.2 # Max Capacity in kWh (150Ah * 48V / 1000)
MIN_BATTERY_KWH = 1.44 # Minimum state of charge (80% DOD)

# --- 2. Data Loading and Caching ---

@st.cache_data
def load_pvgis_data():
    """
    Loads, preprocesses, and simulates the entire solar energy profile 
    based on the PVGIS data, ensuring the data is timezone-aware (IST).
    """

    try:
        # Load the raw PVGIS data
        # FIX: Removed skiprows (file starts with header) and added explicit date_parser
        pvgis_df = pd.read_csv(
            'pvgis_azimuth90.csv', 
            header=0, 
            index_col=0, 
            parse_dates=True,
            date_parser=lambda x: pd.to_datetime(x, format='%Y%m%d:%H%M') 
        )
        pvgis_df.index.name = 'time'
           
        # PVGIS is typically published in UTC. Localize to UTC, then convert to IST.
        # FIX: Changed invalid nonexistent='shift' to nonexistent='NaT'
        pvgis_df = pvgis_df.tz_localize('UTC', nonexistent='NaT', ambiguous='NaT').tz_convert(IST)

        # Calculate Total Incident Irradiance (G_total) in W/m^2
        pvgis_df['G_total (W/m^2)'] = pvgis_df[['Gb(i)', 'Gd(i)', 'Gr(i)']].sum(axis=1)
        pvgis_df['Hourly Irradiance (kW/m^2)'] = pvgis_df['G_total (W/m^2)'] / 1000.0

        # Create unique hourly mapping profile using DayOfYear and Hour
        pvgis_profile = pvgis_df.groupby([pvgis_df.index.dayofyear, pvgis_df.index.hour])['Hourly Irradiance (kW/m^2)'].mean()
        pvgis_profile.index.names = ['DayOfYear', 'Hour']

        # --- 3. Full Simulation Setup (Same as Canvas) ---
        START_DATE = '2025-10-30 00:00:00'
        END_DATE = '2026-05-31 23:00:00'
           
        # Create simulation DataFrame and localize the index to IST
        df = pd.DataFrame(index=pd.to_datetime(pd.date_range(start=START_DATE, end=END_DATE, freq='H'))).tz_localize(IST)
        df.index.name = 'TimeStamp'

        # Map Irradiance Profile using vectorized reindex
        map_index = pd.MultiIndex.from_arrays([df.index.dayofyear, df.index.hour], names=['DayOfYear', 'Hour'])
        df['Hourly Irradiance (kW/m^2)'] = pvgis_profile.reindex(map_index, fill_value=0.0).values

        # Energy Generation
        df['Energy Generated (kWh)'] = (df['Hourly Irradiance (kW/m^2)'] * CAPACITY_KWP * 0.18).clip(lower=0)

        # Load Consumption (4 PM to 8:30 PM = 16 to 20:59:59)
        LOAD_KW = 0.3
        load_hours = df.index.hour
        load_conditions = (load_hours >= 16) & (load_hours < 20)
        load_conditions_partial = (load_hours == 20)

        df['Load Consumption (kWh)'] = 0.0
        df.loc[load_conditions, 'Load Consumption (kWh)'] = LOAD_KW
        df.loc[load_conditions_partial, 'Load Consumption (kWh)'] = LOAD_KW * 0.5
           
        # Battery Simulation (Logic from Canvas)
        INITIAL_BATTERY_LEVEL = BATTERY_CAPACITY_KWH
        battery_level = [INITIAL_BATTERY_LEVEL]
        power_flow = []

        for i in range(len(df) - 1):
            current_level = battery_level[-1]
            generation = df.iloc[i]['Energy Generated (kWh)']
            load = df.iloc[i]['Load Consumption (kWh)']
               
            net_energy = generation - load
            battery_change = net_energy
            new_level = current_level + battery_change
               
            if new_level > BATTERY_CAPACITY_KWH:
                excess = new_level - BATTERY_CAPACITY_KWH
                new_level = BATTERY_CAPACITY_KWH
                battery_change -= excess  
            elif new_level < MIN_BATTERY_KWH:
                deficit = MIN_BATTERY_KWH - new_level
                new_level = MIN_BATTERY_KWH
                battery_change += deficit
                   
            battery_level.append(new_level)
            power_flow.append(battery_change)

        df['Battery Level (kWh)'] = battery_level
        df['Battery Power Flow (kWh)'] = power_flow + [0.0]
           
        df['Is Charging'] = df['Battery Power Flow (kWh)'] > 0.01
        df['Is Using Battery'] = df['Battery Power Flow (kWh)'] < -0.01
           
        return df
           
    except Exception as e:
        st.error(f"Error during data loading or simulation: {e}")
        return pd.DataFrame()

# --- 4. Main Streamlit Application ---

def main():
    # MUST BE THE FIRST STREAMLIT COMMAND
    st.set_page_config(layout="wide", page_title="Solar Energy Tracker")

# --- CSS INJECTION BLOCK (Background Image with Opacity) ---
    # !!! IMPORTANT: REPLACE THIS PLACEHOLDER with your jsDelivr CDN link !!!
    GITHUB_CDN_IMAGE_URL = "https://cdn.jsdelivr.net/gh/Shivani-Srivastava/solar_dashboard@main/e35ce8331760fd3dbd7fd9c41aae7c5c.jpg"
    
    st.markdown(f"""
        <style>
        /* 1. Static Backdrop / Background Image with Opacity */
        .stApp {{
            /* Overlay a 40% opaque light gray color over the image to achieve 60% opacity */
            background: linear-gradient(
                rgba(240, 242, 246, 0.4), 
                rgba(240, 242, 246, 0.4)
            ), 
            url("{GITHUB_CDN_IMAGE_URL}"); 
            
            background-size: cover; 
            background-attachment: fixed;
        }}
           
        /* 2. Color Accents: Styling the main content block for better visibility */
        .main .block-container {{
            padding-top: 2rem;
            padding-right: 3rem;
            padding-left: 3rem;
            padding-bottom: 2rem;
        }}

        /* 3. Accent for Metrics (using gold color for solar theme) */
        [data-testid="stMetric"] {{
            background-color: white; 
            padding: 15px 20px;
            border-radius: 10px;
            border-left: 5px solid #FFD700; 
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
            transition: all 0.3s ease;
        }}
           
        [data-testid="stMetric"]:hover {{
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
        }}
           
        /* 4. Customizing Metric Values for accent color */
        [data-testid="stMetricValue"] {{
            color: #FFD700; 
            font-size: 2.5rem;
        }}

        </style>
        """, unsafe_allow_html=True)
    # --- END CSS INJECTION ---
    # --- END CSS INJECTION ---
       
    # --- HEADER with Logo and Title ---
    header_col1, header_col2 = st.columns([1, 4]) 
       
    with header_col1:
        # NOTE: Ensure 'futrbuilds logo-07.png' is accessible by your Streamlit app
        st.image("futrbuilds logo-07.png", width=250) 
           
    with header_col2:
        st.title("☀️ Solar Energy Tracking")
    
    st.markdown("---")
       
    # --- REAL-TIME CLOCK SETUP ---
    # 1. Get current time in IST
    ist_tz = pytz.timezone(IST)
    now_ist = datetime.datetime.now(ist_tz)
       
    # 2. Find the index in the simulation data that is closest to the current IST hour
    current_time_dt = now_ist.replace(minute=0, second=0, microsecond=0)
       
    df = load_pvgis_data()
           
    if df.empty:
        st.stop()

    # Find the index of the closest hour in the simulation data (Backward-compatible fix)
    # Check if the current hour is outside the simulation range
    if current_time_dt < df.index[0] or current_time_dt > df.index[-1]:
        # Handle outside range (before start or after end)
        if current_time_dt < df.index[0]:
            current_time_index = 0
        else: # current_time_dt > df.index[-1]
            current_time_index = len(df) - 1
            
        current_time_dt = df.index[current_time_index] # Update to the boundary time
        st.warning(f"Current time ({now_ist.strftime('%d %b %Y, %H:%M %Z')}) is outside the installation range. Displaying data for the boundary hour: {current_time_dt.strftime('%d %b %Y, %H:%M %Z')}")

    else:
        # Backward-compatible implementation of method='nearest'
        # Find the index label that is closest to the target datetime
        closest_index_label = (df.index.to_series() - current_time_dt).abs().idxmin()
        
        # Get the integer position using the label
        current_time_index = df.index.get_loc(closest_index_label)
        current_time_dt = df.index[current_time_index] # Ensure current_time_dt matches the index time
        
    st.subheader(f"Current System Snapshot: {now_ist.strftime('%d %b %Y, %H:%M:%S %Z')} (Data shown for the hour ending at: {current_time_dt.strftime('%H:%M %Z')})")
       
    # --- KPI Calculation and Display (Metrics) ---
    current_row = df.iloc[current_time_index]
    
    # Calculate KPIs
    past_hour_generation = current_row['Energy Generated (kWh)']
    start_day = current_time_dt - timedelta(hours=23)
    past_day_df = df.loc[start_day:current_time_dt]
    past_day_generation = past_day_df['Energy Generated (kWh)'].sum()
    
    is_charging = current_row['Is Charging']
    is_using = current_row['Is Using Battery']
    battery_status_text = "Charging" if is_charging else ("Discharging" if is_using else "Idle")
    battery_status_color = "green" if is_charging else ("red" if is_using else "blue")
       
    # Display 4 Metrics in a row
    col1, col2, col3, col4 = st.columns(4)
       
    with col1:
        st.metric(
            label="Installed Capacity", 
            value=f"{CAPACITY_KWP:.1f} kWp", 
            delta="Fixed"
        )
           
    with col2:
        st.metric(
            label="Energy Generated (Past Hour)", 
            value=f"{past_hour_generation:.3f} kWh",
            delta=f"{past_hour_generation * 1000:.0f} Wh"
        )
           
    with col3:
        st.metric(
            label="Energy Generated (Past 24H)", 
            value=f"{past_day_generation:.2f} kWh",
            delta=f"{past_day_generation:.2f} kWh TTD"
        )
           
    with col4:
        st.markdown(f"**Battery Status**")
        st.markdown(f"<h3 style='color:{battery_status_color};'>{battery_status_text}</h3>", unsafe_allow_html=True)
           
    # --- Battery Level KPI (Below the main metrics) ---
    st.markdown("<br>", unsafe_allow_html=True) # Add some spacing
    battery_col, _, _ = st.columns([1, 1, 1])
    with battery_col:
        current_battery_level = current_row['Battery Level (kWh)']
        battery_soc_percent = (current_battery_level / BATTERY_CAPACITY_KWH) * 100
           
        st.metric(
            label="Current Battery Level (State of Charge)", 
            value=f"{current_battery_level:.2f} kWh", 
            delta=f"{battery_soc_percent:.1f}% SOC"
        )
        st.progress(battery_soc_percent / 100)


    st.markdown("---")

    # --- Line Chart (Past 48 Hours Lookback) ---
    st.subheader("Energy Flow (Generation, Load, and Battery Interaction) - Last 48 Hours")
       
    # Define lookback period
    lookback_hours = 48
    start_plot_time = current_time_dt - timedelta(hours=lookback_hours - 1) 
       
    # Ensure plot data only goes up to the current simulated time
    plot_df = df.loc[start_plot_time:current_time_dt].copy()
       
    # Prepare data for plotting
    plot_data = plot_df[[
        'Energy Generated (kWh)', 
        'Load Consumption (kWh)', 
        'Battery Power Flow (kWh)'
    ]]
       
    st.line_chart(plot_data)
       
    st.markdown(
        """
        *Note: The **Battery Power Flow** line shows the net energy (kWh) absorbed 
        by the battery (positive values = charging from excess solar) or delivered 
        by the battery (negative values = discharging to meet load).*
        """
    )
    
    # --- Auto-Refresh Logic ---
    st.markdown("---")
    st.info("Dashboard is automatically refreshing every 15 minutes to show the latest data.")
    
    # Sleep for 15 minutes (900 seconds) and then automatically rerun the script
    time.sleep(900)
    st.rerun()


if __name__ == "__main__":
    main()
