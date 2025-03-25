import random
import numpy as np
import pandas as pd
import simpy
from sim_tools.distributions import Exponential, Lognormal
from sim_tools.time_dependent import NSPPThinning
from vidigi.utils import populate_store


# Class to store global parameter values
class g:
    '''
    Time units are in hours

    Parameters:
    -----------
    random_number_set: int, optional (default=DEFAULT_RNG_SET)
        Set to control the initial seeds of each stream of pseudo
        random numbers used in the model.

    n_beds: int
        The number of beds

    bed_short_los_mean: float
        Mean of the bed length of stay distribution (Lognormal) for short-stay

    bed_long_los_mean: float
        Mean of the bed length of stay distribution (Lognormal) for long-stay

    bed_los_var: float
        Variance of the bed length of stay distribution (Lognormal)

    sim_duration: int
        The number of time units the simulation will run for

    number_of_runs: int
        The number of times the simulation will be run with different random
        number streams

    warm_up_period: int
        Duration the simulation should warm up for

    long_stay_prob: float
        Probabality that the patient is a long-stayer             

    '''
    random_number_set = 42

    n_beds = 5
    bed_short_los_mean = 18
    bed_long_los_mean = 30
    bed_los_var = 5

    # Insert hourly arrival rate from csv file into dataframe
    arrivals_df = pd.read_csv(
        "resources/nspp_patient_arrival_mau.csv")
    arrivals_df["arrival_rate"] = arrivals_df['mean_iat'].apply(lambda x: 1/x)
    arrivals_time_dependent_df = arrivals_df

    sim_duration = 600
    number_of_runs = 10
    warm_up_period = 100

    long_stay_prob = 0.1

# Class representing patients coming into the ward.
class Patient:
    '''
    Class defining details for a patient entity
    '''
    def __init__(self, p_id):
        '''
        Constructor method

        Params:
        -----
        identifier: int
            a numeric identifier for the patient.

        arrival: int
            arrival time of patient

        wait_bed: int
            time waiting for a bed

        bed_los: int
            time spent in bed

        total_time: int
            time waiting for a bed + time spent in bed

        pathway_type: str
            indicates whether patient is short- or long-stayer            
                                             
        '''
        self.identifier = p_id
        self.arrival = -np.inf
        self.wait_bed = -np.inf
        self.bed_los = -np.inf
        self.total_time = -np.inf
        self.pathway_type = ''

