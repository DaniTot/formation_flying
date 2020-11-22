
def calc_distance(p1, p2):
    # p1 = tuple(p1)
    # p2 = tuple(p2)
    dist = (((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2) ** 0.5)
    return dist


def calc_middle_point(a, b):
    return [0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1])]


def utility_function(profit, fuel_saved, delay, with_ally=0, behavior="balanced"):
    behavior_options = {"budget": {"profit_weight": 4,
                                   "fuel_saved_weight": 1,
                                   "delay_weight": -1,
                                   "with_ally_weight": 0},
                        "green": {"profit_weight": 1,
                                  "fuel_saved_weight": 4,
                                  "delay_weight": -1,
                                  "with_ally_weight": 0},
                        "express": {"profit_weight": 1,
                                    "fuel_saved_weight": 1,
                                    "delay_weight": -4,
                                    "with_ally_weight": 0},
                        "balanced": {"profit_weight": 2,
                                     "fuel_saved_weight": 2,
                                     "delay_weight": -2,
                                     "with_ally_weight": 0}}
    # print(behavior)
    # print(behavior_options[behavior])
    # print(behavior_options[behavior].values())
    # print(type(behavior_options[behavior].values()))
    # print(type(*behavior_options[behavior].values()))
    # print(*behavior_options[behavior].values())
    score = utility_score(profit, fuel_saved, delay, with_ally, *behavior_options[behavior].values())
    return score


def utility_score(profit, fuel_saved, delay, with_ally, profit_weight, fuel_saved_weight, delay_weight, with_ally_weight):
    # print(f"Utility score: \nprofit: {profit*profit_weight}\nfuel: {fuel_saved*fuel_saved_weight}\ndelay: {delay*delay_weight}\nally: {with_ally*with_ally_weight}")
    score = profit*profit_weight + fuel_saved*fuel_saved_weight + delay*delay_weight + with_ally*with_ally_weight
    return score
