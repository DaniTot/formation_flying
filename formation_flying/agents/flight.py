'''
# =============================================================================
#    In this file the Flight-styleagent is defined.
#
#    Flights have a communication_range that defines the radius in which they 
#    look for their neighbors to negotiate with. They negotiate who to form a 
#    formation with in order to save fuel.  
#    
#    Different negotiation methods can be applied. In the parameter files one 
#    can set 'negototiation_method' which defines which method will be used. 
#    The base model only includes the greedy algorithm.
#
# =============================================================================
'''

import numpy as np
from random import choices
from matplotlib import pyplot as plt

from mesa import Agent
from .airports import Airport
from ..negotiations.greedy import do_greedy
from ..negotiations.CNP import CNP
from ..negotiations.english import English
from ..negotiations.vickrey import Vickrey
from ..miscellaneous import calc_distance, utility_function, calc_angle, calc_middle_point, calc_vector
from ..negotiations.japanese import Japanese
from ..miscellaneous import calc_distance, utility_function, calc_middle_point

import math


class Flight(Agent):


    # =========================================================================
    # Create a new Flight agent.
    #
    # Args:
    #     unique_id: Unique agent identifier.
    #     pos: Starting position
    #     destination: the position of the destination
    #     destination_agent: the agent of the destination airport
    #     speed: Distance to move per step.
    #     departure_time: step of the model at which the flight should depart its origin
    #
    #     heading: numpy vector for the Flight's direction of movement.
    #     communication_range: Radius to look around for Flights to negotiate with.
    # =========================================================================

    # TODO: Performance indicators:
    #  Fuel saved / alliance

    def __init__(
            self,
            unique_id,
            model,
            pos,
            destination_agent,
            destination_pos,
            departure_time,
            speed,
            communication_range,
            behavior_wights = [1, 0, 0, 0]
    ):

        super().__init__(unique_id, model)
        self.agent_type = "Flight"
        self.pos = np.array(pos)
        self.destination = np.array(destination_pos)
        self.destination_agent = destination_agent
        self.speed = speed
        self.departure_time = departure_time
        self.origin_pos = np.array(pos)
        self.heading = [self.destination[0] - self.pos[0], self.destination[1] - self.pos[1]]
        self.communication_range = communication_range
        self.speed_to_joining = None

        self.behavior = choices(["budget", "green", "express", "balanced"], weights=behavior_wights, k=1)[0]

        # =====================================================================
        #   Initialize parameters, the values will not be used later on.
        # =====================================================================
        self.agents_in_my_formation = []

        self.leaving_point = [-10, -10]
        self.joining_point = [-10, -10]

        # Performance indicators
        self.planned_fuel = calc_distance(self.pos, self.destination)
        self.estimated_fuel_saved = 0  #
        self.real_fuel_saved = None
        self.distance_in_formation = 0  ##
        self.formation_size = 0  ##
        self.planned_flight_time = self.distance_to_destination(self.destination) / self.speed
        self.scheduled_arrival = self.departure_time + self.planned_flight_time
        # self.estimated_flight_time = 0 #
        # self.estimated_arrival = 0 #
        self.real_flight_time = 0  ##
        self.real_arrival = None  ##
        self.estimated_delay = 0
        self.delay = None  ##
        self.fuel_consumption = 0  # A counter which counts the fuel consumed
        self.deal_value = 0  # All the fuel lost or won during bidding
        self.estimated_utility_score = 0
        self.real_utility_score = 0

        self.formation_state = "no_formation"  # 0 = no formation, 1 = committed, 2 = in formation, 3 = unavailable, 4 = adding to formation

        self.state = "scheduled"  # Can be scheduled, flying, or arrived

        self.last_bid_expiration_time = 0
        self.alliance = 0

        # =============================================================================
        #   Agents decide during initialization whether they are manager or auctioneer
        #   However, this can also be changed during the flight.
        #
        #   !!! TODO Exc. 1.3: implement when a manager can become an auctioneer and vice versa.!!!
        # =============================================================================
        self.accepting_bids = 0
        self.received_bids = []

        if self.model.negotiation_method == 0:
            self.manager = self.model.random.choice([0, 1])
        elif self.model.negotiation_method == 1:
            self.manager = 0
        elif self.model.negotiation_method == 4:
            self.manager = 0
        elif self.model.negotiation_method == 2:
            self.manager = 0
        elif self.model.negotiation_method == 3:
            self.manager = 0
        else:
            raise NotImplementedError
        self.update_role()
        # create a negotiation object if required
        if self.model.negotiation_method == 1:
            self.cnp = CNP(self)
        if self.model.negotiation_method == 2:
            self.english = English(self)
        if self.model.negotiation_method == 3:
            self.vickrey = Vickrey(self)
        if self.model.negotiation_method == 4:
            self.japanese = Japanese(self)

    # =============================================================================
    #   __hash__, __eq__, __ne__ are required so Flight objects can be used as
    #   dictionary keys.
    # =============================================================================
    def __hash__(self):
        return hash(self.unique_id)

    def __eq__(self, other):
        return self.unique_id == other.unique_id

    def __ne__(self, other):
        return not(self == other)

    def update_role(self):
        if self.manager:
            if self.formation_state not in ("committed", "adding_to_formation"):
                self.accepting_bids = 1
            else:
                self.accepting_bids = 0
        else:
            self.accepting_bids = 0
        self.auctioneer = abs(1 - self.manager)

    # =============================================================================
    #   In advance, the agent moves (physically) to the next step (after having negotiated)
    # =============================================================================
    def advance(self):
        self.do_move()

    # =============================================================================
    #   In the "step", the negotiations are performed.
    #   Check if the agent is flying, because negotiations are only allowed in the air.
    #
    #   !!! TODO Exc. 2: implement other negotiation methods.!!!
    # =============================================================================
    def step(self):
        if self.state == "flying":
            if self.formation_state in ("committed", "adding_to_formation"):
                if self.manager == 1:
                    for agent in self.agents_in_my_formation:
                        if agent.formation_state is "committed":
                            self.speed_to_joining = self.calc_speed_to_joining_point(agent)
                            break
                else:
                    for agent in self.agents_in_my_formation:
                        if agent.manager == 1:
                            self.speed_to_joining = self.calc_speed_to_joining_point(agent)
                            break

            # Update the relevant performance indicators
            self.real_flight_time += 1
            if self.manager == 1:
                self.formation_size = 1 + len(self.agents_in_my_formation)
            else:
                self.formation_size = 0
            if len(self.agents_in_my_formation) > 0:
                self.distance_in_formation += self.speed

            # Steps for the different negotiation methods
            if self.model.negotiation_method == 0:
                do_greedy(self)
            if self.model.negotiation_method == 1:
                self.cnp.do_cnp()
            if self.model.negotiation_method == 2:
                self.english.do_english()
            if self.model.negotiation_method == 3:
                self.vickrey.do_Vickrey()
            if self.model.negotiation_method == 4:
                self.japanese.do_japanese()

