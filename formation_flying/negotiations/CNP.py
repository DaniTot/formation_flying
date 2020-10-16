# =============================================================================
# This file contains the function to do Contract Net Protocol (CNP). 
# =============================================================================

# def do_CNP(flight):
#     # the do_CNP function takes a flight-agent object
from ..miscellaneous import calc_distance


class CNP:
    def __init__(self, flight):
        self.flight = flight

        # Own status
        self.first_step = True
        self.free_flights_in_reach = []
        self.pending_bids = {}

        # Received communications from other agents
        self.received_neighbor_counts = []
        self.managers_calling = []

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
        if self.flight.manager == 0:
            self.do_contractor()

    # Negotiation activities for manager agents
    def do_manager(self):
        # Do not call for contract, while picking up an accepted agent.
        if self.flight.formation_state not in ("committed", "adding_to_formation"):
            self.call_for_contract()

        # Select a contractor
        # Find the highest bid
        if len(self.flight.received_bids) > 0:
            highest_bid = None
            print(f"{self.flight.agent_type}, {self.flight.unique_id} received {len(self.flight.received_bids)} bids.")
            for bid in self.flight.received_bids:
                if highest_bid is None:
                    highest_bid = bid
                elif bid["value"] > highest_bid["value"]:
                    # Communicate refusal to the contractor agent
                    highest_bid["bidding_agent"].cnp.pending_bids[self.flight]["accepted"] = False
                    highest_bid = bid
                else:
                    # Communicate refusal to the contractor agent
                    bid["bidding_agent"].cnp.pending_bids[self.flight]["accepted"] = False
            # Check if the highest bid meets the acceptance strategy requirements.
            # If a formation is formed, reset received_bids and pending_bids
            if self.acceptance_strategy(list(highest_bid.values())[0],
                                        list(highest_bid.values())[1],
                                        list(highest_bid.values())[2]) is True:
                if len(self.flight.agents_in_my_formation) > 0:
                    self.flight.add_to_formation(list(highest_bid.values())[0],
                                                 list(highest_bid.values())[1], discard_received_bids=True)
                else:
                    self.flight.start_formation(list(highest_bid.values())[0],
                                                list(highest_bid.values())[1], discard_received_bids=True)
                # Communicate acceptance to the contractor agent
                highest_bid["bidding_agent"].cnp.pending_bids[self.flight]["accepted"] = True
                print(f"{self.flight.agent_type}, {self.flight.unique_id} selected {highest_bid['bidding_agent'].unique_id}'s bid: {highest_bid['value']}")
            else:
                # Communicate refusal to the contractor agent
                highest_bid["bidding_agent"].cnp.pending_bids[self.flight]["accepted"] = False

        # TODO: Change manager to contractor if no contractor is found after a while
        return

    # Negotiation activities for contractor agents
    def do_contractor(self):
        # Process any responses to pending bids in pending_bids:
        # A copy of the bids must be created, in order to avoide issuesby removing dict entries while looping.
        refused_bids = []
        accepted_bids = []
        for manager in self.pending_bids:
            if self.pending_bids[manager]["accepted"] is True:
                accepted_bids.append(manager)
            elif self.pending_bids[manager]["accepted"] is False:
                refused_bids.append(manager)
        assert len(accepted_bids) <= 1, f"Multiple bids of Flight {self.flight.unique_id} have " \
                                        f"been accepted."
        # Remove refused bids from pending_bids
        for manager in refused_bids:
            self.pending_bids.pop(manager)
        # Remove accepted bid from pending_bids
        if len(accepted_bids) > 0:
            self.pending_bids.pop(accepted_bids[0])

        # Make a bid.
        # Since bids are binding, there may only be one bid at a time, so only consider the most profitable manager
        if self.flight.formation_state is "no_formation" and len(self.managers_calling) >= 1:
            profit = 0
            selected_manager = None
            selected_bid = 0
            for manager in self.managers_calling:
                fuel_saving = self.flight.calculate_potential_fuelsavings(manager)
                bidding_value = self.bidding_strategy(fuel_saving)
                if fuel_saving - bidding_value > profit:
                    profit = fuel_saving - bidding_value
                    selected_manager = manager
                    selected_bid = bidding_value
            if selected_manager is not None:
                # TODO: Implement bid expiration date. Currently None.
                self.flight.make_bid(selected_manager, selected_bid, None)
                print(self.flight.agent_type, self.flight.unique_id, "makes bid to", selected_manager.unique_id, "with value of", selected_bid)
                # Save the bid that was made, so it can be used in the bidding strategy
                self.pending_bids[selected_manager] = {"bid": selected_bid,
                                                       "time": self.flight.model.schedule.steps,
                                                       "accepted": None}
        # If there are no currently pending bids, check if contractor agent can become a manager
        if self.flight.formation_state is "no_formation" and len(self.pending_bids) == 0:
            self.apply_for_manager()

    # TODO: Implement bidding strategy, to select bidding value
    def bidding_strategy(self, fuel_saved):
        return fuel_saved*0.5

    # TODO: Implement acceptance strategy, to select the winning bid
    def acceptance_strategy(self, bidding_agent, bid_value, bid_expiration_date):
        if bid_value >= self.flight.calculate_potential_fuelsavings(bidding_agent)*0.2:
            return True
        else:
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
                # print(self.flight.agent_type, self.flight.unique_id, f"stays contractor, {neighbor.unique_id} is already manager.")
                break
        if len(self.free_flights_in_reach) >= max(self.received_neighbor_counts) and manager_taken is False:
            self.flight.manager = 1
            print(self.flight.agent_type, self.flight.unique_id, "becomes manager")
        else:
            self.flight.manager = 0
            # print(self.flight.agent_type, self.flight.unique_id, "stays contractor")
        # After evaluation, reset the relevant lists, and update the role
        self.free_flights_in_reach = []
        self.received_neighbor_counts = []
        self.flight.update_role()
        return

    def call_for_contract(self):
        for neighbor in self.flight.model.space.get_neighbors(pos=self.flight.pos,
                                                              radius=self.flight.communication_range,
                                                              include_center=True):
            if neighbor.agent_type == "Flight" and neighbor.unique_id != self.flight.unique_id and neighbor.manager == 0 and neighbor.formation_state is "no_formation":
                neighbor.cnp.managers_calling.append(self.flight)
        return


