import numpy as np
from scipy.stats import norm
import matplotlib.pyplot as plt
import pandas as pd

folder = "cnp_data"
batch = "4_CNP_airport3"


def histogram(data, name):
    print("Plotting", name)
    data_array = np.array([data])

    mu = np.mean(data_array)  # mean of distribution
    sigma = np.std(data_array)  # standard deviation of distribution
    median = np.median(data_array)  # median of distribution

    num_bins = 50
    # the histogram of the data
    plt.hist(data_array, num_bins, density=True, stacked=True, facecolor='blue', alpha=0.5)

    # add a 'best fit' line
    x = np.linspace(np.min(data_array) - mu*0.1, np.max(data_array) + mu*0.1, 100)
    plt.plot(x, norm.pdf(x, mu, sigma), 'r--', label=f"Normal PDF with\nmean={np.round(mu, decimals=2)}\nstd={np.round(sigma, decimals=2)}")
    plt.axvline(median, ymin=0, ymax=mu, c='g', label=f"Median = {np.round(median, decimals=2)}")

    plt.xlabel(f'{name}')
    plt.ylabel('Probability')
    plt.title(f'N = {data_array.size}, mu={np.round(mu, decimals=2)}, sigma={np.round(sigma, decimals=2)}')
    plt.legend()
    plt.savefig(f'{folder}/{name}_{batch}.png')
    plt.close()


distance_in_formation = []
delay = []
est_delay = []
est_saved_fuel = []
est_uti = []
planned_fuel = []
saved_fuel = []
uti = []

labels = ["Planned fuel", "Distance in formation", "Delay time", "Estimated delay", "Estimated fuel saved",
          "Estimated utility", "Planned fuel", "Real fuel saved", "Utility"]
lists = [planned_fuel, distance_in_formation, delay, est_delay, est_saved_fuel, est_uti, planned_fuel, saved_fuel, uti]

for i in range(1):
    # agent_data = pd.read_excel(f'{folder}/agent_output_{batch}{i}.xlsx')
    # model_date = pd.read_excel(f'{folder}/model_output_{batch}{i}.xlsx')
    agent_data = pd.read_excel(f'{folder}/agent_output_{batch}.xlsx')
    print("Loading", i)
    for idx in agent_data.index:
        if agent_data.iloc[idx]["Planned fuel"] > 0. or agent_data.iloc[idx]["Behavior"] is "Airport":
            if agent_data.iloc[idx]["Planned fuel"] == 0.:
                print(agent_data.iloc[idx])
            distance_in_formation.append(agent_data.iloc[idx]["Distance in formation"])
            delay.append(agent_data.iloc[idx]["Delay time"])
            est_delay.append(agent_data.iloc[idx]["Estimated delay"])
            est_saved_fuel.append(agent_data.iloc[idx]["Estimated fuel saved"])
            est_uti.append(agent_data.iloc[idx]["Estimated utility"])
            planned_fuel.append(agent_data.iloc[idx]["Planned fuel"])
            saved_fuel.append(agent_data.iloc[idx]["Real fuel saved"])
            uti.append(agent_data.iloc[idx]["Utility"])

for i in range(len(lists)):
    histogram(lists[i], labels[i])
