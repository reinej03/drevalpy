import warnings
from typing import Union, List
import sklearn.metrics as metrics
import pandas as pd
import numpy as np
from typing import Tuple
from scipy.stats import pearsonr, spearmanr, kendalltau
import pingouin as pg
from .datasets.dataset import DrugResponseDataset

warning_shown = False


def partial_correlation(
    y_pred: np.ndarray,
    y_true: np.ndarray,
    cell_line_ids: np.ndarray,
    drug_ids: np.ndarray,
    method: str = "pearson",
    return_pvalue: bool = False,
) -> Tuple[float, float] | float:
    """
    Computes the partial correlation between predictions and response, conditioned on cell line and drug.
    :param y_pred: predictions
    :param y_true: response
    :param cell_line_ids: cell line IDs
    :param drug_ids: drug IDs
    :param method: method to compute the partial correlation (pearson, spearman)
    :return: partial correlation float
    """

    if len(y_true) < 3:
        return np.nan if not return_pvalue else (np.nan, np.nan)
    assert (
        len(y_pred) == len(y_true) == len(cell_line_ids) == len(drug_ids)
    ), "predictions, response, drug_ids, and cell_line_ids must have the same length"
    
    df = pd.DataFrame(
        {
            "response": y_true,
            "predictions": y_pred,
            "cell_line_ids": cell_line_ids,
            "drug_ids": drug_ids,
        }
    )
    

    if (len(df["cell_line_ids"].unique()) < 2) or (len(df["drug_ids"].unique()) < 2):
        # if we don't have more than one cell line or drug in the data, partial correlation is meaningless
        global warning_shown
        if not warning_shown:
            warnings.warn(
                "Partial correlation not defined if only one cell line or drug is in the data."
            )
            warning_shown = True
        return (np.nan, np.nan) if return_pvalue else np.nan
    
    # Check if predictions are nearly constant for each cell line or drug (or both (e.g. mean predictor))
    variance_threshold = 1e-6       
    for group_col in ["cell_line_ids", "drug_ids"]:
        group_variances = df.groupby(group_col)["predictions"].var()
        if (group_variances < variance_threshold).any():
            warnings.warn(
                f"Predictions are nearly constant for some {group_col}. Adding some noise to these predictions for partial correlation calculation."
            )
            df["predictions"] = df["predictions"] + np.random.normal(0, 1e-5, size=len(df))

    df["cell_line_ids"] = pd.factorize(df["cell_line_ids"])[0]
    df["drug_ids"] = pd.factorize(df["drug_ids"])[0]
    # One-hot encode the categorical covariates
    df_encoded = pd.get_dummies(df, columns=["cell_line_ids", "drug_ids"], dtype=int)

    if df.shape[0] < 3:
        r, p = np.nan, np.nan
    else:
        result = pg.partial_corr(
            data=df_encoded,
            x="predictions",
            y="response",
            covar=[col for col in df_encoded.columns if col.startswith('cell_line_ids') or col.startswith('drug_ids')],
            method=method,
        )
        r = result["r"].iloc[0]
        p = result["p-val"].iloc[0]
    if return_pvalue:
        return r, p
    else:
        return r


def pearson(y_pred: np.ndarray, y_true: np.ndarray) -> float:
    """
    Computes the pearson correlation between predictions and response.
    :param y_pred: predictions
    :param y_true: response
    :return: pearson correlation float
    """

    assert len(y_pred) == len(
        y_true
    ), "predictions, response  must have the same length"
    if (y_pred == y_pred[0]).all() or (y_true == y_true[0]).all() or len(y_true) < 2:
        return np.nan
    return pearsonr(y_pred, y_true)[0]


def spearman(y_pred: np.ndarray, y_true: np.ndarray) -> float:
    """
    Computes the spearman correlation between predictions and response.
    :param y_pred: predictions
    :param y_true: response
    :return: spearman correlation float
    """
    # we can use scipy.stats.spearmanr
    assert len(y_pred) == len(
        y_true
    ), "predictions, response  must have the same length"
    if (y_pred == y_pred[0]).all() or (y_true == y_true[0]).all() or len(y_true) < 2:
        return np.nan
    return spearmanr(y_pred, y_true)[0]


def kendall(y_pred: np.ndarray, y_true: np.ndarray) -> float:
    """
    Computes the kendall tau correlation between predictions and response.
    :param y_pred: predictions
    :param y_true: response
    :return: kendall tau correlation float
    """
    # we can use scipy.stats.spearmanr
    assert len(y_pred) == len(
        y_true
    ), "predictions, response  must have the same length"
    if (y_pred == y_pred[0]).all() or (y_true == y_true[0]).all() or len(y_true) < 2:
        return np.nan
    return kendalltau(y_pred, y_true)[0]


AVAILABLE_METRICS = {
    "MSE": metrics.mean_squared_error,
    "RMSE": metrics.root_mean_squared_error,
    "MAE": metrics.mean_absolute_error,
    "R^2": metrics.r2_score,
    "Pearson": pearson,
    "Spearman": spearman,
    "Kendall": kendall,
    "Partial_Correlation": partial_correlation,
}
MINIMIZATION_METRICS = ["MSE", "RMSE", "MAE"]
MAXIMIZATION_METRICS = ["R^2", "Pearson", "Spearman", "Kendall", "Partial_Correlation"]


def get_mode(metric: str):
    if metric in MINIMIZATION_METRICS:
        mode = "min"
    elif metric in MAXIMIZATION_METRICS:
        mode = "max"
    else:
        raise ValueError(
            f"Invalid metric: {metric}. Need to add metric to MINIMIZATION_METRICS or MAXIMIZATION_METRICS?"
        )
    return mode


def evaluate(dataset: DrugResponseDataset, metric: Union[List[str], str]):
    """
    Evaluates the model on the given dataset.
    :param dataset: dataset to evaluate on
    :param metric: evaluation metric(s) (one or a list of "mse", "rmse", "mae", "r2", "pearson", "spearman", "kendall", "partial_correlation")
    :return: evaluation metric
    """
    if isinstance(metric, str):
        metric = [metric]
    predictions = dataset.predictions
    response = dataset.response
    results = {}
    for m in metric:
        assert (
            m in AVAILABLE_METRICS
        ), f"invalid metric {m}. Available: {list(AVAILABLE_METRICS.keys())}"
        if len(response) < 2:
            results[m] = float(np.nan)
        else:
            if m == "Partial_Correlation":
                results[m] = float(
                    AVAILABLE_METRICS[m](
                        y_pred=predictions,
                        y_true=response,
                        cell_line_ids=dataset.cell_line_ids,
                        drug_ids=dataset.drug_ids,
                    )
                )
            else:
                results[m] = float(
                    AVAILABLE_METRICS[m](y_pred=predictions, y_true=response)
                )

    return results


def visualize_results(results: pd.DataFrame, mode: Union[List[str], str]):
    """
    Visualizes the model on the given dataset.
    :param dataset: dataset to evaluate on
    :mode
    :return: evaluation metric
    """
    raise NotImplementedError("visualize not implemented yet")
