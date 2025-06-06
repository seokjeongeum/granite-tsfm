# Copyright contributors to the TSFM project
#

import copy
import json
import os
import tempfile
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException
from tsfminference.inference import InferenceRuntime
from tsfminference.inference_payloads import (
    ForecastingInferenceInput,
    ForecastingMetadataInput,
    ForecastingParameters,
    PredictOutput,
)


SERIES_LENGTH = int(os.getenv("TSFM_PROFILE_SERIES_LENGTH", 512))
FORECAST_LENGTH = 96
MODEL_ID = "mytest-tsfm/ttm-r1"
NUM_TIMESERIES = int(os.getenv("TSFM_PROFILE_NUM_TIMESERIES", 2))


@pytest.fixture(scope="module")
def ts_data_base() -> pd.DataFrame:
    # Generate a date range
    length = SERIES_LENGTH
    date_range = pd.date_range(start="2023-10-01", periods=length, freq="h")

    timeseries = []
    for idx in range(NUM_TIMESERIES):
        timeseries.append(
            pd.DataFrame(
                {
                    "date": date_range,
                    "ID": str(idx),
                    "VAL": np.random.rand(length),
                }
            )
        )

    return pd.concat(timeseries, ignore_index=True)


@pytest.fixture(scope="module")
def forecasting_input_base() -> ForecastingInferenceInput:
    # df: pd.DataFrame = ts_data_base
    schema: ForecastingMetadataInput = ForecastingMetadataInput(
        timestamp_column="date", id_columns=["ID"], target_columns=["VAL"]
    )
    parameters: ForecastingParameters = ForecastingParameters()
    input: ForecastingInferenceInput = ForecastingInferenceInput(
        model_id=MODEL_ID,
        schema=schema,
        parameters=parameters,
        data={
            "date": [
                "2024-10-18T01:00:21+00:00",
            ],
            "ID1": [
                "I1",
            ],
            "VAL": [
                10.0,
            ],
        },  # this should get replaced in each test case anyway,
    )
    return input


def _basic_result_checks(results: PredictOutput, df: pd.DataFrame):
    # expected length
    assert len(results) == FORECAST_LENGTH * NUM_TIMESERIES
    # expected start time
    answer = results["date"].iloc[0] - df["date"].iloc[-1]
    assert (
        answer == timedelta(hours=1) if isinstance(answer, timedelta) else answer == timedelta(hours=1).total_seconds()
    )
    # expected end time
    answer = results["date"].iloc[-1] - df["date"].iloc[-1]
    assert (
        answer == timedelta(hours=FORECAST_LENGTH)
        if isinstance(answer, timedelta)
        else answer == timedelta(hours=FORECAST_LENGTH).total_seconds()
    )


def test_forecast_with_decimal_freq(ts_data_base: pd.DataFrame, forecasting_input_base: ForecastingInferenceInput):
    input: ForecastingInferenceInput = forecasting_input_base
    input: ForecastingInferenceInput = copy.deepcopy(input)
    input.schema.freq = "3600.0s"  # 1-hr
    df = copy.deepcopy(ts_data_base)
    input.data = df.to_dict(orient="list")
    runtime: InferenceRuntime = InferenceRuntime()
    po: PredictOutput = runtime.forecast(input=input)
    results = pd.DataFrame.from_dict(po.results[0])
    _basic_result_checks(results, df)

    # without a period specifier
    input: ForecastingInferenceInput = forecasting_input_base
    input: ForecastingInferenceInput = copy.deepcopy(input)
    input.schema.freq = "3600.0"  # 1-hr
    df = copy.deepcopy(ts_data_base)
    df["date"] = df["date"].values.astype("int64") // 10**9
    input.data = df.to_dict(orient="list")
    runtime: InferenceRuntime = InferenceRuntime()
    po: PredictOutput = runtime.forecast(input=input)
    results = pd.DataFrame.from_dict(po.results[0])
    _basic_result_checks(results, df)


