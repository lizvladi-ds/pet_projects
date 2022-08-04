import pandas as pd
from typing import List, Tuple

def custom_split_train_test(
    data: pd.DataFrame, labels: pd.DataFrame, train_ids: List[int],
    test_ids: List[ids]
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split data into train and test.
    For features dataset: add 10 averaged colling with sliding windows from 2 to 10.
    Crop such dataset into 10 smaller dataset with shape 10x10.
    So from one 160 timeseries we have a dataset of shape 15x10x10.
    Examples with pictures are in the presentation.
    
    :param data: Dataset of timeserieses concatenated.
    :param labels: Dataset of targets.
    :param train_ids: Randomly shuffled ids for test.
    :param test_ids: Randomly shuffled ids for test.
    :return: Train and test data.
    """
    # Prepare lists for feature modified datasets.
    datasets_train = []
    datasets_test = []
    y_train = []
    y_test = []

    # For each gfid:
    for _ in gfids:
        # Add 10 moving averages of NDVI.
        rolling_data = []
        rolling_data.append(data[data['gfid'] == _]['ndvi'].iloc[4:])
        for i in range(2, 11):
            rolling_data.append(
                data[data['gfid'] == _]['ndvi'].rolling(i).mean())
        data_1_rolling = pd.concat(rolling_data, axis=1)
        data_1_rolling = data_1_rolling.dropna()
        # Rename columns.
        data_1_rolling.columns = ['ndvi'] + [f'ndvi_{i}' for i in range(2, 11)]
        # Define whether this gfid is train or test and add it to needed list.
        if _ in train_ids:
            datasets_train.append(data_1_rolling[:150].values.reshape(
                15, 10, 10))
            y_train += [labels.loc[labels['gfid'] == _, 'wheat'].iloc[0]]
        else:
            datasets_test.append(data_1_rolling[:150].values.reshape(
                15, 10, 10))
            y_test += [labels.loc[labels['gfid'] == _, 'wheat'].iloc[0]]

        return datasets_train, datasets_test, y_train, y_test
    
    
def calculate_out(h_in, w_in, ker, pad=0, stride=1):
    """
    Calculate shape of an output of CNN layer.
    """
    h_out = (h_in + 2 * pad - (ker - 1) - 1) / (stride) + 1
    w_out = (w_in + 2 * pad - (ker - 1) - 1) / (stride) + 1
    return h_out, w_out