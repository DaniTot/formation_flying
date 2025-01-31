'''
# =============================================================================
# This file contains the function to do a Greedy Algorithm. In the greedy method
# agents form a formation with the first agent in the nighborhood that makes 
# their potential fuel savings positive!
# =============================================================================
'''

# The do_greedy function takes a flight-agent object
def do_greedy(flight):
    if not flight.departure_time:
        raise Exception("The object passed to the greedy protocol has no departure time, therefore it seems that it is not a flight.")

    # If the agent is not yet in a formation, start finding candidates.
    if flight.formation_state == "no_formation" and flight.manager == 0:
        formation_targets = flight.find_greedy_candidate()
        
        # If there are candidates, start a formation with the first candidate 
        # with positive potential fuelsavings.
        if formation_targets is not None:
            for agent in formation_targets:
                if agent.formation_state in ("no_formation", "in_formation"):
                    if len(agent.agents_in_my_formation) > 0:
                        if flight.calculate_potential_fuelsavings(agent) > 0:
                            formation_savings = flight.calculate_potential_fuelsavings(agent)
                            assert flight.unique_id != agent.unique_id
                            agent.add_to_formation(flight, formation_savings, discard_received_bids=True)
                            break
                    elif len(agent.agents_in_my_formation) == 0:
                        if flight.calculate_potential_fuelsavings(agent) > 0:
                            formation_savings = flight.calculate_potential_fuelsavings(agent)
                            flight.start_formation(agent, formation_savings, discard_received_bids=True)
                            break
