
from __future__ import annotations
from typing import List
import numpy as np
import pandas as pd

def style_percent_cell(val):
    try:
        v = float(val)
    except Exception:
        return ''
    if np.isnan(v):
        return ''
    if v < -20:
        color = 'background-color: #b7e4c7'
    elif v < 0:
        color = 'background-color: #d4f8e8'
    elif v == 0:
        color = 'background-color: #ffffff'
    elif v <= 20:
        color = 'background-color: #ffe7a3'
    else:
        color = 'background-color: #ffb3b3'
    return color
