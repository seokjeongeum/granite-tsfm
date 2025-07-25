# Standard

import tempfile
from pathlib import Path

import pytest
from tsfmfinetuning.finetuning import FinetuningRuntime
from tsfmfinetuning.ftpayloads import TinyTimeMixerForecastingTuneInput


PAYLOADS = [
    {
        "data": "file://./path/to/pandas.csv/or/pandas.feather/or/pandas.csv.gz",
        "model_id": "mytest-tsfm/ttm-r1",
        "schema": {
            "timestamp_column": "date",
            "target_columns": ["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL", "OT"],
        },
        "parameters": {
            "tune_prefix": "fine_tuned/",
            "trainer_args": {"num_train_epochs": 1, "per_device_train_batch_size": 256},
            "fewshot_fraction": 0.05,
        },
    }
]

file_data_uris = [
    "file://./data/ETTh1.feather",
    "file://./data/ETTh1.csv",
    "file://./data/ETTh1.csv.gz",
    "file://./data/multipart",
]


@pytest.mark.parametrize("uri", file_data_uris)
@pytest.mark.parametrize("payload", PAYLOADS)
def test_fine_tune_forecasting_with_local_io(uri, payload):
    payload["data"] = uri
    input: TinyTimeMixerForecastingTuneInput = TinyTimeMixerForecastingTuneInput(**payload)

    ftr: FinetuningRuntime = FinetuningRuntime()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tuned_model_name = "pytest_tuned_model"
        response = ftr.finetuning(input=input, tuned_model_name=tuned_model_name, output_dir=Path(tmp_dir))
        assert response.exists()
        assert (response / "config.json").exists() and (response / "config.json").stat().st_size > 0
