'''
# =============================================================================
# When running this file the batchrunner will be used for the model. 
# No visulaization will happen.
# =============================================================================
'''
from mesa.batchrunner import BatchRunner
from formation_flying.model import FormationFlying
from formation_flying.parameters import model_params, max_steps, n_iterations, model_reporter_parameters, agent_reporter_parameters, variable_params


batch_run = BatchRunner(FormationFlying,
                        fixed_parameters=model_params,
                        variable_parameters=variable_params,
                        iterations=n_iterations,
                        max_steps=max_steps,
                        model_reporters=model_reporter_parameters,
                        agent_reporters=agent_reporter_parameters
                        )

batch_run.run_all()

run_data = batch_run.get_model_vars_dataframe()
agent_data = batch_run.get_agent_vars_dataframe()
agent_data.to_excel(f"agent_output_{n_iterations}_CNP_airport2.xlsx")
run_data.to_excel(f"model_output_{n_iterations}_CNP_airport2.xlsx")
# agent_data.to_excel(f"agent_output.xlsx")
# run_data.to_excel(f"model_output.xlsx")

