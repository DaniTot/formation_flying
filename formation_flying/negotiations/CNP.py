# =============================================================================
# This file contains the function to do Contract Net Protocol (CNP). 
# =============================================================================

# def do_CNP(flight):
#     # the do_CNP function takes a flight-agent object
from ..miscellaneous import calc_distance, utility_function
from random import choices


class CNP:
    def __init__(self, flight):
        self.flight = flight

        # Own status
        self.first_step = True
        # self.behavior = choices(["budget", "green", "express", "balanced"], weights=[1, 0, 0, 0], k=1)[0]
        self.free_flights_in_reach = []
        self.pending_bids = {}

        # Received communications from other agents
        self.received_neighbor_counts = []
        self.managers_calling = []

        # Properties
        self.negotiation_window = 10 # The time available for negotiation. Call for contract expires after this duration.
        self.bidding_end_time = None

    def do_cnp(self):
        # print()
        # Only evaluate role from the second step onwards
        if self.first_step is True:
            self.first_step = False
        elif len(self.received_neighbor_counts) > 0:
            self.evaluate_role()
        # Role specific activities
        if self.flight.manager == 1:
            self.do_manager()
        elif self.flight.manager == 0:
            self.do_contractor()

    # Negotiation activities for manager agents
    def do_manager(self):
        print(f"{self.flight.unique_id} does manager")
        # Do not call for contract, while picking up an accepted agent.
        if self.flight.formation_state not in ("committed", "adding_to_formation"):
            # Do not call for contract, when already close to destination
            if  not calc_distance(self.flight.pos, self.flight.destination)/self.flight.speed <= self.negotiation_window:
                self.call_for_contract()
                print(f"{self.flight.unique_id} calls for contract with deadline {self.bidding_end_time}")
            else:
                # By setting the bid end time to the past, the manager will be demoted to contractor at the end of its turn
                self.bidding_end_time = self.flight.model.schedule.steps - 1

        # Select a contractor
        # Find the highest bid
        current_bids = []
        for bid in self.flight.received_bids:
            if bid["validity"] is True:
                current_bids.append(bid)
                # Change the validity to false, so every bid is considered only once.
                bid["validity"] = False
        if len(current_bids) > 0:
            highest_bid = None
            highest_utility = None
            print(f"{self.flight.agent_type}, {self.flight.unique_id} received {len(current_bids)} new bids.")
            for bid in current_bids:
                # print(f"Contractor {bid['bidding_agent'].agent_type, bid['bidding_agent'].unique_id}'s bid: {bid['value']}")
                bid_saving = self.flight.calculate_potential_fuelsavings(bid["bidding_agent"], individual=True)
                bid_share = bid["value"] / (len(self.flight.agents_in_my_formation) + 1)
                bid_delay = self.flight.calculate_potential_delay(bid["bidding_agent"])
                bid_utility = utility_function(bid_saving + bid_share, bid_saving, bid_delay, behavior=self.flight.behavior)
                print(f"Manager {self.flight.unique_id} is considering bid of {bid['value']} from {bid['bidding_agent'].unique_id} for utility {bid_utility}")
                if highest_bid is None:
                    highest_bid = bid.copy()
                    highest_utility = bid_utility
                else:
                    if bid_utility > highest_utility:
                        highest_bid = bid.copy()
                        highest_utility = bid_utility

            # Communicate refusal to the rest of the contractor agents
            for bid in current_bids:
                if bid["bidding_agent"] is not highest_bid["bidding_agent"]:
                    try:
                        bid["bidding_agent"].cnp.pending_bids[self.flight]["accepted"] = False
                    except KeyError as err:
                        print()
                        print(bid["bidding_agent"].agent_type, bid["bidding_agent"].unique_id, bid["value"])
                        print(bid["bidding_agent"].cnp.pending_bids)
                        print(self.flight, bid["bidding_agent"].cnp.pending_bids.keys())
                        print(self.flight in bid["bidding_agent"].cnp.pending_bids.keys())
                        print(bid["bidding_agent"].cnp.pending_bids[self.flight])
                        raise err

            # Check if the highest bid meets the acceptance strategy requirements.
            # If a formation is formed, reset received_bids and pending_bids
            if self.acceptance_strategy(highest_bid["bidding_agent"], highest_bid["value"]) is True:
                if len(self.flight.agents_in_my_formation) > 0:
                    self.flight.add_to_formation(list(highest_bid.values())[0],
                                                 list(highest_bid.values())[1], discard_received_bids=True)
                else:
                    self.flight.start_formation(list(highest_bid.values())[0],
                                                list(highest_bid.values())[1], discard_received_bids=True)
                # Communicate acceptance to the contractor agent
                highest_bid["bidding_agent"].cnp.pending_bids[self.flight]["accepted"] = True
                self.bidding_end_time = None
                self.flight.accepting_bids = 0
                print(f"{self.flight.agent_type}, {self.flight.unique_id} selected {highest_bid['bidding_agent'].unique_id}'s bid: {highest_bid['value']}")
            else:
                # Communicate refusal to the contractor agent
                try:
                    highest_bid["bidding_agent"].cnp.pending_bids[self.flight]["accepted"] = False
                except KeyError as err:
                    print()
                    print(highest_bid["bidding_agent"].agent_type, highest_bid["bidding_agent"].unique_id, highest_bid["value"])
                    print(highest_bid["bidding_agent"].cnp.pending_bids)
                    print(self.flight.unique_id, [k.unique_id for k in highest_bid["bidding_agent"].cnp.pending_bids.keys()])
                    print(self.flight in highest_bid["bidding_agent"].cnp.pending_bids.keys())
                    print(highest_bid["bidding_agent"].cnp.pending_bids[self.flight])
                    raise err

        # Change manager to contractor if it couldn't form a formation by the end of the negotiation window
        elif self.flight.formation_state is "no_formation" and self.bidding_end_time < self.flight.model.schedule.steps:
            self.bidding_end_time = None
            self.flight.accepting_bids = 0
            self.flight.manager = 0
            self.flight.received_bids = []
            self.flight.update_role()
            print(f"Flight {self.flight.unique_id} got demoted to contractor.")
        return

    # Negotiation activities for contractor agents
    def do_contractor(self):
        print(f"{self.flight.unique_id} does contractor")
        # Process any responses to pending bids in pending_bids:
        # A copy of the bids must be created, in order to avoide issuesby removing dict entries while looping.
        refused_bids = []
        accepted_bids = []
        for manager in self.pending_bids:
            if self.pending_bids[manager]["accepted"] is True:
                accepted_bids.append(manager)
                print(f"Contractor {self.flight.unique_id}'s bid to Manager {manager.unique_id} was accepted")
            elif self.pending_bids[manager]["accepted"] is False:
                refused_bids.append(manager)
                print(f"Contractor {self.flight.unique_id}'s bid to Manager {manager.unique_id} was refused")
        assert len(accepted_bids) <= 1, f"Multiple bids of Flight {self.flight.unique_id} have " \
                                        f"been accepted."
        # Remove refused bids from pending_bids
        for manager in refused_bids:
            self.pending_bids.pop(manager)
        # Remove accepted bid from pending_bids
        if len(accepted_bids) > 0:
            self.pending_bids.pop(accepted_bids[0])
        assert len(self.pending_bids) == 0, self.pending_bids

        # Make a bid.
        # Since bids are binding, there may only be one bid at a time, so only consider the most profitable manager
        if self.flight.formation_state is "no_formation" and len(self.managers_calling) >= 1:
            utility_score = 0
            selected_manager = None
            selected_bid = 0
            for i, [manager, end_time] in enumerate(self.managers_calling):
                if manager.accepting_bids == 1 and end_time >= self.flight.model.schedule.steps:
                    fuel_saving = self.flight.calculate_potential_fuelsavings(manager, individual=True)
                    delay = self.flight.calculate_potential_delay(manager)
                    bidding_value = self.bidding_strategy(fuel_saving, delay, end_time)
                    profit = fuel_saving - bidding_value
                    if utility_function(profit, fuel_saving, delay, behavior=self.flight.behavior) > utility_score:
                        utility_score = utility_function(profit, fuel_saving, delay, behavior=self.flight.behavior)
                        selected_manager = manager
                        selected_bid = bidding_value
                # Remove the expired calls
                elif end_time < self.flight.model.schedule.steps:
                    self.managers_calling.pop(i)
            print(f"Contractor {self.flight.unique_id} has {len(self.managers_calling)} open calls.")

            if selected_manager is not None:
                # TODO: Implement bid expiration date. Currently None.
                self.flight.make_bid(selected_manager, selected_bid, True, None)
                print(self.flight.agent_type, self.flight.unique_id, "makes bid to", selected_manager.unique_id, "with value of", selected_bid, "and potential utility of", utility_score)
                # Save the bid that was made, so it can be used in the bidding strategy
                self.pending_bids[selected_manager] = {"bid": selected_bid,
                                                       "time": self.flight.model.schedule.steps,
                                                       "accepted": None}

        # If there are no currently pending bids, check if contractor agent can become a manager
        elif self.flight.formation_state is "no_formation" and len(self.pending_bids) == 0:
            # Do not apply for manager, once close to destination, as you wouldn't be able to call for contract anyway
            if not calc_distance(self.flight.pos, self.flight.destination) / self.flight.speed <= self.negotiation_window:
                print(f"Contractor {self.flight.unique_id} applying for manager")
                self.apply_for_manager()

    def bidding_strategy(self, fuel_saving, delay, end_time, min_utility_frac=0.50, kappa=0, beta=1):
        # Time-dependent tactics
        # Find the maximum possible utility (at 0 bid)
        max_utility = utility_function(fuel_saving, fuel_saving, delay, behavior=self.flight.behavior)
        min_utility = max_utility*min_utility_frac
        # Find the highest possible bid for minimum acceptable utility score
        highest_bid = 0
        while utility_function(fuel_saving - highest_bid, fuel_saving, delay, behavior=self.flight.behavior) > min_utility:
            highest_bid += 10
        highest_bid -= 10
        while utility_function(fuel_saving - highest_bid, fuel_saving, delay, behavior=self.flight.behavior) > min_utility:
            highest_bid += 1
        highest_bid -= 1
        # TODO: check if the -= part is actually correct
        print(f"Highest bid {highest_bid}, resulting to utility {utility_function(fuel_saving - highest_bid, fuel_saving, delay, behavior=self.flight.behavior)}, compared to min utility {min_utility}")
        # print(f"Flight {self.flight.unique_id} utility score: {utility_function(fuel_saving - highest_bid, fuel_saving, delay, behavior=self.flight.behavior)}, with highest bid {highest_bid}")

        alpha = kappa + (1 - kappa) * (min([self.flight.model.schedule.steps, end_time]) / end_time)**(1/beta)
        return highest_bid*alpha

    def acceptance_strategy(self, bidding_agent, bid_value, min_utility=880):
        # Combination of constant and time based strategy, where the constant
        fuel_saving = self.flight.calculate_potential_fuelsavings(bidding_agent, individual=True)
        bid_receive = bid_value/(len(self.flight.agents_in_my_formation) + 1)
        delay = self.flight.calculate_potential_delay(bidding_agent)
        potential_utility = utility_function(fuel_saving + bid_receive, fuel_saving, delay, behavior=self.flight.behavior)
        current_min_utility = min_utility/(self.flight.model.schedule.steps - self.bidding_end_time + self.negotiation_window + 1)
        if potential_utility >= current_min_utility:
            print(f"Bid from {bidding_agent.unique_id} of utility {potential_utility} accepted by {self.flight.unique_id} as min utility is {current_min_utility}")
            return True
        else:
            print(f"Bid from {bidding_agent.unique_id} of utility {potential_utility} refused by {self.flight.unique_id} as min utility is {current_min_utility}")
            return False

    def apply_for_manager(self):
        # Look for neighboring contractor flights that don't have a formation yet.
        for neighbor in self.flight.model.space.get_neighbors(pos=self.flight.pos,
                                                              radius=self.flight.communication_range,
                                                              include_center=True):
            if neighbor.agent_type == "Flight" and neighbor.unique_id != self.flight.unique_id and neighbor.manager == 0 and neighbor.formation_state is "no_formation":
                self.free_flights_in_reach.append(neighbor)
        # Contact the neighboring free agents
        for neighbor in self.free_flights_in_reach:
            if neighbor.manager == 0:
                neighbor.cnp.received_neighbor_counts.append(len(self.free_flights_in_reach))
        return

    def evaluate_role(self):
        # If a tie occurs, follow the order of flights processed/generated/take off.
        # Check if there are neighbors that already took manager role
        manager_taken = False
        for neighbor in self.free_flights_in_reach:
            if neighbor.manager == 1:
                manager_taken = True
                print(self.flight.agent_type, self.flight.unique_id, f"stays contractor, {neighbor.unique_id} is already manager.")
                break
        if len(self.free_flights_in_reach) >= max(self.received_neighbor_counts) and manager_taken is False:
            self.flight.manager = 1
            print(self.flight.agent_type, self.flight.unique_id, "becomes manager")
        else:
            # Promote some contractors randomly to managers, in order to allow for formations that otherwise wouldn't form.
            if choices([True, False], weights=[1, 3*self.negotiation_window], k=1)[0]:
                self.flight.manager = 1
                print(self.flight.agent_type, self.flight.unique_id, "becomes manager by chance.")
            else:
                self.flight.manager = 0
                print(self.flight.agent_type, self.flight.unique_id, "stays contractor")
        # After evaluation, reset the relevant lists, and update the role
        self.free_flights_in_reach = []
        self.received_neighbor_counts = []
        self.flight.update_role()
        return

    def call_for_contract(self):
        if self.bidding_end_time is None:
            self.bidding_end_time = self.flight.model.schedule.steps + self.negotiation_window
            self.flight.accepting_bids = 1
        for neighbor in self.flight.model.space.get_neighbors(pos=self.flight.pos,
                                                              radius=self.flight.communication_range,
                                                              include_center=True):
            if neighbor.agent_type == "Flight" and neighbor.unique_id != self.flight.unique_id and neighbor.manager == 0 and neighbor.formation_state is "no_formation":
                # Also invite newly available contractors to the ongoing negotiation
                new_contractor = True
                for call in neighbor.cnp.managers_calling:
                    if call[0] == self.flight:
                        new_contractor = False
                if new_contractor:
                    neighbor.cnp.managers_calling.append([self.flight, self.bidding_end_time])
        return


