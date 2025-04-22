import os
import pandas as pd
import copy
from fuzzywuzzy import process
from unidecode import unidecode
import numpy as np
from scipy.stats import entropy
import datetime
import shutil
def shannon_index(values):
    probabilities = values / np.sum(values)
    return np.round(entropy(probabilities, base=2),4)
def coefficient_of_variation(values):
    mean = np.mean(values)
    return np.round((np.std(values) / mean),4) if mean != 0 else None
def gini_index(values):
    sorted_values = np.sort(values)
    n = len(values)
    cumulative = np.cumsum(sorted_values)
    return np.round((1 - (2 * np.sum(cumulative) / (n * cumulative[-1])) + (1 / n)),4) if n > 0 else None
def hhi_index(values):
    probabilities = 1 / values
    probabilities /= np.sum(probabilities)
    return np.round(np.sum(probabilities ** 2),4)
def calculate_consensus(row, columns):
    votes_H = sum([1 for col in columns["H"] if row[col] < row[columns["D"][0]] and row[col] < row[columns["A"][0]]])
    votes_D = sum([1 for col in columns["D"] if row[col] < row[columns["H"][0]] and row[col] < row[columns["A"][0]]])
    votes_A = sum([1 for col in columns["A"] if row[col] < row[columns["H"][0]] and row[col] < row[columns["D"][0]]])
    if votes_H > max(votes_D, votes_A):
        return 'H'
    elif votes_D > max(votes_H, votes_A):
        return 'D'
    elif votes_A > max(votes_H, votes_D):
        return 'A'
    else:
        return 'No Consensus'