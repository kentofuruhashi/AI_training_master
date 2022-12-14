import pandas as pd 
from typing import Dict,Union
from datasets.utils import read_df
from data_loader.json_loader import save_param
import lightgbm as lgb
from settings.params import TARGET_OBJ,SEED,N_BOOST_ROUND,N_EARLY_STOPPING_ROUND,TRIAL_NUM
import numpy as np
import numpy.typing as npt
import optuna
from sklearn.metrics import mean_squared_error

"""
optuna まとめ
suggest_categorical(name, [choices]): choicesから選ぶ
suggest_float(name, low, high, [step, log]): lowからhighまでstep刻み
suggest_int(name, low, high, step): lowからhighまでstep刻み
"""



class Objective:
    def __init__(
        self,
        train_data: lgb.Dataset,
        valid_data: lgb.Dataset,
        test_x: npt.NDArray[np.float32],
        test_y: npt.NDArray[np.float32],
    ) -> None:
        self.train_data = train_data
        self.valid_data = valid_data
        self.test_x = test_x
        self.test_y = test_y
    
    def __call__(self, trial: optuna.trial.Trial) -> float:
        params = {
            "objective": "regression",
            "metrics": "rmse",
            "verbosity": -1,
            "boosting": "gbdt",
            "seed": SEED,
            "n_jobs": -1,
            "learning_rate": trial.suggest_float("learning_rate", 1e-6, 0.1, log=True),
            "lambda_l1": trial.suggest_float("lambda_l1", 1e-8, 10.0, log=True),
            "lambda_l2": trial.suggest_float("lambda_l2", 1e-8, 10.0, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 2, 2 ^ 10),
            "max_depth": trial.suggest_int("max_depth", 1, 100),
            "feature_fraction": trial.suggest_float("feature_fraction", 0.1, 1.0, log=True),
            "bagging_fraction": trial.suggest_float("bagging_fraction", 0.1, 1.0, log=True),
            "bagging_freq": trial.suggest_int("bagging_freq", 0, 30),
            "min_data_in_leaf": trial.suggest_int("min_child_samples", 1, 100),
            "feature_pre_filter": False,
        }

        model = lgb.train(
            params,
            self.train_data,
            valid_sets=self.valid_data,
            num_boost_round=N_BOOST_ROUND,
            early_stopping_rounds=N_EARLY_STOPPING_ROUND,
            verbose_eval=False,
        )

        pred_y = model.predict(self.test_x)
        rmse:float = np.sqrt(mean_squared_error(self.test_y,pred_y))
        print(f"RMSE: {rmse}")

        return rmse




def optimize_param(train_df:pd.DataFrame,valid_df:pd.DataFrame,test_df:pd.DataFrame)-> Dict[str,Union[int,float,str]]:
    train_x, train_y = read_df(train_df, TARGET_OBJ)
    valid_x, valid_y = read_df(valid_df, TARGET_OBJ)
    test_x, test_y = read_df(test_df, TARGET_OBJ)

    train_dataset = lgb.Dataset(train_x, train_y)
    valid_dataset = lgb.Dataset(valid_x, valid_y)

    objective = Objective(train_dataset,valid_dataset,test_x,test_y)
    study = optuna.create_study(
        study_name="optimize_param-1-2", storage="sqlite:///optuna_study.sqlite", load_if_exists=True
    )
    study.optimize(objective, n_trials=TRIAL_NUM,timeout=30)

    params: Dict[str, Union[int, float, str]] = {
        "objective": "regression",
        "metrics": "rmse",
        "verbosity": -1,
        "boosting": "gbdt",
        "seed": SEED,
        "n_jobs": -1,
    }
    for k, v in study.best_params.items():
        params[k] = v
    save_param(params)

    return params