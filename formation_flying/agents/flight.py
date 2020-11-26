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

        self.behavior = choices(["budget", "green", "express", "balanced"], weights=behavior_wights, k=1)[0]

        # =====================================================================
        #   Initialize parameters, the values will not be used later on.
        # =====================================================================
        self.agents_in_my_formation = []

        self.leaving_point = [-10, -10]
        self.joining_point = [-10, -10]

        # Performance indicators
        self.planned_fuel = calc_distance(self.pos, self.destination)
        self.model.total_planned_fuel += self.planned_fuel
        self.estimated_fuel_saved = 0  #
        self.real_fuel_saved = None
        self.distance_in_formation = 0  ##
        self.formation_size = 0  ##
        self.planned_flight_time = calc_distance(self.pos, self.destination) / self.speed
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
            self.accepting_bids = 1
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

            print(self.calc_joining_point(self))


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
            leaving_point = self.calc_joining_point(target_agent)
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
                added_distance = calc_distance(self.pos, joining_point) + calc_distance(leaving_point, self.destination)
                formation_distance = calc_distance(leaving_point, joining_point)
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

                joining_point = self.calc_joining_point(formation_leader.pos, formation_joiner.pos)
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
                    joining_point = self.calc_joining_point(formation_leader.pos, formation_joiner.pos)
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
                    joining_point = self.calc_joining_point(formation_leader.pos, formation_joiner.pos)
                    leaving_point = formation_leader.leaving_point
                    fuel_to_joining = calc_distance(self.pos, joining_point)
                    fuel_in_formation = calc_distance(joining_point, leaving_point) * self.model.fuel_reduction
                    fuel_from_leaving = calc_distance(leaving_point, formation_joiner.destination)
                    new_fuel = fuel_to_joining + fuel_in_formation + fuel_from_leaving
                    original_fuel = calc_distance(formation_joiner.pos, formation_joiner.destination)
                    fuel_savings = original_fuel - new_fuel

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
            leaving_point = self.calc_leaving_point(target_agent)
            original_time = calc_distance(self.pos, self.destination) / self.speed

            # WARNING: If you change the way the leaving- and joining-points are calculated, you should change this formula accordingly!

        else:
            if len(self.agents_in_my_formation) > 0 and len(target_agent.agents_in_my_formation) > 0:
                raise Exception("This function is not advanced enough to handle two formations joining")

            if len(self.agents_in_my_formation) > 0 and len(target_agent.agents_in_my_formation) == 0:
                formation_leader = self
                formation_joiner = target_agent
                original_time = (calc_distance(self.pos, self.leaving_point) + calc_distance(self.leaving_point,
                                                                                             self.destination)) / self.speed

            elif len(self.agents_in_my_formation) == 0 and len(target_agent.agents_in_my_formation) > 0:
                formation_leader = target_agent
                formation_joiner = self
                original_time = calc_distance(self.pos, self.destination) / self.speed

            joining_point = self.calc_joining_point(formation_leader.pos, formation_joiner.pos)
            leaving_point = formation_leader.leaving_point

        if calc_distance(self.pos, joining_point) > 0.001:
            joining_time = calc_distance(self.pos, joining_point) / self.calc_speed_to_joining_point(target_agent)
        else:
            joining_time = 0
        if calc_distance(leaving_point, self.destination) > 0.001:
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

        self.joining_point = self.calc_joining_point(self.pos, target_agent.pos)
        self.speed_to_joining = self.calc_speed_to_joining_point(target_agent)

        involved_agents = [self]
        for agent in self.agents_in_my_formation:
            involved_agents.append(agent)  # These are the current formation agents

        for agent in involved_agents:
            agent.agents_in_my_formation.append(target_agent)
            agent.formation_state = "adding_to_formation"

        if target_agent in involved_agents:
            raise Exception("This is not correct")

        bid_receivers = bid_value / (len(
            self.agents_in_my_formation) + 1)
        self.deal_value += bid_receivers
        for agent in self.agents_in_my_formation:
            agent.deal_value += bid_receivers
        target_agent.deal_value -= bid_value

        target_agent.formation_state = "committed"

        potential_fuel_saved = self.calculate_potential_fuelsavings(target_agent, individual=True)
        self.estimated_fuel_saved += potential_fuel_saved
        target_potential_fuel_saved = target_agent.calculate_potential_fuelsavings(self, individual=True)
        target_agent.estimated_fuel_saved += target_potential_fuel_saved

        potential_delay = self.calculate_potential_delay(target_agent)
        self.estimated_delay += potential_delay
        target_potential_delay = target_agent.calculate_potential_delay(self)
        target_agent.estimated_delay += target_potential_delay

        self.estimated_utility_score += utility_function(potential_fuel_saved + bid_receivers, potential_fuel_saved,
                                                         potential_delay, behavior=self.behavior)
        target_agent.estimated_utility_score += utility_function(target_potential_fuel_saved - bid_value,
                                                                 target_potential_fuel_saved, target_potential_delay,
                                                                 behavior=target_agent.behavior)

        target_agent.agents_in_my_formation = involved_agents[:]
        involved_agents.append(target_agent)

        for agent in involved_agents:
            agent.joining_point = self.joining_point
            agent.leaving_point = self.leaving_point
            agent.speed_to_joining = self.speed_to_joining

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

        if not self.manager and target_agent.auctioneer:
            raise Exception("Something is going wrong")

        if discard_received_bids:
            self.received_bids = []

        if self.distance_to_destination(target_agent.pos) < 0.001:
            # Edge case where agents are at the same spot.
            self.formation_state = "in_formation"
            target_agent.formation_state = "in_formation"
            self.accepting_bids = True

        else:
            self.joining_point = self.calc_joining_point(self.pos, target_agent.pos)

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

        self.leaving_point = self.calc_joining_point(self.destination, target_agent.destination)
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
                if agent.accepting_bids == 1:
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
                print(
                    f"Flight {self.unique_id} arrived at {self.real_arrival} with a delay of {self.delay}, saving {self.real_fuel_saved} fuel.")
                self.state = "arrived"

        elif self.model.schedule.steps >= self.departure_time:
            # The agent only starts flying if it is at or past its departure time.
            self.state = "flying"

            if self.formation_state == "in_formation" and self.distance_to_destination(
                    self.leaving_point) <= self.speed / 2:
                # If agent is in formation & close to leaving-point, leave the formation
                self.state = "flying"
                self.formation_state = "no_formation"
                self.agents_in_my_formation = []

            if (self.formation_state == "committed" or self.formation_state == "adding_to_formation") and \
                    self.distance_to_destination(self.joining_point) <= self.speed_to_joining / 2:
                # If the agent reached the joining point of a new formation, 
                # change status to "in formation" and start accepting new bids again.
                self.formation_state = "in_formation"
                self.accepting_bids = True

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

        joining_point = self.calc_joining_point(neighbor.pos)
        # Am I stupid, or dist_self and are literally the same in the original code?
        dist_self = ((joining_point[0] - self.pos[0]) ** 2 + (joining_point[1] - self.pos[1]) ** 2) ** 0.5
        dist_neighbor = ((joining_point[0] - neighbor.pos[0]) ** 2 + (joining_point[1] - neighbor.pos[1]) ** 2) ** 0.5
        try:
            if abs(1 - dist_self / dist_neighbor) > 0.001:
                # If this exception is thrown, it means that the joining point is
                # not at equal distances from both aircraft.
                raise Exception("Joining point != middle point")
        except FloatingPointError as err:
            # What if self and neighbor take off from the same airport at the same time, and thus dist_self and dist_neighbor are 0?
            if dist_self == 0 and dist_neighbor == 0:
                pass
            else:
                print(dist_self, dist_neighbor)
                raise err
        try:
            rest = dist_self % self.speed
            regular_time = math.floor(dist_self / self.speed)
            if rest > 0:
                time = regular_time + 1
            elif rest == 0:
                time = regular_time
            return (dist_self / time)
        except FloatingPointError as err:
            # What if self and neighbor take off from the same airport at the same time, and thus dist_self and dist_neighbor are 0?
            if dist_self == 0 and dist_neighbor == 0:
                return 0.0
            else:
                print(self.pos, neighbor.pos)
                print(dist_self, dist_neighbor)
                print(regular_time, rest)
                raise err

    def calc_joining_point(self, target_agent):
        # middle point between self and target location
        mid_point1 = calc_middle_point(self.pos, target_agent.pos)
        # middle point between self and target destination
        mid_point2 = calc_middle_point(self.destination, target_agent.destination)
        # original distance from current position to middle point
        # b_magn = calc_distance(self.pos, mid_point1)

        # vector a is middle point to current position
        a_vec = calc_vector(mid_point1, self.pos)
        # vector b is from middle point to destination middle point (same for both self and target, because middle point)
        b_vec = calc_vector(mid_point1, mid_point2)
        # alfa is angle between self and vector from mid point to mid point
        alfa = calc_angle(a_vec, b_vec)

        # try 40000: vary potential point B (is new meeting point)
        unity_vector = np.array([np.sin(alfa), np.cos(alfa)])
        # point b was meeting point in my original drawings
        potential_b = np.zeros((100, 2))
        route_length = np.zeros(100)
        total_route_length = np.zeros(100)
        route_length_target = np.zeros(100)

        for i in range(100):
            potential_b[i] = unity_vector * i
            route_length[i] = calc_distance(self.pos, potential_b[i]) + 0.75 * calc_distance(potential_b[i], mid_point2)
            route_length_target[i] = calc_distance(target_agent.pos, potential_b[i]) + 0.75 * calc_distance(
                potential_b[i],
                mid_point2)
            total_route_length[i] = route_length[i] + route_length_target[i]

        combined_list = np.column_stack((potential_b, total_route_length))

        shortest_route = 10000
        opt_joining_point = (0, 0)
        for i in range(len(combined_list)):
            if total_route_length[i] < shortest_route:
                shortest_route = total_route_length[i]
                opt_joining_point = potential_b[i]
            else:
                shortest_route = total_route_length[i-1]
                opt_joining_point = potential_b[i-1]
        print(opt_joining_point)
        return opt_joining_point

    def calc_leaving_point(self, target_agent):
        # middle point between self and target location
        mid_point1 = calc_middle_point(self.pos, target_agent.pos)
        # middle point between self and target destination
        mid_point2 = calc_middle_point(self.destination, target_agent.destination)
        # original distance from current position to middle point
        # b_magn = calc_distance(self.pos, mid_point1)

        # vector a is middle point (at end) to destination
        a_vec = calc_vector(mid_point2, self.destination)
        # vector b is from middle point to destination middle point (same for both self and target, because middle point)
        b_vec = calc_vector(mid_point2, mid_point1)
        # alfa is angle between self and vector from mid point to mid point
        alfa = calc_angle(a_vec, b_vec)
        # try 40000: vary potential point B (is new meeting point)
        unity_vector = np.array([np.sin(alfa), np.cos(alfa)])
        # point b was meeting point in my original drawings
        potential_b = np.zeros((100, 2))
        route_length = np.zeros(100)
        total_route_length = np.zeros(100)
        route_length_target = np.zeros(100)

        for i in range(100):
            potential_b[i] = unity_vector * i
            route_length[i] = calc_distance(self.destination, potential_b[i]) + 0.75 * calc_distance(potential_b[i], mid_point1)
            route_length_target[i] = calc_distance(target_agent.des, potential_b[i]) + 0.75 * calc_distance(
                potential_b[i],
                mid_point1)
            total_route_length[i] = route_length[i] + route_length_target[i]

        combined_list = np.column_stack((potential_b, total_route_length))

        shortest_route = 10000
        opt_leaving_point = (0, 0)
        for i in range(len(combined_list)):
            if total_route_length[i] < shortest_route:
                shortest_route = total_route_length[i]
                opt_leaving_point = potential_b[i]

        #print(opt_leaving_point)
        return opt_leaving_point
