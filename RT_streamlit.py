from RT_vidigi_des_model_classes import Trial, g
from vidigi.animation import animate_activity_log, generate_animation
from vidigi.prep import reshape_for_animations, generate_animation_df

import pandas as pd
import plotly.io as pio
pio.renderers.default = "notebook"

import streamlit as st

st.set_page_config(layout="wide", page_title="Discrete Event Simulation - Beds")
st.title("Acute Ward Bed Occupancy Simulator")
st.write(
    "This discrete event simulator simulates bed occupancy on an acute ward.")
st.write(
    "Please set the simulation parameters on the left.")

with st.sidebar:

    tab1, tab2 = st.tabs(["Basic Parameters", "Advanced Parameters"])

    with tab1:
        st.header("Parameters for simulation:")
        number_of_beds_slider = st.slider("🛏️ Total number of beds in the ward",
                                min_value=5,
                                max_value=30,
                                value=15)
        
        sim_duration_input = st.number_input("📆 How long should the " +
                                        "simulation run for (no. of days)?",
                                        min_value=1,
                                        max_value=14,
                                        value=7)

        number_of_runs_input = st.number_input("📋 How many runs of the "+
                                        "simulation should be done?",
                                        min_value=5,
                                        max_value=50,
                                        value=10)                                        

    with tab2:
        st.header("Advanced parameters for adjustments:")
        mean_LOS_short_slider = st.slider("⏱️ Average length of stay (in " + 
                                        "hours) for each SHORT-stay patient",
                                    min_value=1,
                                    max_value=30,
                                    value=18)

        mean_LOS_long_slider = st.slider("⏱️ Average length of stay (in " + 
                                        "hours) for each LONG-stay patient",
                                    min_value=24,
                                    max_value=60,
                                    value=30)

        long_stay_prob_slider = st.slider("🤒 Percentage of long-stay patients",
                                    min_value=0,
                                    max_value=50,
                                    value=10)       

        # warm_up_period_input = st.number_input("🏃‍♂️ How long (in days) should " +
        #                                     "the system warm up for?",
        #                                     min_value=7,
        #                                     max_value=14,
        #                                     value=14)
        
g.n_beds = number_of_beds_slider
g.bed_short_los_mean = mean_LOS_short_slider
g.bed_long_los_mean = mean_LOS_long_slider
g.long_stay_prob = long_stay_prob_slider / 100
g.sim_duration = sim_duration_input * 24

button_run_pressed = st.button("Run simulation")

if button_run_pressed:
    # Progress spinner
    with st.spinner('Simulating the system...'):

        my_trial = Trial()

        my_trial.run_trial()

        STEP_SNAPSHOT_MAX = 45
        LIMIT_DURATION = g.sim_duration + g.warm_up_period
        WRAP_QUEUES_AT = 15

        full_patient_df = reshape_for_animations(
            event_log=my_trial.all_event_logs[my_trial.all_event_logs['run']==1],
            every_x_time_units=2,
            step_snapshot_max=STEP_SNAPSHOT_MAX,
            limit_duration=LIMIT_DURATION,
            debug_mode=True
            )

        event_position_df = pd.DataFrame([
                    {'event': 'arrival',
                     'x':  50, 'y': 300,
                     'label': "Arrival" },

                    # Triage - minor and trauma
                    {'event': 'bed_wait_begins',
                     'x':  275, 'y': 270,
                     'label': "Waiting for Bed"},

                    {'event': 'bed_occupy_begins',
                     'x':  275, 'y': 75,
                     'resource':'n_beds',
                     'label': "Occupying Bed"},

                    {'event': 'exit',
                     'x':  400, 'y': 5,
                     'label': "Exit"}

                ])
        
        full_patient_df_plus_pos = generate_animation_df(
                                    full_patient_df=full_patient_df,
                                    event_position_df=event_position_df,
                                    wrap_queues_at=WRAP_QUEUES_AT,
                                    step_snapshot_max=STEP_SNAPSHOT_MAX,
                                    gap_between_entities=20,
                                    gap_between_resources=20,
                                    gap_between_rows=30,
                                    debug_mode=True
                                    )
        
        def show_priority_icon(row):
            if "more" not in row["icon"]:
                if row["pathway"] == "long-stay":
                        return "⚠️"
                else:
                    return row["icon"]
            else:
                return row["icon"]
            
        full_patient_df_plus_pos = full_patient_df_plus_pos.assign(
            icon=full_patient_df_plus_pos.apply(show_priority_icon, axis=1)
            )
        
        animate_activity = generate_animation(
            full_patient_df_plus_pos=full_patient_df_plus_pos.sort_values(
                ['patient', 'minute']),
            event_position_df= event_position_df,
            scenario=g(),
            debug_mode=True,
            setup_mode=False,
            include_play_button=True,
            icon_and_text_size=20,
            plotly_height=700,
            frame_duration=800,
            frame_transition_duration=200,
            plotly_width=1200,
            override_x_max=300,
            override_y_max=500,
            time_display_units="dhm",
            display_stage_labels=False,
            gap_between_resources= 20,
            gap_between_rows=30,
            wrap_resources_at=15,
            custom_resource_icon="🛏️",
            add_background_image="https://raw.githubusercontent.com/ReyTan8/Project---DES-Vidigi/1a779553238f51794820f8cb53781e738401f733/resources/ward.drawio.png?token=GHSAT0AAAAAADAW6B5RZPFKM276ATTFFZDQZ7CXB6Q",
        )

        st.write(animate_activity)