#            print(self.calc_joining_point(self))


    # =============================================================================
    #   This formula assumes that the route of both agents are of same length, 
    #   because joining- and leaving-points are taken to be as the middle-point 
    #   between their current positions / destinations.
    #
    #   !!! TODO Exc. 1.3: improve calculation joining/leaving point.!!!
    # =============================================================================
    # If individual is True, function calculates the individual fuel saving of self, instead of the savings of the full formation.

    def calculate_potential_fuelsavings(self, target_agent, individual=False):
        if len(self.agents_in_my_formation) == 0 and len(target_agent.agents_in_my_formation) == 0:
            joining_point = self.calc_joining_point(target_agent)
            leaving_point = self.calc_leaving_point(target_agent.pos, target_agent.destination)
            if individual is False:
                original_distance = calc_distance(self.pos, self.destination) + calc_distance(target_agent.pos,
                                                                                              target_agent.destination)

                # We can multiply by 2 as the joining- and leaving-points are in the middle!
                # WARNING: If you change the way the leaving- and joining-points are calculated, you should change this formula accordingly!

                added_distance_agent1 = calc_distance(self.pos, joining_point) + calc_distance(leaving_point,
                                                                                               self.destination)
                added_distance_agent2 = calc_distance(target_agent.pos, joining_point) + calc_distance(
                    target_agent.destination, leaving_point)
                formation_distance = calc_distance(leaving_point, joining_point) * 2

                new_total_fuel = self.model.fuel_reduction * formation_distance + added_distance_agent1 + added_distance_agent2

                fuel_savings = original_distance - new_total_fuel
            else:
                original_distance = calc_distance(self.pos, self.destination)
                # print("original distance", original_distance)
                added_distance = calc_distance(self.pos, joining_point) + calc_distance(leaving_point, self.destination)
                # print(f"added distance {added_distance} = {calc_distance(self.pos, joining_point)} + {calc_distance(leaving_point, self.destination)}")
                formation_distance = calc_distance(leaving_point, joining_point)
                # print("formation distance", formation_distance)
                new_total_fuel = self.model.fuel_reduction * formation_distance + added_distance
                fuel_savings = original_distance - new_total_fuel

        else:
            if len(self.agents_in_my_formation) > 0 and len(target_agent.agents_in_my_formation) > 0:
                raise Exception("This function is not advanced enough to handle two formations joining")
            if individual is False:
                if len(self.agents_in_my_formation) > 0 and len(target_agent.agents_in_my_formation) == 0:
                    formation_leader = self
                    formation_joiner = target_agent
                    n_agents_in_formation = len(self.agents_in_my_formation) + 1

                elif len(self.agents_in_my_formation) == 0 and len(target_agent.agents_in_my_formation) > 0:
                    formation_leader = target_agent
                    formation_joiner = self
                    n_agents_in_formation = len(target_agent.agents_in_my_formation) + 1

                joining_point = formation_leader.calc_joining_point(formation_joiner)
                leaving_point = formation_leader.leaving_point

                # Fuel for leader
                new_distance_formation = calc_distance(formation_leader.pos, joining_point) + calc_distance(
                    joining_point, leaving_point)
                total_fuel_formation = self.model.fuel_reduction * n_agents_in_formation * new_distance_formation

                original_distance_formation = calc_distance(formation_leader.pos, leaving_point)
                original_fuel_formation = self.model.fuel_reduction * n_agents_in_formation * original_distance_formation

                fuel_savings_formation = original_fuel_formation - total_fuel_formation

                # Fuel for new agent
                fuel_to_joining_joiner = calc_distance(self.pos, joining_point)
                fuel_in_formation_joiner = calc_distance(joining_point, leaving_point) * self.model.fuel_reduction
                fuel_from_leaving_joiner = calc_distance(leaving_point, formation_joiner.destination)
                total_fuel_joiner = fuel_to_joining_joiner + fuel_in_formation_joiner + fuel_from_leaving_joiner

                original_fuel_joiner = calc_distance(formation_joiner.pos, formation_joiner.destination)

                fuel_savings_joiner = original_fuel_joiner - total_fuel_joiner

                fuel_savings = fuel_savings_joiner + fuel_savings_formation
            else:
                if len(self.agents_in_my_formation) > 0 and len(target_agent.agents_in_my_formation) == 0:
                    formation_leader = self
                    formation_joiner = target_agent
                    joining_point = formation_leader.calc_joining_point(formation_joiner)
                    leaving_point = formation_leader.leaving_point
                    new_distance_formation = calc_distance(formation_leader.pos, joining_point) + calc_distance(
                        joining_point, leaving_point)
                    new_formation_fuel = self.model.fuel_reduction * new_distance_formation
                    original_distance_formation = calc_distance(formation_leader.pos, leaving_point)
                    original_fuel_formation = self.model.fuel_reduction * original_distance_formation
                    fuel_savings = original_fuel_formation - new_formation_fuel

                elif len(self.agents_in_my_formation) == 0 and len(target_agent.agents_in_my_formation) > 0:
                    formation_leader = target_agent
                    formation_joiner = self
                    joining_point = target_agent.calc_joining_point(formation_joiner)
                    leaving_point = formation_leader.leaving_point
                    fuel_to_joining = calc_distance(self.pos, joining_point)
                    fuel_in_formation = calc_distance(joining_point, leaving_point) * self.model.fuel_reduction
                    fuel_from_leaving = calc_distance(leaving_point, formation_joiner.destination)
                    new_fuel = fuel_to_joining + fuel_in_formation + fuel_from_leaving
                    original_fuel = calc_distance(formation_joiner.pos, formation_joiner.destination)
                    fuel_savings = original_fuel - new_fuel
        # print('fuel savings', fuel_savings)
        return fuel_savings


    # =============================================================================
    #   This formula assumes that the route of both agents are of same length,
    #   because joining- and leaving-points are taken to be as the middle-point
    #   between their current positions / destinations.
    #
    #   !!! TODO Exc. 1.3: improve calculation joining/leaving point.!!!
    # =============================================================================
    def calculate_potential_delay(self, target_agent):
        if len(self.agents_in_my_formation) == 0 and len(target_agent.agents_in_my_formation) == 0:
            joining_point = self.calc_joining_point(target_agent)
            leaving_point = self.calc_leaving_point(target_agent.pos, target_agent.destination)
            original_time = calc_distance(self.pos, self.destination) / self.speed

        else:
            if len(self.agents_in_my_formation) > 0 and len(target_agent.agents_in_my_formation) > 0:
                raise Exception("This function is not advanced enough to handle two formations joining")

            elif len(self.agents_in_my_formation) > 0 and len(target_agent.agents_in_my_formation) == 0:
                formation_leader = self
                formation_joiner = target_agent
                original_time = (calc_distance(self.pos, self.leaving_point) + calc_distance(self.leaving_point,
                                                                                             self.destination)
                                 ) / self.speed

            elif len(self.agents_in_my_formation) == 0 and len(target_agent.agents_in_my_formation) > 0:
                formation_leader = target_agent
                formation_joiner = self
                original_time = calc_distance(self.pos, self.destination) / self.speed

            joining_point = formation_leader.calc_joining_point(formation_joiner)
            leaving_point = formation_leader.leaving_point

        if self.speed_to_joining is None:
            assert self.formation_state in ("no_formation", "in_formation"), self.formation_state
            local_speed_to_joining = self.calc_speed_to_joining_point(target_agent)
        else:
            assert self.formation_state in ("adding_to_formation", "committed"), self.formation_state
            local_speed_to_joining = self.speed_to_joining
        if calc_distance(self.pos, joining_point) > 0.002 and \
                local_speed_to_joining != 0.0:
            joining_time = calc_distance(self.pos, joining_point) / local_speed_to_joining
        else:
            joining_time = 0
        if calc_distance(leaving_point, self.destination) > (self.speed / 2):
            leaving_time = calc_distance(leaving_point, self.destination) / self.speed
        else:
            leaving_time = 0
        formation_time = calc_distance(leaving_point, joining_point) / self.speed
        new_time = formation_time + joining_time + leaving_time

        delay = new_time - original_time

        return delay


    # =========================================================================
    #   Add the chosen flight to the formation. While flying to the joining point 
    #   of a new formation, managers temporarily don't accept any new bids.
    #
    #   Calculate how the "bid_value" is divided.
    #   The agents already in the formation, share the profit from the bid equally.
    #
    #   !!! TODO Exc. 1.1: improve calculation joining/leaving point.!!!
    # =========================================================================
    def add_to_formation(self, target_agent, bid_value, discard_received_bids=True):
        self.model.fuel_savings_closed_deals += self.calculate_potential_fuelsavings(target_agent)

        if len(target_agent.agents_in_my_formation) > 0 and len(self.agents_in_my_formation) > 0:
            raise Exception(
                "Warning, you are trying to combine multiple formations - some functions aren't ready for this ("
                "such as potential fuel-savings)")

        if len(target_agent.agents_in_my_formation) > 0 and len(self.agents_in_my_formation) == 0:
            raise Exception("Model isn't designed for this scenario.")


        self.model.add_to_formation_counter += 1
        self.accepting_bids = False

        if discard_received_bids:
            # Discard all bids that have been received
            self.received_bids = []

        involved_agents = [self]
        for agent in self.agents_in_my_formation:
            involved_agents.append(agent)  # These are the current formation agents

        for agent in involved_agents:
            agent.agents_in_my_formation.append(target_agent)
            agent.formation_state = "adding_to_formation"

        if target_agent in involved_agents:
            raise Exception("This is not correct")

        self.joining_point = self.calc_joining_point(target_agent)
        self.speed_to_joining = self.calc_speed_to_joining_point(target_agent)
        target_speed_to_joining = target_agent.calc_speed_to_joining_point(self)

        bid_receivers = bid_value / (len(
            self.agents_in_my_formation) + 1)
        self.deal_value += bid_receivers
        for agent in self.agents_in_my_formation:
            agent.deal_value += bid_receivers
        target_agent.deal_value -= bid_value

        target_agent.formation_state = "committed"

        target_agent.speed_to_joining = target_speed_to_joining
        target_agent.joining_point = self.joining_point
        target_agent.leaving_point = self.leaving_point

        potential_fuel_saved = self.calculate_potential_fuelsavings(target_agent, individual=True)
        potential_delay = self.calculate_potential_delay(target_agent)
        target_potential_fuel_saved = target_agent.calculate_potential_fuelsavings(self, individual=True)
        target_potential_delay = target_agent.calculate_potential_delay(self)

        target_agent.agents_in_my_formation = involved_agents[:]
        for agent in involved_agents:
            agent.joining_point = self.joining_point
            agent.leaving_point = self.leaving_point
            agent.speed_to_joining = self.speed_to_joining

            agent.estimated_fuel_saved += potential_fuel_saved
            agent.estimated_delay += potential_delay
            agent.estimated_utility_score += utility_function(potential_fuel_saved + bid_receivers,
                                                              potential_fuel_saved,
                                                              potential_delay,
                                                              behavior=agent.behavior)

        # involved_agents.append(target_agent)

        target_agent.estimated_fuel_saved += target_potential_fuel_saved
        target_agent.estimated_delay += target_potential_delay
        target_agent.estimated_utility_score += utility_function(target_potential_fuel_saved - bid_value,
                                                                 target_potential_fuel_saved,
                                                                 target_potential_delay,
                                                                 behavior=target_agent.behavior)

        # self.estimated_flight_time = self.real_flight_time + (
        #         calc_distance(self.pos, self.joining_point) +
        #         calc_distance(self.joining_point, self.leaving_point) +
        #         calc_distance(self.leaving_point, self.destination)) / self.speed
        # self.estimated_arrival = self.departure_time + self.estimated_flight_time

        # target_agent.estimated_flight_time = target_agent.real_flight_time + (
        #         calc_distance(target_agent.pos, target_agent.joining_point) +
        #         calc_distance(target_agent.joining_point, target_agent.leaving_point) +
        #         calc_distance(target_agent.leaving_point, target_agent.destination)) / target_agent.speed
        # target_agent.estimated_arrival = target_agent.departure_time + target_agent.estimated_flight_time

    # =========================================================================
    #   The value of the bid is added to the "deal value" of the manager, 
    #   and removed from the auctioneer. A manager leads the formation, the rest
    #   are 'slaves' to the manager.
    #
    #   !!! TODO Exc. 1.3: improve calculation joining/leaving point.!!!
    # =========================================================================
    def start_formation(self, target_agent, bid_value, discard_received_bids=True):
        self.model.new_formation_counter += 1
        self.model.fuel_savings_closed_deals += self.calculate_potential_fuelsavings(target_agent)
        self.deal_value += bid_value
        target_agent.deal_value -= bid_value

        self.accepting_bids = False
        self.formation_role = "manager"
        target_agent.formation_role = "slave"

        # You can use the following error message if you want to ensure that managers can only start formations with
        # auctioneers. The code itself has no functionality, but is a "check"

        if self.agents_in_my_formation and target_agent.auctioneer:
            raise Exception("Something is going wrong")

        if discard_received_bids:
            self.received_bids = []

        if self.distance_to_destination(target_agent.pos) < 0.002:
            # Edge case where agents are at the same spot.
            self.formation_state = "in_formation"
            target_agent.formation_state = "in_formation"
            self.accepting_bids = True

        else:
            self.joining_point = self.calc_joining_point(target_agent)

            target_agent.joining_point = self.joining_point
            self.speed_to_joining = self.calc_speed_to_joining_point(target_agent)
            target_agent.speed_to_joining = self.calc_speed_to_joining_point(target_agent)

            target_agent.formation_state = "committed"
            self.formation_state = "committed"

        potential_fuel_saved = self.calculate_potential_fuelsavings(target_agent, individual=True)
        self.estimated_fuel_saved += potential_fuel_saved
        target_potential_fuel_saved = target_agent.calculate_potential_fuelsavings(self, individual=True)
        target_agent.estimated_fuel_saved += target_potential_fuel_saved

        potential_delay = self.calculate_potential_delay(target_agent)
        self.estimated_delay += potential_delay
        target_potential_delay = target_agent.calculate_potential_delay(self)
        target_agent.estimated_delay += target_potential_delay

        self.estimated_utility_score += utility_function(potential_fuel_saved + bid_value, potential_fuel_saved,
                                                         potential_delay, behavior=self.behavior)
        target_agent.estimated_utility_score += utility_function(target_potential_fuel_saved - bid_value,
                                                                 target_potential_fuel_saved, target_potential_delay,
                                                                 behavior=target_agent.behavior)

        self.leaving_point = self.calc_leaving_point(target_agent.pos, target_agent.destination)
        self.agents_in_my_formation.append(target_agent)
        target_agent.agents_in_my_formation.append(self)
        target_agent.leaving_point = self.leaving_point

        # self.estimated_flight_time = self.real_flight_time + (
        #         calc_distance(self.pos, self.joining_point) +
        #         calc_distance(self.joining_point, self.leaving_point) +
        #         calc_distance(self.leaving_point, self.destination)) / self.speed
        # self.estimated_arrival = self.departure_time + self.estimated_flight_time

        # target_agent.estimated_flight_time = target_agent.real_flight_time + (
        #         calc_distance(target_agent.pos, target_agent.joining_point) +
        #         calc_distance(target_agent.joining_point, target_agent.leaving_point) +
        #         calc_distance(target_agent.leaving_point, target_agent.destination)) / target_agent.speed
        # target_agent.estimated_arrival = target_agent.departure_time + target_agent.estimated_flight_time

    # =============================================================================
    #   This function finds the agents to make a bid to, and returns a list of these agents.
    #   In the current implementation, it randomly returns an agent, 
    #   instead of deciding which manager it wants tomake a bid to.
    # =============================================================================

    def find_greedy_candidate(self):
        neighbors = self.model.space.get_neighbors(pos=self.pos, radius=self.communication_range, include_center=True)
        candidates = []
        for agent in neighbors:
            if type(agent) is Flight:
                if agent.manager == 1 and agent.accepting_bids == 1:
                    if agent.formation_state == "no_formation" or agent.formation_state == "in_formation":
                        candidates.append(agent)
        return candidates

    # =========================================================================
    #   Making the bid.
    # =========================================================================
    def make_bid(self, bidding_target, bid_value, validity, bid_expiration_date):
        bid = {"bidding_agent": self, "value": bid_value, "validity": validity, "exp_date": bid_expiration_date}
        bidding_target.received_bids.append(bid)

    # =========================================================================
    #   This function randomly chooses a new destination airport. 
    #
    #   !!! This can be used if you decide to close airports on the fly while 
    #   implementing de-commitment (bonus-assignment).!!!
    # =========================================================================
    def find_new_destination(self):
        open_destinations = []
        for agent in self.model.schedule.agents:
            if type(agent) is Airport:
                if agent.airport_type == "Destination":
                    open_destinations.append(agent)

        self.destination_agent = self.model.random.choice(open_destinations)
        self.destination = self.destination_agent.pos

        # You could add code here to decommit from the current bid.

    # =========================================================================
    #   'calc_middle_point'
    #   Calculates the middle point between two geometric points a & b. 
    #   Is used to calculate the joining- and leaving-points of a formation.
    #
    #   'distance_to_destination' 
    #   Calculates the distance to one point (destination) from an agents' current point.
    #
    #   !!! TODO Exc. 1.3: improve calculation joining/leaving point.!!!
    # =========================================================================

    def distance_to_destination(self, destination):
        # 
        return ((destination[0] - self.pos[0]) ** 2 + (destination[1] - self.pos[1]) ** 2) ** 0.5

    # =========================================================================
    #   This function actually moves the agent. It considers many different 
    #   scenarios in the if's and elif's, which are explained step-by-step.
    # =========================================================================
    def do_move(self):

        if self.distance_to_destination(self.destination) <= self.speed / 2:
            # If the agent is within reach of its destination, the state is changed to "arrived"
            if self.state == "flying":
                self.real_fuel_saved = self.planned_fuel - self.fuel_consumption
                self.real_arrival = self.departure_time + self.real_flight_time
                self.delay = self.real_arrival - self.scheduled_arrival
                # Only consider the utility of flights that entered a formation.
                # Flights that did not enter any formations will be assumed to have 0 utility
                if self.deal_value != 0:
                    self.real_utility_score = utility_function(self.real_fuel_saved + self.deal_value,
                                                               self.real_fuel_saved, self.delay, behavior=self.behavior)
                # print(
                #     f"Flight {self.unique_id} arrived at {self.real_arrival} with a delay of {self.delay}, saving {self.real_fuel_saved} fuel.")
                self.state = "arrived"

        elif self.model.schedule.steps >= self.departure_time:
            # The agent only starts flying if it is at or past its departure time.
            self.state = "flying"

            if self.formation_state == "in_formation" and self.distance_to_destination(
                    self.leaving_point) <= self.speed / 2:
                # If agent is in formation & close to leaving-point, disband the formation
                for agent in self.agents_in_my_formation:
                    agent.state = "flying"
                    agent.formation_state = "no_formation"
                    agent.agents_in_my_formation = []
                self.state = "flying"
                self.formation_state = "no_formation"
                self.agents_in_my_formation = []

            if (self.formation_state == "committed" or self.formation_state == "adding_to_formation") and \
                    (self.distance_to_destination(self.joining_point) <= self.speed_to_joining / 2 or \
                    self.distance_to_destination(self.joining_point) <= 0.002):
                # If the agent reached the joining point of a new formation,
                # change status to "in formation" and start accepting new bids again.
                # If an agent from an already existing formation reaches the joining point, assume all agents that are
                # already in formation have reached the joining point
                all_arrived = True
                for agent in self.agents_in_my_formation:
                    if not (agent.distance_to_destination(agent.joining_point) <= agent.speed_to_joining / 2 or \
                            agent.distance_to_destination(agent.joining_point) <= 0.002):
                        all_arrived = False

                if all_arrived:
                    for agent in self.agents_in_my_formation:
                        agent.formation_state = "in_formation"
                        if agent.manager == 1:
                            agent.accepting_bids = True
                        agent.speed_to_joining = None
                        agent.joining_point = None
                    self.formation_state = "in_formation"
                    if self.manager == 1:
                        self.accepting_bids = True
                    self.speed_to_joining = None
                    self.joining_point = None

        if self.state == "flying":
            self.model.total_flight_time += 1
            if self.formation_state == "in_formation":
                # If in formation, fuel consumption is 75% of normal fuel consumption.
                f_c = self.model.fuel_reduction * self.speed
                self.heading = [self.leaving_point[0] - self.pos[0], self.leaving_point[1] - self.pos[1]]
                self.heading /= np.linalg.norm(self.heading)
                new_pos = self.pos + self.heading * self.speed

            elif self.formation_state == "committed" or self.formation_state == "adding_to_formation":
                # While on its way to join a new formation
                if self.formation_state == "adding_to_formation" and len(self.agents_in_my_formation) > 0:
                    f_c = self.speed_to_joining * self.model.fuel_reduction
                else:
                    f_c = self.speed_to_joining

                # If somehow arrived to the joining point sooner than other agents in formation, stay put
                if self.distance_to_destination(self.joining_point) == 0.0:
                    new_pos = self.pos
                else:
                    self.heading = [self.joining_point[0] - self.pos[0], self.joining_point[1] - self.pos[1]]
                    self.heading /= np.linalg.norm(self.heading)
                    new_pos = self.pos + self.heading * self.speed_to_joining

            else:
                self.heading = [self.destination[0] - self.pos[0], self.destination[1] - self.pos[1]]
                f_c = self.speed
                self.heading /= np.linalg.norm(self.heading)
                new_pos = self.pos + self.heading * self.speed

            if f_c < 0:
                raise Exception("Fuel cost lower than 0")
            # if f_c < 0.001:
            #     print(self.unique_id, self.formation_state, self.manager, self.distance_to_destination(self.joining_point), f_c, self.speed_to_joining)
            #     print([(mate.unique_id, mate.formation_state, mate.manager) for mate in self.agents_in_my_formation])

            self.model.total_fuel_consumption += f_c
            self.fuel_consumption += f_c

            # print(f"Flight {self.unique_id} moves to {new_pos}.")
            self.model.space.move_agent(self, new_pos)



    def is_destination_open(self):
        if self.destination_agent.airport_type == "Closed":
            return False
        else:
            return True


    # ========================================================================= 
    #   Calculates the speed to joining point.
    #
    #   !!! TODO Exc. 1.3: improve calculation joining/leaving point.!!!
    # =========================================================================
    def calc_speed_to_joining_point(self, neighbor):
        if self.joining_point is None:
            joining_point = self.calc_joining_point(neighbor)
        else:
            joining_point = self.joining_point
        # Am I stupid, or dist_self and are literally the same in the original code?
        dist_self = ((joining_point[0] - self.pos[0]) ** 2 + (joining_point[1] - self.pos[1]) ** 2) ** 0.5
        dist_neighbor = ((joining_point[0] - neighbor.pos[0]) ** 2 + (joining_point[1] - neighbor.pos[1]) ** 2) ** 0.5
        try:
            if dist_self > 0.0 and dist_neighbor > 0.0:
                # Calculate the speed of each airplane, such that they reach the joining point simultaniously.
                # This means the speed to joining point must be proportional to the distance to the joining point
                # dist_self = time * speed_self ; dist_neighbor = time * speed_neighbor
                # => dist_self / dist_neighbor = speed_self / speed_neighbor
                dist_fraction = dist_self/dist_neighbor
                # Keep the average of the two speeds to the regular speed: (speed_self + speed_neighbor)/2 = self.speed
                speed_self = self.speed * 2 * dist_fraction / (1 + dist_fraction)
                speed_neighbor = speed_self / dist_fraction
                time_self = math.floor(dist_self / speed_self) + 1*bool(dist_self % speed_self>0.002)
                # time_neighbor = math.floor(dist_neighbor / speed_neighbor) + 1*bool(dist_neighbor % speed_self>0.002)
                # speed_self = dist_self/time_self
                # speed_neighbor = dist_neighbor/time_self
                # assert time_self == time_neighbor, (time_self, time_neighbor)
                # assert speed_self == dist_self/time_self, (dist_self, dist_self/speed_self, time_self, speed_self, dist_self/time_self)
                assert round(dist_self / speed_self, 3) == round(dist_neighbor / speed_neighbor, 3), f"{dist_self} / {speed_self} = {dist_neighbor} / {speed_neighbor} => {round(dist_self / speed_self, 3)} = {round(dist_neighbor / speed_neighbor, 3)}"
                assert speed_self > 0 and speed_neighbor > 0, f"{speed_self}, {speed_neighbor}\n{dist_self}, {dist_neighbor}\n{1-speed_fraction}"
            elif dist_self == 0.0:
                speed_self = 0.0
                speed_neighbor = self.speed
            elif dist_neighbor == 0.0:
                speed_self = self.speed
                speed_neighbor = 0.0
            else:
                raise Exception(f"What the fuck? {dist_self}, {dist_neighbor}")
        except FloatingPointError as err:
            print(dist_self)
            print(dist_neighbor)
            print(dist_fraction)
            print(speed_self)
            raise err
        # print(f"Self: {dist_self, speed_self} = {dist_self/speed_self}; Neighbor{dist_neighbor, speed_neighbor} = {dist_neighbor/speed_neighbor}")
        return speed_self
        # try:
        #     rest = dist_self % self.speed
        #     regular_time = math.floor(dist_self / self.speed)
        #     if rest > 0:
        #         time = regular_time + 1
        #     elif rest == 0:
        #         time = regular_time
        #     return (dist_self / time)
        # except FloatingPointError as err:
        #     # What if self and neighbor take off from the same airport at the same time, and thus dist_self and dist_neighbor are 0?
        #     if dist_self == 0 and dist_neighbor == 0:
        #         return 0.0
        #     else:
        #         print(self.pos, neighbor.pos)
        #         print(dist_self, dist_neighbor)
        #         print(regular_time, rest)
        #         raise err

    def calc_joining_point(self, target_agent):
        target_agent_pos = target_agent.pos
        target_agent_des = target_agent.destination
        margin = 1
        if abs(self.pos[0] - target_agent_pos[0]) < margin and abs(self.pos[1] - target_agent_pos[1]) < margin:
            opt_joining_point = self.pos
            return opt_joining_point
        else:
            if len(self.agents_in_my_formation) > 0:
                self_joining_fuel_fraction = self.model.fuel_reduction
                target_joining_fuel_fraction = 1
            elif len(target_agent.agents_in_my_formation) > 0:
                target_joining_fuel_fraction = self.model.fuel_reduction
                self_joining_fuel_fraction = 1
            else:
                target_joining_fuel_fraction = 1
                self_joining_fuel_fraction = 1
            assert not (len(self.agents_in_my_formation) > 0 and len(target_agent.agents_in_my_formation) > 0), \
                "Not possible for two formations to merge"

            # middle point between self and target location
            mid_point1 = calc_middle_point(self.pos, target_agent_pos)
            # middle point between self and target destination
            mid_point2 = calc_middle_point(self.destination, target_agent_des)
            # original distance from current position to middle point
            # vector a is middle point to current position
            # a_vec = calc_vector(mid_point1, self.pos)
            # print('a vector', a_vec)
            # # vector b is from middle point to destination middle point (same for both self and target, because middle point)
            # b_vec = calc_vector(mid_point1, mid_point2)
            # print('b vector', b_vec)
            # alfa is angle between self and vector from mid point to mid point
            #alfa = calc_angle(a_vec, b_vec)
            # alfa = np.arctan((mid_point2[0] - mid_point1[0]) / (mid_point2[1]-mid_point1[1])) +\
            #        np.arctan((mid_point1[0] - self.pos[0]) / (mid_point1[1] - self.pos[1]))
            # print('alfa', alfa)
            #use y = ax+b
            #determine a
            a = (mid_point1[1] - mid_point2[1]) / (mid_point1[0] - mid_point2[0])
            b = mid_point1[1]- a * mid_point1[0]
            y = np.linspace(mid_point1[1], mid_point2[1], num=200)
            x=np.zeros(len(y))
            for i in range(len(y)):
                x[i]=(y[i] - b) / a

            potential_b = np.column_stack((x,y))
            route_fuel_self = np.zeros(len(y))
            route_fuel_target = np.zeros(len(y))
            total_route_fuel = np.zeros(len(y))

            for i in range(len(y)):
                route_fuel_self[i] = self_joining_fuel_fraction * calc_distance(self.pos, potential_b[i])\
                                  + self.model.fuel_reduction * calc_distance(potential_b[i], mid_point2)
                route_fuel_target[i] = target_joining_fuel_fraction * calc_distance(target_agent_pos, potential_b[i])\
                                         + self.model.fuel_reduction * calc_distance(potential_b[i], mid_point2)
                total_route_fuel[i] = route_fuel_self[i] + route_fuel_target[i]
            the_index = np.argmin(total_route_fuel)
            opt_joining_point = potential_b[the_index]
            # print(the_index)
            #print(opt_joining_point)

            # shortest_route = 10000
            # opt_joining_point = (0, 0)
            # for i in range(len(potential_b)):
            #     if total_route_length[i] < shortest_route:
            #         shortest_route = total_route_length[i]
            #         opt_joining_point = potential_b[i]
            #     # else:
            #     #     break
            return opt_joining_point

    def calc_leaving_point(self, target_agent_pos, target_agent_des):
        margin = 1
        if abs(self.destination[0] - target_agent_des[0]) < margin and abs(self.destination[1] - target_agent_des[1]) < margin:
            opt_leaving_point = self.pos
            return opt_leaving_point
        else:
            # middle point between self and target location
            mid_point1 = calc_middle_point(self.pos, target_agent_pos)
            # middle point between self and target destination
            mid_point2 = calc_middle_point(self.destination, target_agent_des)
            # original distance from current position to middle point
            # b_magn = calc_distance(self.pos, mid_point1)
            # vector a is middle point (at end) to destination
            a_vec = calc_vector(mid_point2, self.destination)
            # vector b is from middle point to destination middle point (same for both self and target, because middle point)
            b_vec = calc_vector(mid_point2, mid_point1)
            # alfa is angle between self and vector from mid point to mid point
            #alfa = calc_angle(a_vec, b_vec)
            a = (mid_point1[1] - mid_point2[1]) / (mid_point1[0] - mid_point2[0])
            b = mid_point1[1] - a * mid_point1[0]
            y = np.linspace(mid_point1[1], mid_point2[1], num=200)
            x = np.zeros(len(y))
            for i in range(len(y)):
                x[i] = (y[i] - b) / a

            potential_b = np.column_stack((x, y))
            route_length = np.zeros(len(y))
            total_route_length = np.zeros(len(y))
            route_length_target = np.zeros(len(y))

            for i in range(len(y)):
                route_length[i] = calc_distance(self.destination, potential_b[i]) + 0.75 * calc_distance(potential_b[i],
                                                                                                 mid_point1)
                route_length_target[i] = calc_distance(target_agent_des, potential_b[i]) + 0.75 * calc_distance(
                    potential_b[i],
                    mid_point1)
                total_route_length[i] = route_length[i] + route_length_target[i]
            the_index = np.argmin(total_route_length)
            opt_leaving_point = potential_b[the_index]
            # print(the_index)
            #print(opt_leaving_point)
            return opt_leaving_point



            # alfa = np.arctan((mid_point2[0] - mid_point1[0]) / (mid_point2[1] - mid_point1[1])) + \
            #        np.arctan((mid_point1[0] - self.pos[0]) / (mid_point1[1] - self.pos[1]))
            # # try 40000: vary potential point B (is new meeting point)
            # unity_vector = np.array([np.sin(alfa), np.cos(alfa)])
            # # point b was meeting point in my original drawings
            # potential_b = np.zeros((100, 2))
            # route_length = np.zeros(100)
            # total_route_length = np.zeros(100)
            # route_length_target = np.zeros(100)
            #
            # for i in range(100):
            #     potential_b[i] = unity_vector * i
            #     route_length[i] = calc_distance(self.destination, potential_b[i]) + 0.75 * calc_distance(potential_b[i], mid_point1)
            #     route_length_target[i] = calc_distance(target_agent_des, potential_b[i]) + 0.75 * calc_distance(
            #         potential_b[i],
            #         mid_point1)
            #     total_route_length[i] = route_length[i] + route_length_target[i]
            #
            # combined_list = np.column_stack((potential_b, total_route_length))
            #
            # shortest_route = 10000
            # opt_leaving_point = (0, 0)
            # for i in range(len(combined_list)):
            #     if total_route_length[i] < shortest_route:
            #         shortest_route = total_route_length[i]
            #         opt_leaving_point = potential_b[i]
            #     # else:
            #     #     break

            # #print(opt_leaving_point)
            # return opt_leaving_point