def test_forecast_with_single_character_column_name(
    ts_data_base: pd.DataFrame, forecasting_input_base: ForecastingInferenceInput
):
    input: ForecastingInferenceInput = forecasting_input_base
    input: ForecastingInferenceInput = copy.deepcopy(input)
    input.schema.target_columns = ["V"]
    input.schema.timestamp_column = "D"
    input.schema.id_columns = ["I"]
    df = copy.deepcopy(ts_data_base)
    df = df.rename(columns={"VAL": "V"})
    df = df.rename(columns={"date": "D"})
    df = df.rename(columns={"ID": "I"})

    input.data = df.to_dict(orient="list")
    runtime: InferenceRuntime = InferenceRuntime()
    po: PredictOutput = runtime.forecast(input=input)
    results = pd.DataFrame.from_dict(po.results[0])

    # change column names back so _basic_result_checks works
    df = df.rename(columns={"V": "VAL"})
    df = df.rename(columns={"D": "date"})
    df = df.rename(columns={"I": "ID"})

    results = results.rename(columns={"V": "VAL"})
    results = results.rename(columns={"D": "date"})
    results = results.rename(columns={"I": "ID"})

    _basic_result_checks(results, df)


def test_forecast_with_good_data(ts_data_base: pd.DataFrame, forecasting_input_base: ForecastingInferenceInput):
    input = forecasting_input_base
    model_id = input.model_id
    df = ts_data_base if int(os.environ.get("TSFM_TESTS_AS_PROFILER", "0")) == 0 else copy.deepcopy(ts_data_base)
    input.data = df.to_dict(orient="list")

    # useful for generating sample payload files
    if int(os.environ.get("TSFM_TESTS_DO_VERBOSE_DUMPS", "0")) == 1:
        with open(f"{tempfile.gettempdir()}/{model_id}.payload.json", "w") as out:
            foo = copy.deepcopy(df)
            foo["date"] = foo["date"].apply(lambda x: x.isoformat())
            json.dump(foo.to_dict(orient="list"), out)

    runtime: InferenceRuntime = InferenceRuntime()
    po: PredictOutput = runtime.forecast(input=input)
    results = pd.DataFrame.from_dict(po.results[0])
    _basic_result_checks(results, df)


def test_forecast_with_schema_missing_target_columns(
    ts_data_base: pd.DataFrame, forecasting_input_base: ForecastingInferenceInput
):
    input = forecasting_input_base
    input.schema.target_columns = []
    df = copy.deepcopy(ts_data_base)
    input.data = df.to_dict(orient="list")
    runtime: InferenceRuntime = InferenceRuntime()
    po: PredictOutput = runtime.forecast(input=input)
    results = pd.DataFrame.from_dict(po.results[0])
    _basic_result_checks(results, df)


def test_forecast_with_integer_timestamps(
    ts_data_base: pd.DataFrame, forecasting_input_base: ForecastingInferenceInput
):
    input: ForecastingInferenceInput = copy.deepcopy(forecasting_input_base)
    df = copy.deepcopy(ts_data_base)

    timestamp_column = input.schema.timestamp_column
    df[timestamp_column] = df[timestamp_column].astype(int)
    df[timestamp_column] = range(1, SERIES_LENGTH * NUM_TIMESERIES + 1)
    input.data = df.to_dict(orient="list")
    runtime: InferenceRuntime = InferenceRuntime()
    po: PredictOutput = runtime.forecast(input=input)
    results = pd.DataFrame.from_dict(po.results[0])
    assert results[timestamp_column].iloc[0] == SERIES_LENGTH + 1
    assert results[timestamp_column].iloc[-1] - df[timestamp_column].iloc[-1] == FORECAST_LENGTH
    assert results.dtypes[timestamp_column] == df.dtypes[timestamp_column]


