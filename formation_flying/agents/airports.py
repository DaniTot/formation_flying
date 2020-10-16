
'''
# =============================================================================
# In this file the aiport agents are defined. The airports are randomly positioned
# within a specified part of the model. 
# =============================================================================
'''

import numpy as np
from mesa import Agent

class Airport(Agent):
    def __init__(self,
                 unique_id,
                 model,
                 pos,
                 type,
                 closure_time
                 ):

        super().__init__(unique_id, model)
        self.agent_type = "Airport"
        self.pos = np.array(pos)
        self.airport_type = type

        # Performance indicators added because otherwise the metrics give errors.
        self.planned_fuel = 0
        self.estimated_fuel_saved = 0
        self.real_fuel_saved = 0
        self.distance_in_formation = 0
        self.formation_size = 0
        self.planned_flight_time = 0
        self.scheduled_arrival = 0
        # self.estimated_flight_time = 0 #
        # self.estimated_arrival = 0 #
        self.real_flight_time = 0
        self.real_arrival = 0
        self.delay = 0
        self.fuel_consumption = 0   # A counter which counts the fuel consumed
        self.deal_value = 0

        self.closure_time = closure_time
        if type == "Origin":
            self.model.origin_list.append(pos)
        elif type == "Destination":
            self.model.destination_list.append(pos)


    def step(self):
        if self.closure_time != 0:
            if self.model.schedule.steps >= self.closure_time:
                self.airport_type = "Closed"
                # self.model.space.move_agent(self, [0,0])
                print("check")

    # =========================================================================
    #   As we are using a bi-step activation (first a step and then advance), 
    #   the airports-agents need such a function as well.
    # =========================================================================
    def advance(self):
        return
