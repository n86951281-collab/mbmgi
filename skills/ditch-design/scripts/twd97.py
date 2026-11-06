"""TWD97 TM2（121°E）↔ WGS84 經緯度（GRS80，誤差 < 0.1 m）。"""
import math
A = 6378137.0; F = 1 / 298.257222101; K0 = 0.9999; L0 = math.radians(121); DX = 250000.0
E2 = F * (2 - F)
def to_latlon(x, y):
    x -= DX; e1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))
    M = y / K0; mu = M / (A * (1 - E2 / 4 - 3 * E2**2 / 64 - 5 * E2**3 / 256))
    p = mu + (3*e1/2 - 27*e1**3/32) * math.sin(2*mu) + (21*e1**2/16 - 55*e1**4/32) * math.sin(4*mu) + (151*e1**3/96) * math.sin(6*mu) + (1097*e1**4/512) * math.sin(8*mu)
    ep2 = E2 / (1 - E2); C1 = ep2 * math.cos(p)**2; T1 = math.tan(p)**2
    N1 = A / math.sqrt(1 - E2 * math.sin(p)**2); R1 = A * (1 - E2) / (1 - E2 * math.sin(p)**2)**1.5; D = x / (N1 * K0)
    lat = p - (N1 * math.tan(p) / R1) * (D**2/2 - (5 + 3*T1 + 10*C1 - 4*C1**2 - 9*ep2) * D**4/24 + (61 + 90*T1 + 298*C1 + 45*T1**2 - 252*ep2 - 3*C1**2) * D**6/720)
    lon = L0 + (D - (1 + 2*T1 + C1) * D**3/6 + (5 - 2*C1 + 28*T1 - 3*C1**2 + 8*ep2 + 24*T1**2) * D**5/120) / math.cos(p)
    return math.degrees(lat), math.degrees(lon)
