import numpy as np
import pandas as pd

from sklearn.base import BaseEstimator
from sklearn.impute import SimpleImputer
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, matthews_corrcoef, f1_score

from typing import Any, Dict, List, Optional, Union

_BASE_LABELS = [' 50000+.', ' - 50000.']
_POS_LABEL = ' 50000+.'


##############################################################################################################
# Show results
##############################################################################################################

def remove_features(features:List[str], dfs:List[pd.DataFrame]) -> None:
    """
    Remove several features from several dataframes.
    
    :param features: Features to remove.
    :param dfs: Dataframes for feature removal.
    """
    for col in features:
        for df in dfs:
            df.drop(col, axis=1, inplace=True)

def compute_metrics(y_true:Union[np.array, pd.Series], y_pred:Union[np.array, pd.Series], 
                    labels:List[Any], pos_label:Union[str,int,float]) -> pd.DataFrame:
    """
    Compute balanced accuracy and MCC for given target and prediction.
    
    :param y_true: Real target values.
    :param y_pred: Predicted target values.
    :param labels: Class labels.
    :param pos_label: Positive class label.
    :return: 1-column table where rows are different metrics.
    """
    pd.set_option("display.precision", 3)
    ba = balanced_accuracy_score(y_true, y_pred)
    mcc = matthews_corrcoef(y_true, y_pred)
    metrics = pd.DataFrame([ba, mcc], index=['Balanced_Accuracy', 'MCC'], columns=['result'])
    return metrics

def compute_confusion_matrix(y_true:Union[np.array, pd.Series], y_pred:Union[np.array, pd.Series], 
                    labels:List[Any] = _BASE_LABELS, pos_label:Union[str,int,float]=_POS_LABEL) -> pd.DataFrame:
    """
    Compute confusion matrix for given target and prediction.
    
    :param y_true: Real target values.
    :param y_pred: Predicted target values.
    :param labels: Class labels.
    :param pos_label: Positive class label.
    :return: Confusion matrix.
    """
    results = pd.DataFrame(confusion_matrix(y_true,
                                         y_pred,
                                         labels=labels),
                        columns=['a(x) < 50.000', 'a(x) > 50.000'],
                        index=['y < 50.000 ', 'y > 50.000 ']).T
    return results.sort_index(axis=0, ascending=False).sort_index(axis=1, ascending=False)

def get_resample_results(y_orig: pd.Series, y_fitted: pd.Series) -> pd.DataFrame:
    """
    Show results of resampling compared to original data balance.
    
    :param y_orig: Original data.
    :param y_fitted: Resampled data.
    :return: Table with balance of classes shown before and after resampling.
    """
    pd.set_option("display.precision", 2)

    result = pd.DataFrame(
        pd.concat(
            [y_orig.value_counts(normalize=True),
             y_fitted.value_counts(normalize=True),
             y_orig.value_counts(),
             y_fitted.value_counts()],
            axis=1))
    result.columns = ['%_orig', '%_fitted', 'count_orig', 'count_fitted']
    result.index = ['<50.000', '>50.000']
    return result
                 
##############################################################################################################
# Preprocessing
##############################################################################################################                 
                 
class CustomEncoder(BaseEstimator): 
    """
    Encoding of features based on the given mappings. Dict with columns
    and the corresponding mappings must be given.
    
    Can also be used as a column features merger, if some column values
    amount have to reduced by merging some categories into one.
    For example, uniqoe values ['1st grade', '2nd grade', '3rd grade, 'High school']
    can be encoded into ['1-3 grades', 'High school'] if the appropriate mapping given.
    Can be helpful if some categories are poorly presented.
    """
    
    def __init__(self, mapping: Optional[Dict[str, Dict[str, int]]] = None):
        """
        :param mapping: Mapping for categories and numbers for all columns.
        """
        self.mapping = mapping
        
    def fit(self, X:pd.DataFrame, y: Optional[Any] = None):
        assert type(X) == pd.DataFrame, ' X must be a Dataframe.'
        
        cols = X.columns.tolist()
        for key in self.mapping.keys():
            assert key in cols, f'{key} not in X columns.'
        return self
        
    def transform(self, X:pd.DataFrame):
        X = X.copy()
        
        for key in self.mapping.keys():
            X[key] = X[key].replace(self.mapping[key])
            
        return X
    
    def fit_transform(self, X:pd.DataFrame, y: Optional[Any] = None):
        return self.fit(X).transform(X)
    
class BinaryEncoder(BaseEstimator):
    """
    Binary encoding with possible aditional '-1' class for N/A.
    
    For example, unique values ['Married', 'Divorced, 'N/A']
    would be encoded into [1, 0, -1].
    """
    
    def __init__(self, na_values:Optional[List[str]] = None):
        """
        :param na_values: Not applicable value if any.
        """
        self.na_values = None
        if na_values:
            self.na_values = na_values
            
        
    def fit(self, X:pd.DataFrame, y: Optional[Any] = None):
        """
        For every column create mappings between categories and labels.
        """
        assert type(X) == pd.DataFrame, f'{X.columns}, X must be a Dataframe.'
        
        self.mapping = {}
        self.columns = X.columns.tolist()
        
        for column in self.columns:       
            # Take unique column values.
            unique_vals = X[column].unique().tolist()
            if self.na_values:
                unique_vals = list(set(unique_vals).difference(set(self.na_values)))
            assert len(unique_vals) == 2, f'{column} It is a binary encoder, there must be 2 values besides N/A.'

            # Create a mapping with [-1, 0, 1] classes for obserbed column.
            col_mapping = dict(zip(unique_vals, [0, 1]))
            if self.na_values:
                for val in self.na_values:
                    col_mapping[val] = -1
        
            self.mapping[column] = col_mapping
            
        return self
        
        
    def transform(self, X:pd.DataFrame):
        """
        Apply the fitted mapping.
        """
        X = X.copy()
        
        for column in self.columns:
            X[column] = X.replace(self.mapping[column])
        return X
    
    def fit_transform(self, X:pd.DataFrame, y: Optional[Any] = None):
        return self.fit(X).transform(X)