def test_forecast_with_float_timestamps(ts_data_base: pd.DataFrame, forecasting_input_base: ForecastingInferenceInput):
    input: ForecastingInferenceInput = copy.deepcopy(forecasting_input_base)
    df = copy.deepcopy(ts_data_base)

    timestamp_column = input.schema.timestamp_column
    df[timestamp_column] = [float(0.0) + x for x in range(1, SERIES_LENGTH * NUM_TIMESERIES + 1)]
    input.data = df.to_dict(orient="list")
    runtime: InferenceRuntime = InferenceRuntime()
    po: PredictOutput = runtime.forecast(input=input)
    results = pd.DataFrame.from_dict(po.results[0])
    assert results[timestamp_column].iloc[0] == SERIES_LENGTH + 1
    assert results[timestamp_column].iloc[-1] - df[timestamp_column].iloc[-1] == FORECAST_LENGTH
    assert results.dtypes[timestamp_column] == df.dtypes[timestamp_column]


def test_forecast_with_bogus_timestamps(ts_data_base: pd.DataFrame, forecasting_input_base: ForecastingInferenceInput):
    input: ForecastingInferenceInput = copy.deepcopy(forecasting_input_base)
    df = copy.deepcopy(ts_data_base)

    timestamp_column = input.schema.timestamp_column
    df[timestamp_column] = df[timestamp_column].astype(str)
    df[timestamp_column] = [str(x) for x in range(1, SERIES_LENGTH * NUM_TIMESERIES + 1)]
    input.data = df.to_dict(orient="list")
    runtime: InferenceRuntime = InferenceRuntime()
    with pytest.raises(HTTPException) as _:
        runtime.forecast(input=input)


def test_forecast_with_bogus_values(ts_data_base: pd.DataFrame, forecasting_input_base: ForecastingInferenceInput):
    input: ForecastingInferenceInput = copy.deepcopy(forecasting_input_base)
    df = copy.deepcopy(ts_data_base)
    df["VAL"] = df["VAL"].astype(str)
    df["VAL"] = [str(x) for x in range(1, SERIES_LENGTH * NUM_TIMESERIES + 1)]
    input.data = df.to_dict(orient="list")
    runtime: InferenceRuntime = InferenceRuntime()
    with pytest.raises(HTTPException) as _:
        runtime.forecast(input=input)


def test_forecast_with_bogus_model_id(ts_data_base: pd.DataFrame, forecasting_input_base: ForecastingInferenceInput):
    input: ForecastingInferenceInput = copy.deepcopy(forecasting_input_base)
    df = copy.deepcopy(ts_data_base)
    input.data = df.to_dict(orient="list")
    input.model_id = "hoo-hah"

    runtime: InferenceRuntime = InferenceRuntime()
    with pytest.raises(HTTPException) as _:
        runtime.forecast(input=input)


def test_forecast_with_insufficient_context_length(
    ts_data_base: pd.DataFrame, forecasting_input_base: ForecastingInferenceInput
):
    input: ForecastingInferenceInput = copy.deepcopy(forecasting_input_base)
    df = copy.deepcopy(ts_data_base)
    df = df.iloc[0:-100]

    input.data = df.to_dict(orient="list")

    runtime: InferenceRuntime = InferenceRuntime()
    with pytest.raises(HTTPException) as _:
        runtime.forecast(input=input)


@pytest.mark.skip
def test_forecast_with_nan_data(ts_data_base: pd.DataFrame, forecasting_input_base: ForecastingInferenceInput):
    input: ForecastingInferenceInput = copy.deepcopy(forecasting_input_base)
    df = copy.deepcopy(ts_data_base)
    df.iloc[0, df.columns.get_loc("VAL")] = np.nan

    input.data = df.to_dict(orient="list")

    runtime: InferenceRuntime = InferenceRuntime()
    # with pytest.raises(HTTPException) as _:
    runtime.forecast(input=input)


# @pytest.mark.skip
def test_forecast_with_missing_row(ts_data_base: pd.DataFrame, forecasting_input_base: ForecastingInferenceInput):
    input: ForecastingInferenceInput = copy.deepcopy(forecasting_input_base)
    df = copy.deepcopy(ts_data_base)
    df = df.drop(index=10)

    # append a row to give it the correct length
    # don't forget to update the timestamp accordingly in the
    # appended row

    input.data = df.to_dict(orient="list")

    runtime: InferenceRuntime = InferenceRuntime()
    with pytest.raises(HTTPException) as _:
        runtime.forecast(input=input)
