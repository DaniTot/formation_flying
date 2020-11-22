'''
# =============================================================================
# This file contains the function to do a Japanese auction. 
# =============================================================================
'''
from ..miscellaneous import calc_distance, utility_function, calc_middle_point
from random import choices
import numpy as np


class Japanese:
    def __init__(self, flight):
        self.flight = flight

        # Own status
        self.first_step = True
        self.free_flights_in_reach = []
        self.received_neighbor_counts = []

        self.open_auctions = []
        self.favored_auction = {"manager": None, "utility": 0, "start_time": None}
        self.current_auction = None
        self.min_bid_utility_frac = 0.5

        self.contractors_in_auction = []
        self.contractors_dropped_out = []
        self.display_price = None
        self.leading_exiting_bidder = {"bidder": None, "bid": None}
        self.min_reserve_utility_frac = 0.7

        # Properties
        self.auction_joining_timeframe = 10  # Time available for contractors to enter the auction before it begins
        self.auction_start_time = None
        # TODO: consider implementing a more elaborate reserve price system
        self.reserve_price = 30

        # TODO: better manager selection
        # Select manager at random
        if choices([False, True], weights=[5, 1]):
            self.promote()
        else:
            self.demote()
        return

    def do_japanese(self):
        # Role specific activities
        if self.flight.manager == 1:
            self.do_manager()
        elif self.flight.manager == 0:
            self.do_contractor()

        return

    def do_manager(self):
        # If manager is not in the process of joining up with committed flights,
        # and has no ongoing auction yet, invite potential bidders
        if self.flight.formation_state is not "committed":
            if self.auction_start_time is None or self.auction_start_time < self.flight.model.schedule.steps:
                self.call_for_bidders()

        # If there is at least one bidder willing to join the auction by the end of the joining timeframe,
        # create the auction
        # TODO: Create a time frame in which contractors can join an auction
        if self.auction_start_time == self.flight.model.schedule.steps:
            if len(self.contractors_in_auction) > 0:
                self.create_auction()
            # If no flights are interested joining a formation with the manager, demote the manager
            else:
                self.demote()
        
        # If multiple contractors are still in the auction, increase the displayed price
        if len(self.contractors_in_auction) >= 1:
            self.increase_price()
        # If only a single contractor is still in the auction,
        # that conctractor won the deal with the current display price
        elif len(self.contractors_in_auction) == 1:
            if len(self.flight.agents_in_my_formation) > 0:
                self.flight.add_to_formation(self.contractors_in_auction[0], self.display_price,
                                             discard_received_bids=True)
            else:
                self.flight.start_formation(self.contractors_in_auction[0], self.display_price,
                                            discard_received_bids=True)
        # If multiple contractors exited the auction at the same display price,
        # select the one that submitted the highest exiting price
        elif len(self.contractors_in_auction) == 0 and self.leading_exiting_bidder["bid"] is not None:
            if len(self.flight.agents_in_my_formation) > 0:
                self.flight.add_to_formation(self.leading_exiting_bidder["bidder"],
                                             self.leading_exiting_bidder["bid"],
                                             discard_received_bids=True)
            else:
                self.flight.start_formation(self.leading_exiting_bidder["bidder"],
                                            self.leading_exiting_bidder["bid"],
                                            discard_received_bids=True)
        return

    def do_contractor(self):
        # Since bids are binding, there may only be one bid at a time, so only enter the most profitable auction
        if self.flight.formation_state is "no_formation" and self.current_auction is None:
            if len(self.open_auctions) >= 1:
                for i, [manager, start_time] in enumerate(self.open_auctions):
                    if manager.accepting_bids == 1 and start_time < self.flight.model.schedule.steps:
                        fuel_saving = self.flight.calculate_potential_fuelsavings(manager, individual=True)
                        delay = self.flight.calculate_potential_delay(manager)
                        bidding_value = manager.japanese.display_price
                        profit = fuel_saving - bidding_value
                        if utility_function(profit, fuel_saving, delay, behavior=self.flight.behavior) > self.favored_auction["utility"]:
                            self.favored_auction["utility"] = utility_function(profit, fuel_saving, delay, behavior=self.flight.behavior)
                            self.favored_auction["manager"] = manager
                            self.favored_auction["start_time"] = start_time
                    # Remove the expired calls
                    elif start_time >= self.flight.model.schedule.steps:
                        self.open_auctions.pop(i)
                print(f"Contractor {self.flight.unique_id} has {len(self.open_auctions)} open calls.")

                if self.favored_auction["manager"] is not None:
                    # Wait until the last moment to enter an auction, in case a better one comes up
                    if self.favored_auction["start_time"] - 1 == self.flight.model.schedule.steps:
                        self.favored_auction["manager"].japanese.enter_auction(self.flight)
                        self.current_auction = self.favored_auction["manager"]
                        print(self.flight.agent_type, self.flight.unique_id, "enters auction of ",
                              self.favored_auction["manager"].unique_id, "with potential utility of",
                              self.favored_auction["utility"])

        # Decide whether to exit or remain in the current auction
        elif self.flight.formation_state is "no_formation" and self.current_auction.accepting_bids == 1:
            fuel_saving = self.flight.calculate_potential_fuelsavings(self.current_auction, individual=True)
            delay = self.flight.calculate_potential_delay(self.current_auction)
            bidding_value = self.current_auction.japanese.display_price
            profit = fuel_saving - bidding_value
            # Recalculate the minimum utility that can be accepted
            max_utility = utility_function(fuel_saving, fuel_saving, delay, behavior=self.flight.behavior)
            min_utility = max_utility * self.min_bid_utility_frac
            # Exit the auction if display bid results in a utility lower than the minimum utility
            if utility_function(profit, fuel_saving, delay, behavior=self.flight.behavior) < min_utility:
                # Find the bid corresponding to the minimum utility
                exit_bid = 0
                while utility_function(fuel_saving - exit_bid, fuel_saving, delay,
                                       behavior=self.flight.behavior) > min_utility:
                    exit_bid += 10
                while utility_function(fuel_saving - exit_bid, fuel_saving, delay,
                                       behavior=self.flight.behavior) > min_utility:
                    exit_bid += 1
                # Exit the auction with the exit bid
                self.current_auction.exit_auction(self.flight, exit_bid)
                # Reset attributes
                self.reset_attributes()
        else:
            assert self.flight.formation_state is not "no_formation" or self.current_auction.accepting_bids == 1
        return

    def call_for_bidders(self):
        if self.auction_start_time is None:
            self.flight.accepting_bids = 0
            self.auction_start_time = self.flight.model.schedule.steps + self.auction_joining_timeframe
            self.display_price = self.reserve_price
        for neighbor in self.flight.model.space.get_neighbors(pos=self.flight.pos,
                                                              radius=self.flight.communication_range,
                                                              include_center=True):
            if neighbor.agent_type == "Flight" and neighbor.unique_id != self.flight.unique_id and neighbor.manager == 0 and neighbor.formation_state is "no_formation":
                # Also invite newly available contractors to the ongoing negotiation
                new_contractor = True
                for call in neighbor.japanese.open_auctions:
                    if call[0] == self.flight:
                        new_contractor = False
                if new_contractor:
                    neighbor.japanese.open_auctions.append([self.flight, self.auction_start_time])
        return

    def create_auction(self):
        self.flight.accepting_bids = 1
        self.leading_exiting_bidder = {"bidder": None, "bid": None}
        self.contractors_in_auction = []
        self.contractors_dropped_out = []
        self.auction_start_time = None
        return

    def increase_price(self):
        # Increase the show price by 10% of the reserve price
        self.display_price += self.reserve_price*0.1
        return

    def exit_auction(self, bidder, exit_bid):
        self.contractors_in_auction.remove(bidder)
        self.contractors_dropped_out.append(bidder)
        if exit_bid > self.leading_exiting_bidder["bid"]:
            self.leading_exiting_bidder["bidder"] = bidder
            self.leading_exiting_bidder["bid"] = exit_bid

    def enter_auction(self, bidder):
        if self.flight.model.schedule.steps < self.auction_joining_timeframe:
            if bidder not in self.contractors_dropped_out:
                self.contractors_in_auction.append(bidder)

    def demote(self):
        self.flight.manager = 0
        self.flight.update_role()
        self.reset_attributes()

    def promote(self):
        self.flight.manager = 1
        self.flight.update_role()
        self.reset_attributes()

    def reset_attributes(self):
        self.free_flights_in_reach = []
        self.received_neighbor_counts = []
        self.open_auctions = []
        self.current_auction = None
        self.favored_auction = {"manager": None, "utility": 0, "start_time": None}

        self.contractors_in_auction = []
        self.contractors_dropped_out = []
        self.display_price = None
        self.leading_exiting_bidder = {"bidder": None, "bid": None}
        self.auction_start_time = None

    def set_reserve_price(self):
        # The reserve price must be low enough to attract bidders
        # Calculate the maximum possible utility with zero bid,
        # i.e.: joining up with flight that is at the same position, and is going to the same destination
        max_fuel_saved = self.flight.calculate_potential_fuelsavings(self.flight, individual=True)
        min_utility = utility_function(max_fuel_saved, max_fuel_saved, 0,
                                       behavior=self.flight.behavior) * self.min_reserve_utility_frac
        # Find the size of bid that will result in the minimum acceptable utility, in the worst case scenario
        # i.e. when the contractor is at the edge of communication range,
        # the furthest away from the manager's destination
        destination_vector = np.array(self.flight.destination) - np.array(self.flight.pos)
        destination_unit_vector = destination_vector / np.linalg.norm(destination_vector)
        worst_contractor_pos = np.array(self.flight.pos) - destination_unit_vector * self.flight.communication_range
        worst_joining_point = calc_middle_point(self.flight.pos, worst_contractor_pos)
        added_distance = calc_distance(self.flight.pos, worst_joining_point)
        reserve_fuel_saved = max_fuel_saved - added_distance
        # It is assumed that the speed to the joining point is the default speed
        added_delay = calc_distance(self.flight.pos, worst_joining_point)/self.flight.speed

        reserve_price = 0
        while utility_function(reserve_fuel_saved - reserve_price, reserve_fuel_saved,
                               added_delay, behavior=self.flight.behavior) > min_utility:
            reserve_price += 10
        while utility_function(reserve_fuel_saved - reserve_price, reserve_fuel_saved,
                               added_delay, behavior=self.flight.behavior) > min_utility:
            reserve_price += 1

        self.reserve_price = reserve_price
        return reserve_price
