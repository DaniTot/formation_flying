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
    if flight.formation_state == 0:
        formation_targets = flight.find_greedy_candidate()
        
        # If there are candidates, start a formation with the first candidate 
        # with positive potential fuelsavings.
        if formation_targets != None:
            
            for agent in formation_targets:
                
                if flight.calculate_potential_fuelsavings(agent) > 0:
                    formation_target = agent
                    formation_savings = flight.calculate_potential_fuelsavings(agent)
                    
                    if len(flight.agents_in_my_formation) > 0:
                        flight.add_to_formation(formation_target, formation_savings, discard_received_bids=True)
                    else:
                        flight.start_formation(formation_target, formation_savings, discard_received_bids=True)
                    break
                
        