# Class representing our model of the ward.
class Model:
    '''
    Simulates the simplest ward admission process for a patient

    1. Arrive
    2. Occupies a bed when available
    3. Discharged
    '''
    # Constructor to set up the model for a run.  We pass in a run number when
    # we create a new model.
    def __init__(self, run_number):

        # Create a SimPy environment in which everything will live
        self.env = simpy.Environment()

        self.event_log = []

        # Create a patient counter (which we'll use as a patient ID)
        self.patient_counter = 0

        self.patients = []

        # Create our resources
        self.init_resources()

        # Store the passed in run number
        self.run_number = run_number

        # Create a new Pandas DataFrame that will store some results against
        # the patient ID (which we'll use as the index).
        self.results_df = pd.DataFrame()
        self.results_df["Patient ID"] = [1]
        self.results_df["Queue Time Bed"] = [0.0]
        self.results_df["Length of Stay"] = [0.0]
        self.results_df.set_index("Patient ID", inplace=True)

        # Create an attribute to store the mean queuing times across this run of
        # the model
        self.mean_q_time_bed = 0

        # Arrivals distribution using NSPP Thinning Method
        self.arrivals_dist = NSPPThinning(
          data=g.arrivals_time_dependent_df,
          random_seed1 = run_number * 42,
          random_seed2 = run_number * 88
        )

        # Distribution of short LOS
        self.bed_short_los_dist = Lognormal(mean = g.bed_short_los_mean,
            stdev = g.bed_los_var,
            random_seed = self.run_number*g.random_number_set)
        
        # Distribution of long LOS
        self.bed_long_los_dist = Lognormal(mean = g.bed_long_los_mean,
            stdev = g.bed_los_var,
            random_seed = self.run_number*g.random_number_set)

    def init_resources(self):
        '''
        Init the number of resources
        and store in the arguments container object

        Resource list:
            1. Beds

        '''
        self.beds = simpy.Store(self.env)

        populate_store(num_resources=g.n_beds,
                       simpy_store=self.beds,
                       sim_env=self.env)

        # for i in range(g.n_beds):
        #     self.beds.put(
        #         CustomResource(
        #             self.env,
        #             capacity=1,
        #             id_attribute = i+1)
        #         )

    # A generator function that represents the DES generator for patient
    # arrivals
    def generator_patient_arrivals(self):

        while True:
            # Increment the patient counter by 1
            self.patient_counter += 1

            # Create a new patient, using patient_counter as patient ID
            p = Patient(self.patient_counter)

            # Store patient in list
            self.patients.append(p)

            # Tell SimPy to start up the occupy_bed generator function with
            # this patient
            self.env.process(self.occupy_bed(p))

            # Randomly sample the time to the next patient arriving
            sampled_inter = self.arrivals_dist.sample(
                simulation_time=self.env.now)

            # Freeze this instance of this function in place until the
            # inter-arrival time we sampled above has elapsed.
            yield self.env.timeout(sampled_inter)

    # A generator function that represents the pathway for a patient going
    # through the ward.

    def occupy_bed(self, patient):

        # to determine whether patient is a long stayer or not
        if random.uniform(0,1) > g.long_stay_prob:
            # short stay patient
            # sample bed los duration
            self.bed_los = self.bed_short_los_dist.sample()
            patient.pathway_type = 'short-stay'
        
        else:
            # long stay patient
            # sample bed los duration
            self.bed_los = self.bed_long_los_dist.sample()
            patient.pathway_type = 'long-stay'

        self.arrival = self.env.now

        # record patient arrival
        self.event_log.append(
            {'patient': patient.identifier,
             'pathway': patient.pathway_type,
             'event_type': 'arrival_departure',
             'event': 'arrival',
             'time': self.env.now}
        )

        # request examination resource
        start_wait = self.env.now

        # record time patient starts to wait for bed
        self.event_log.append(
            {'patient': patient.identifier,
             'pathway': patient.pathway_type,
             'event': 'bed_wait_begins',
             'event_type': 'queue',
             'time': self.env.now}
        )

        # Seize a bed resource when available
        bed_resource = yield self.beds.get()

        # record the waiting time for bed
        self.wait_bed = self.env.now - start_wait
        self.results_df.at[patient.identifier, "Queue Time Bed"] = (
            self.wait_bed)
        
        # record time patient starts to occupy bed
        self.event_log.append(
            {'patient': patient.identifier,
                'pathway': patient.pathway_type,
                'event': 'bed_occupy_begins',
                'event_type': 'resource_use',
                'time': self.env.now,
                'resource_id': bed_resource.id_attribute
                }
        )

        # To block overnight discharge, if end of stay falls between 8pm and 8am 
        # then extend stay until after 8am, and add between 2 and 5 hours
        # after 8am

        if (((self.env.now + self.bed_los)) % 24) >= 12:
            
            after_hours_end_time = self.env.now + self.bed_los

            self.bed_los = self.bed_los + (
                24-((self.env.now + self.bed_los) % 24)) + (
                    random.uniform(2.0, 5.0))
            
            # For patients staying overnight, record original end time before
            # LOS extension
            self.event_log.append(
            {'patient': patient.identifier,
                'pathway': patient.pathway_type,
                'event': 'overnight_stay',
                'event_type': 'overnight_log',
                'time': after_hours_end_time,
                'resource_id': bed_resource.id_attribute}
            )
        
        self.results_df.at[patient.identifier, "Length of Stay"] = (
            self.bed_los)

        yield self.env.timeout(self.bed_los)

        self.event_log.append(
            {'patient': patient.identifier,
                'pathway': patient.pathway_type,
                'event': 'bed_occupy_complete',
                'event_type': 'resource_use_end',
                'time': self.env.now,
                'resource_id': bed_resource.id_attribute}
        )

        # Resource is no longer in use, release
        self.beds.put(bed_resource)

        # total time in system
        self.total_time = self.env.now - self.arrival

        # record patient departure from ward
        self.event_log.append(
            {'patient': patient.identifier,
            'pathway': patient.pathway_type,
            'event': 'depart',
            'event_type': 'arrival_departure',
            'time': self.env.now}
        )


    # This method calculates results over a single run.  Here we just calculate
    # a mean, but in real world models you'd probably want to calculate more.
    def calculate_run_results(self):
        # Take the mean of the queuing times across patients in this run of the
        # model.
        self.mean_q_time_bed = self.results_df["Queue Time Bed"].mean()
        self.mean_los = self.results_df["Length of Stay"].mean()

    # The run method starts up the DES entity generators, runs the simulation,
    # and in turns calls anything we need to generate results for the run
    def run(self):
        # Start up DES entity generator that creates new patients
        self.env.process(self.generator_patient_arrivals())

        # Run the model for the duration specified in g class, including a warm-
        # up period
        self.env.run(until=g.sim_duration + g.warm_up_period)

        # Now the simulation run has finished, call the method that calculates
        # run results
        self.calculate_run_results()

        self.event_log = pd.DataFrame(self.event_log)

        self.event_log["run"] = self.run_number

        return {'results': self.results_df, 'event_log': self.event_log}

# Class representing a Trial for our simulation - a batch of simulation runs.
class Trial:
    # The constructor sets up a pandas dataframe that will store the key
    # results from each run against run number, with run number as the index.
    def  __init__(self):
        self.df_trial_results = pd.DataFrame()
        self.df_trial_results["Run Number"] = [0]
        self.df_trial_results["Arrivals"] = [0]
        self.df_trial_results["Mean Queue Time Bed"] = [0.0]
        self.df_trial_results.set_index("Run Number", inplace=True)

        self.all_event_logs = []

    # Method to run a trial
    def run_trial(self):
        print(f"{g.n_beds} beds")
        print("") ## Print a blank line

        # Run the simulation for the number of runs specified in g class.
        # For each run, we create a new instance of the Model class and call its
        # run method, which sets everything else in motion.  Once the run has
        # completed, we grab out the stored run results (just mean queuing time
        # here) and store it against the run number in the trial results
        # dataframe.
        for run in range(g.number_of_runs):
            random.seed(run)

            my_model = Model(run)
            model_outputs = my_model.run()
            patient_level_results = model_outputs["results"]
            event_log = model_outputs["event_log"]

            self.df_trial_results.loc[run] = [
                len(patient_level_results),
                my_model.mean_q_time_bed,
            ]
            #print(self.df_trial_results)
            #print(event_log)

            self.all_event_logs.append(event_log)

        self.all_event_logs = pd.concat(self.all_event_logs)
