'''
# =============================================================================
# In this file one can define how the agents and model will be visulised in the 
# server.
# 
# When wanting additional charts or be able to change in the server, changes 
# need to be made here.
# =============================================================================
'''

from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.modules import ChartModule

from .model import FormationFlying
from .SimpleContinuousModule import SimpleCanvas
from .agents.flight import Flight
from .agents.airports import Airport
from .parameters import model_params



def boid_draw(agent):
    if type(agent) is Flight:
        # The visualization is changed based on the status of the flight. You 
        # can change this as you like. For example, you can give agents that are 
        # arrived a radius=0 to remove them from the map.

        if agent.state == "scheduled":
            return {"Shape": "circle", "r": 1, "Filled": "true", "Color": "Red"}
        elif agent.state == "flying":
            if (agent.formation_state == 0 or agent.formation_state == 3):
                if agent.auctioneer:
                    return {"Shape": "circle", "r": 2, "Filled": "true", "Color": "Red"}
                elif agent.manager:
                    return {"Shape": "circle", "r": 2, "Filled": "true", "Color": "Pink"}
            elif agent.formation_state == 4:
                return {"Shape": "circle", "r": 2, "Filled": "true", "Color": "Yellow"}
            elif agent.formation_state == 2:
                return {"Shape": "circle", "r": 2, "Filled": "true", "Color": "Black"}
            elif agent.formation_state == 1:
                return {"Shape": "circle", "r": 2, "Filled": "true", "Color": "Orange"}
        elif agent.state == "arrived":
            return {"Shape": "circle", "r": 1, "Filled": "true", "Color": "Red"}
        else:
            raise Exception("Flight is in unknown state")
    elif type(agent) is Airport:
        if agent.airport_type == "Origin":
            return {"Shape": "circle", "r": 3, "Filled": "true", "Color": "Green"}
        elif agent.airport_type == "Destination":
            return {"Shape": "circle", "r": 3, "Filled": "true", "Color": "Blue"}
        elif agent.airport_type == "Closed":
            return {"Shape": "circle", "r": 3, "Filled": "true", "Color": "Grey"}
        else:
            raise Exception("Airport is neither origin or destination")
    else:
        raise Exception("Trying to display an agent of unknown type")



# Makes a canvas of 500x500 pixels. Increasing or decreasing canvas size should 
# not affect results - only visualization.
formation_canvas = SimpleCanvas(boid_draw, 1000, 1000) 


chart = ChartModule([{"Label": "Total Fuel Used", "Color": "Black"}],
                    data_collector_name='datacollector')
server = ModularServer(FormationFlying, [formation_canvas, chart], "Formations", model_params)
server.launch()