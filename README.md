This is a project for the Health Service Modelling Associates (HSMA) programme (cohort 6), by Rey Tan.

The purpose of this discrete event simulation model is to simulate bed occupancy on an acute ward. By providing the option to define various measures such as average length of stay (for both short- and long-stayers), number of beds and proportion of long-stayers, outcomes from changes to these measures can be simulated and presented visually to end users/decision makers.

It has the following features:
1. Patient arrivals are time-dependent. Non-stationary Poisson Process is used in this scenario.
2. Patients are not expected to discharge overnight and are kept on the ward until the next day.
3. Some patients stay on the ward much longer than the average length of stay. The proportion of long-stayers can be customised.
4. Vidigi module is used to animate patient flow.
5. The model is presented on Streamlit for better user experience and customisability.

