"""
# =============================================================================
# In this file the FormationFlying model class is defined. 
# Handles agent creation, placement and scheduling.
# =============================================================================
"""

import numpy as np
np.seterr(all='raise')

from mesa import Model
from mesa.space import ContinuousSpace
from mesa.time import SimultaneousActivation
from mesa.datacollection import DataCollector
from mesa.batchrunner import BatchRunner
from .metrics import *
from .parameters import model_params, max_steps, n_iterations, model_reporter_parameters, agent_reporter_parameters, variable_params

from .agents.flight import Flight
from .agents.airports import Airport




class FormationFlying(Model):

    # =========================================================================
    #   Create a new FormationFlying model.
    # 
    #   Args:
    #       n_flights: Number of flights
    #       width, height: Size of the space, in kilometers.
    #       speed: cruise-speed of flights in m/s.
    #       communication_range: How far around should each Boid look for its neighbors
    #       separation: What's the minimum distance each Boid will attempt to
    #                   keep from any other the three drives.
    # =========================================================================
    def __init__(
        self,
        n_flights=2,
        n_origin_airports=2,
        n_destination_airports=2,
        width=1500, # [km]
        height=1500,
        speed=0.220, #[km/second]
        communication_range=1000, #[km]
        departure_window = 3,
        origin_airport_x = [0.0, 0.3], # the origin airports are randomly generated within these boundaries
        origin_airport_y = [0.0, 0.3],
        destination_airport_x = [0.7, 0.9], # same for destination airports
        destination_airport_y = [0.7, 0.9],
        fuel_reduction = 0.75,
        negotiation_method = 1
    ):
        
        # =====================================================================
        #   Initialize parameters, the exact values will be defined later on.
        # =====================================================================

        self.n_flights = n_flights
        self.n_origin_airports = n_origin_airports
        self.n_destination_airports = n_destination_airports
        self.vision = communication_range
        self.speed = speed
        
        # The agents are activated in random order at each step, in a space that
        # has a certain width and height and that is not toroidal 
        # (which means that edges do not wrap around)
        self.schedule = SimultaneousActivation(self)
        self.space = ContinuousSpace(width, height, False) 

        # These are values between [0,1] that limit the boundaries of the 
        # position of the origin- and destination airports.
        self.origin_airport_x = origin_airport_x
        self.origin_airport_y = origin_airport_y
        self.destination_airport_x = destination_airport_x
        self.destination_airport_y = destination_airport_y

        self.destination_agent_list = []
        self.departure_window = departure_window
        self.fuel_reduction = fuel_reduction
        self.negotiation_method = negotiation_method

        self.fuel_savings_closed_deals = 0

        self.total_planned_fuel = 0


        self.new_formation_counter = 0
        self.add_to_formation_counter = 0

        self.total_fuel_consumption = 0
        self.total_flight_time = 0

        self.origin_list = []
        self.destination_list = []

        self.make_airports()
        self.make_agents()
        self.running = True

        self.datacollector = DataCollector(model_reporter_parameters, agent_reporter_parameters)
        
    # =========================================================================
    #  Create all flights, the flights are not all initialized at the same time,
    #  but within a departure window.
    # =========================================================================

    def make_agents(self):

        for i in range(self.n_flights):


            departure_time = self.random.uniform(0, self.departure_window)
            pos = self.random.choice(self.origin_list)
            destination_agent = self.random.choice(self.destination_agent_list)
            destination_pos = destination_agent.pos
            flight = Flight(
                i,
                self,
                pos,
                destination_agent,
                destination_pos,
                departure_time,
                self.speed,
                self.vision,
            )
            self.space.place_agent(flight, pos)
            self.schedule.add(flight)


    # =============================================================================
    #   Create all airports. The option "inactive_airports" gives you the 
    #   opportunity to have airports close later on in the simulation.
    # =============================================================================
    def make_airports(self):

        inactive_airports = 0
        for i in range(self.n_origin_airports):
            x = self.random.uniform(self.origin_airport_x[0], self.origin_airport_x[1]) * self.space.x_max
            y = self.random.uniform(self.origin_airport_y[0], self.origin_airport_y[1]) * self.space.y_max
            closure_time = 0
            pos = np.array((x, y))
            airport = Airport(i + self.n_flights, self, pos, "Origin", closure_time)
            self.space.place_agent(airport, pos)
            self.schedule.add(airport) # they are only plotted if they are part of the schedule

        for i in range(self.n_destination_airports):
            x = self.random.uniform(self.destination_airport_x[0], self.destination_airport_x[1]) * self.space.x_max
            y = self.random.uniform(self.destination_airport_y[0], self.destination_airport_y[1]) * self.space.y_max
            if inactive_airports:
                closure_time = 50
                inactive_airports = 0
            else:
                closure_time = 0
            pos = np.array((x, y))
            airport = Airport(i + self.n_flights + self.n_origin_airports, self, pos, "Destination", closure_time)
            self.space.place_agent(airport, pos)
            self.destination_agent_list.append(airport)
            self.schedule.add(airport) # agents are only plotted if they are part of the schedule


    # =========================================================================
    # Define what happens in the model in each step.
    # =========================================================================
    def step(self):
        all_arrived = True
        total_deal_value = 0
        for agent in self.schedule.agents:
            if type(agent) is Flight:
                total_deal_value += agent.deal_value
                if agent.state != "arrived":
                    all_arrived = False
        if all_arrived:
            self.running = False

        # This is a verification that no deal value is created or lost (total deal value 
        # must be 0, and 0.001 is chosen here to avoid any issues with rounded numbers)
        if abs(total_deal_value) > 0.001:
            raise Exception("Deal value is {}".format(total_deal_value))

        self.schedule.step()
        self.datacollector.collect(self)




