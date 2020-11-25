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
        self.leading_exiting_bidder = {"bidder": None, "bid": 0}
        self.min_reserve_utility_frac = 0.7

        # Properties
        self.auction_joining_timeframe = 10  # Time available for contractors to enter the auction before it begins
        self.auction_start_time = None
        # TODO: consider implementing a more elaborate reserve price system
        self.reserve_price = 0

        # TODO: better manager selection
        # Select manager at random
        if choices([False, True], weights=[5, 1])[0]:
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
            if self.auction_start_time is None or self.auction_start_time > self.flight.model.schedule.steps:
                self.call_for_bidders()

            # If there is at least one bidder willing to join the auction by the end of the joining timeframe,
            # create the auction
            if self.auction_start_time == self.flight.model.schedule.steps:
                if len(self.contractors_in_auction) > 0:
                    self.create_auction()
                # If no flights are interested joining a formation with the manager, demote the manager
                else:
                    print(f"Flight {self.flight.unique_id} failed to to find auctioneers by the deadline {self.auction_start_time}")
                    self.demote()

            # Wait until the auction start time, and make sure manager did not get demoted in the meanwhile
            if self.flight.manager == 1 and self.auction_start_time <= self.flight.model.schedule.steps:
                print(f"Flights in {self.flight.unique_id}'s auction:", [c.unique_id for c in self.contractors_in_auction])
                # If multiple contractors are still in the auction, increase the displayed price
                if len(self.contractors_in_auction) > 1:
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
                    print(
                        f"Last man standing: {self.contractors_in_auction[0].unique_id} won the auction, with price {self.display_price}")
                    self.reset_attributes()
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
                    print(f"Highest exit: {self.leading_exiting_bidder['bidder'].unique_id} won the auction, "
                          f"with price {self.leading_exiting_bidder['bid']}")
                    self.reset_attributes()
        return

    def do_contractor(self):
        # Since bids are binding, there may only be one bid at a time, so only enter the most profitable auction
        if self.flight.formation_state is "no_formation" and self.current_auction is None:
            if len(self.open_auctions) >= 1:
                # print(f"Flight {self.flight.unique_id} considering {len(self.open_auctions)} auctions")
                for i, [manager, start_time] in enumerate(self.open_auctions):
                    if start_time > self.flight.model.schedule.steps:
                        fuel_saving = self.flight.calculate_potential_fuelsavings(manager, individual=True)
                        delay = self.flight.calculate_potential_delay(manager)
                        bidding_value = manager.japanese.display_price
                        profit = fuel_saving - bidding_value
                        utility = utility_function(profit, fuel_saving, delay, behavior=self.flight.behavior)
                        # print(f"{manager.unique_id}'s auction: {utility, self.favored_auction['utility']}")
                        if utility > self.favored_auction["utility"]:
                            self.favored_auction["utility"] = utility
                            self.favored_auction["manager"] = manager
                            self.favored_auction["start_time"] = start_time
                        elif self.favored_auction["manager"] is not None and self.favored_auction["manager"] == manager:
                            # Update the utility of the currently favored manager
                            self.favored_auction["utility"] = utility
                    # Remove the expired calls
                    elif start_time <= self.flight.model.schedule.steps:
                        removed = self.open_auctions.pop(i)
                        print(f"Removed: {removed[0].unique_id}'s auction due {removed[1]} exceeded current time {self.flight.model.schedule.steps}")
                # print(f"Contractor {self.flight.unique_id} has {len(self.open_auctions)} open calls.")

            if self.favored_auction["manager"] is not None:
                # Wait until the last moment to enter an auction, in case a better one comes up
                if self.favored_auction["start_time"] - 1 == self.flight.model.schedule.steps:
                    self.favored_auction["manager"].japanese.enter_auction(self.flight)
                    self.current_auction = self.favored_auction["manager"]

            else:
                # No favorable manager, try for promotion
                # TODO: better manager selection
                if choices([False, True], weights=[5, 1])[0]:
                    self.promote()

        # Decide whether to exit or remain in the current auction
        elif self.flight.formation_state is "no_formation" and self.current_auction.accepting_bids == 1:
            fuel_saving = self.flight.calculate_potential_fuelsavings(self.current_auction, individual=True)
            delay = self.flight.calculate_potential_delay(self.current_auction)
            bidding_value = self.current_auction.japanese.display_price
            profit = fuel_saving - bidding_value
            # Recalculate the minimum utility that can be accepted
            max_utility = utility_function(fuel_saving, fuel_saving, delay, behavior=self.flight.behavior)
            min_utility = max_utility * self.min_bid_utility_frac
            # print(f"Flight {self.flight.unique_id} is considering {self.current_auction.unique_id}'s auction: "
            #       f"min utility: {min_utility}; "
            #       f"potential utility: {utility_function(profit, fuel_saving, delay, behavior=self.flight.behavior)}")
            # Exit the auction if display bid results in a utility lower than the minimum utility
            if utility_function(profit, fuel_saving, delay, behavior=self.flight.behavior) < min_utility:
                # Find the bid corresponding to the minimum utility
                exit_bid = 0
                while utility_function(fuel_saving - exit_bid, fuel_saving, delay,
                                       behavior=self.flight.behavior) > min_utility:
                    exit_bid += 10
                exit_bid -= 10
                while utility_function(fuel_saving - exit_bid, fuel_saving, delay,
                                       behavior=self.flight.behavior) > min_utility:
                    exit_bid += 1
                exit_bid -= 1
                # TODO: fixed(?) calculation, if works, check if CNP needs it too
                # Exit the auction with the exit bid
                self.current_auction.japanese.exit_auction(self.flight, exit_bid)
                # Reset attributes
                self.reset_attributes()
        # else:
        #     assert self.flight.formation_state is not "no_formation" or self.current_auction.accepting_bids == 1, f"{self.flight.unique_id}, {self.flight.formation_state}, {self.current_auction.unique_id}, {self.current_auction.accepting_bids}"
        return

    def call_for_bidders(self):
        if self.auction_start_time is None:
            self.flight.accepting_bids = 0
            self.auction_start_time = self.flight.model.schedule.steps + self.auction_joining_timeframe
            self.reserve_price = self.set_reserve_price(dynamic_price=True)
            self.display_price = self.reserve_price
            print(f"Flight {self.flight.unique_id} scheduled auction to {self.auction_start_time}, and display price {self.display_price}")
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
                    # print(f"Flight {self.flight.unique_id} invited {neighbor.unique_id} for the auction at {self.auction_start_time} with display price {self.display_price}")
        return

    def create_auction(self):
        self.flight.accepting_bids = 1
        self.leading_exiting_bidder = {"bidder": None, "bid": 0}
        self.contractors_dropped_out = []
        return

    def increase_price(self):
        # Increase the show price by 10% of the reserve price
        self.display_price += self.reserve_price*0.3
        print(f"Flight {self.flight.unique_id} increases display price to {self.display_price}")
        return

    def exit_auction(self, bidder, exit_bid):
        print(f"Flight {bidder.unique_id} is exiting {self.flight.unique_id}'s auction, with an exit bid of {exit_bid}")
        self.contractors_in_auction.remove(bidder)
        self.contractors_dropped_out.append(bidder)
        if exit_bid > self.leading_exiting_bidder["bid"]:
            self.leading_exiting_bidder["bidder"] = bidder
            self.leading_exiting_bidder["bid"] = exit_bid

    def enter_auction(self, bidder):
        # print(f"{bidder.unique_id} entering auction: {self.flight.model.schedule.steps, self.auction_start_time, bidder not in self.contractors_dropped_out}")
        if self.flight.model.schedule.steps < self.auction_start_time:
            if bidder not in self.contractors_dropped_out:
                self.contractors_in_auction.append(bidder)
                print(f"{bidder.flight.agent_type}, {bidder.flight.unique_id}, enters auction of {self.flight.unique_id}")

    def demote(self):
        self.flight.manager = 0
        self.flight.update_role()
        self.reset_attributes()
        print(f"Flight {self.flight.unique_id} is demoted to contractor")

    def promote(self):
        self.flight.manager = 1
        self.flight.update_role()
        self.reset_attributes()
        print(f"Flight {self.flight.unique_id} is promoted to manager")

    def reset_attributes(self):
        self.free_flights_in_reach = []
        self.received_neighbor_counts = []
        self.open_auctions = []
        self.current_auction = None
        self.favored_auction = {"manager": None, "utility": 0, "start_time": None}

        self.contractors_in_auction = []
        self.contractors_dropped_out = []
        self.display_price = None
        self.leading_exiting_bidder = {"bidder": None, "bid": 0}
        self.auction_start_time = None
        self.reserve_price = 0

    def set_reserve_price(self, dynamic_price=True):
        # The reserve price must be low enough to attract bidders
        if dynamic_price:

            # From neighbor contractors, find the one that would provide the highest utility in formation
            max_utility = 0
            best_neighbor = None
            for neighbor in self.flight.model.space.get_neighbors(pos=self.flight.pos,
                                                                  radius=self.flight.communication_range,
                                                                  include_center=True):
                if neighbor.agent_type == "Flight" and neighbor.unique_id != self.flight.unique_id and neighbor.manager == 0 and neighbor.formation_state is "no_formation":
                    fuel_saved = self.flight.calculate_potential_fuelsavings(neighbor, individual=True)
                    delay = self.flight.calculate_potential_delay(neighbor)
                    if utility_function(fuel_saved, fuel_saved, delay, behavior=self.flight.behavior) > max_utility:
                        max_utility = utility_function(fuel_saved, fuel_saved, delay, behavior=self.flight.behavior)
                        best_neighbor = neighbor

            # Find the bid that contractor would need to pay for positive utility -> this will be the reserve price
            if best_neighbor is not None:
                reserve_price = 0
                fuel_saving = self.flight.calculate_potential_fuelsavings(best_neighbor, individual=True)
                bid_receive = reserve_price / (len(self.flight.agents_in_my_formation) + 1)
                delay = self.flight.calculate_potential_delay(best_neighbor)
                while utility_function(fuel_saving + bid_receive, fuel_saving, delay,
                                       behavior=self.flight.behavior) < 0:
                    reserve_price += 10
                    bid_receive = reserve_price / (len(self.flight.agents_in_my_formation) + 1)
                reserve_price -= 10
                while utility_function(fuel_saving + bid_receive, fuel_saving, delay,
                                       behavior=self.flight.behavior) < 0:
                    reserve_price += 1
                    bid_receive = reserve_price / (len(self.flight.agents_in_my_formation) + 1)
                reserve_price -= 1

            # If that bid is smaller than 10, set the reserve price to 10
            if best_neighbor is None or reserve_price < 10:
                reserve_price = 10

        else:
            # Static reserve price
            reserve_price = 30

        self.reserve_price = reserve_price
        return reserve_price
