
def calc_distance(p1, p2):
    # p1 = tuple(p1)
    # p2 = tuple(p2)
    dist = (((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2) ** 0.5)
    return dist
