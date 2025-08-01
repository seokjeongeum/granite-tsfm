# Standard
import json
import sys
import traceback

import torch

from tsfmfinetuning.error_logging import write_termination_log
from tsfmfinetuning.finetuning import FinetuningRuntime
from tsfmfinetuning.ftargs import argparser
from tsfmfinetuning.ftpayloads import TinyTimeMixerForecastingTuneInput


# remote container space
def main():
    # ###########################3
    args, _ = argparser().parse_known_args()

    # reconstruct our input object
    # these come from a mutually exclusive group
    payload: dict = json.load(open(args.payload, "r"))
    # this will give us param validation

    if args.model_arch == "ttm" and args.task_type == "forecasting":
        input: TinyTimeMixerForecastingTuneInput = TinyTimeMixerForecastingTuneInput(**payload)
        ftr: FinetuningRuntime = FinetuningRuntime()
        ftr.finetuning(input=input, tuned_model_name=args.model_name, output_dir=args.target_dir)
    else:
        raise NotImplementedError(f"model arch/task type not implemented {args.model_arch_type} {args.task_type}")


if __name__ == "__main__":
    try:
        if torch.cuda.is_available() and torch.cuda.device_count() >= 1:
            print(f"{torch.cuda.device_count()} gpu device(s) are available for use.")
        else:
            print("no gpu or torch.cuda is not available, using CPU")
        main()
        sys.exit(0)
    except Exception as e:
        traceback.print_exception(e)
        write_termination_log(f"Exception when running finetuning {e}")
        sys.exit(1)
