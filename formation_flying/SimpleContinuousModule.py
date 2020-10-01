'''
# =============================================================================
# This file contains the drawing of the canvas for the visualization. It uses 
# 'simple_continuous_canvas.js' which is a standard java script for continuous 
# canvasses.
# =============================================================================
'''

from mesa.visualization.ModularVisualization import VisualizationElement
import random


class SimpleCanvas(VisualizationElement):
    local_includes = ["formation_flying/simple_continuous_canvas.js?" + str(random.randint(100,999))]
    portrayal_method = None
    canvas_height = 500
    canvas_width = 500

    def __init__(self, portrayal_method, canvas_height=500, canvas_width=500):
        """
        Instantiate a new SimpleCanvas
        """
        self.portrayal_method = portrayal_method
        self.canvas_height = canvas_height
        self.canvas_width = canvas_width
        new_element = "new Simple_Continuous_Module({}, {})".format(
            self.canvas_width, self.canvas_height
        )
        self.js_code = "elements.push(" + new_element + ");"

    def render(self, model):
        space_state = []
        for obj in model.schedule.agents:
            #import the types of agents here and do
            # if type(obj) == Boid:
            # do formation-portrayal
            # if type(obj) == Airport:
            # do airport-portrayal

            portrayal = self.portrayal_method(obj)
            x, y = obj.pos
            x = (x - model.space.x_min) / (model.space.x_max - model.space.x_min)
            y = (y - model.space.y_min) / (model.space.y_max - model.space.y_min)
            portrayal["x"] = x
            portrayal["y"] = y
            space_state.append(portrayal)
        return space_state
