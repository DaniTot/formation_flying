# =============================================================================
# This file contains the function to do Contract Net Protocol (CNP). 
# =============================================================================

# def do_CNP(flight):
#     # the do_CNP function takes a flight-agent object

class CNP:
    def __init__(self, flight):
        self.flight = flight

        # Own status
        self.first_step = True
        self.free_agents_in_reach = []
        self.pending_bids = None

        # Received communications from other agents
        self.received_neighbor_counts = []
        self.received_bids = []

    def do_cnp(self):
        print()
        print(self.flight.unique_id)
        # Only evaluate role from the second step onwards
        if self.first_step is True:
            self.first_step = False
        elif len(self.received_neighbor_counts) > 0:
            print("received:", self.received_neighbor_counts)
            self.evaluate_role()
            # Put other step activities here:
            # Call for contract
            # TODO: Should manager call for contract after it's already in formation? Probably
            if self.flight.manager == 1 and self.flight.formation_state is "no_formation":
                self.call_for_contract()
            # TODO: Make a bid
            # TODO: Select a bidder
        if self.flight.manager is 0 and self.pending_bids is None:
            self.apply_for_manager()

    def apply_for_manager(self):
        # Fill the ree_agents_in_reach list
        temporary_free_agent_list = []
        for neighbor in self.flight.model.space.get_neighbors(pos=self.flight.pos,
                                                              radius=self.flight.communication_range,
                                                              include_center=True):
            # TODO: Should neighboring managers be counted? I'm guessing not
            if neighbor.agent_type is "Flight" and neighbor.unique_id != self.flight.unique_id and neighbor.manager is 0 and neighbor.formation_state is "no_formation":
                temporary_free_agent_list.append(neighbor)
        self.free_agents_in_reach = temporary_free_agent_list
        # Contact the neighboring free agents
        for neighbor in self.free_agents_in_reach:
            # TODO: Should neighboring managers be contacted? Why should they?
            if neighbor.manager == 0:
                print(f"transmit to {neighbor.agent_type} {neighbor.unique_id}: {len(self.free_agents_in_reach)}")
                neighbor.cnp.received_neighbor_counts.append(len(self.free_agents_in_reach))
        return

    def evaluate_role(self):
        # TODO: What happens when theres a tie in count? Follow the order of flights generated/take off.
        # Check if there are neighbors that already took manager role
        manager_taken = False
        for neighbor in self.free_agents_in_reach:
            if neighbor.manager == 1:
                manager_taken = True
                break
        if len(self.free_agents_in_reach) >= max(self.received_neighbor_counts) and manager_taken is False:
            self.flight.manager = 1
            print(self.flight.unique_id, "becomes manager")
        else:
            self.flight.manager = 0
            print(self.flight.unique_id, "becomes contractor")
        self.free_agents_in_reach = []
        self.flight.update_role()
        print(self.flight.formation_state)
        return

    # TODO: Call for contract
    def call_for_contract(self):
        for neighbor in self.free_agents_in_reach:
            if (((self.flight.pos[0] - neighbor.pos[0])**2 + (self.flight.pos[1] - neighbor.pos[1])**2) ** 0.5) >= self.flight.communication_range:
                return
        return


