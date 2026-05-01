#!/usr/bin/env python
import traceback
import argparse
import time
from .utility.runUtils import create_dirs_if_do_not_exist
from .config import *

from datetime import datetime

from commands import (
    init,
    BannerCategorization,
)

# parse the command line arguments
parser = argparse.ArgumentParser()

parser.add_argument(
    "--headless", action="store_true", help="start on headless mode"
)
parser.add_argument(
    "--num-browsers", type=int, default=1, help="Number of browser instances"
)
parser.add_argument(
    "--num-repetitions", type=int, default=1, help="Number of repetitions per website"
)
parser.add_argument(
    "--bannerclick", action="store_true", help="Run banner click custom command"
)
args = parser.parse_args()
HEADLESS = args.headless
NUM_BROWSERS = args.num_browsers

create_dirs_if_do_not_exist()

init(HEADLESS, NUM_BROWSERS, args.num_repetitions)

start_time = datetime.now()
with open(log_file, "a+") as f:
    init_str = "started at: " + start_time.strftime("%H-%M-%S").__str__()
    print(init_str, file=f)

site = "init"
index = 0
counter = 0
error_count = 0

visit_ids = None

sites = domains
print("number of sites: ", len(sites))
start = 0
end = len(sites)
step = 1

try:
    for site_index in range(start, end, step):
        try:
            site = sites[site_index]

            if args.bannerclick:
                print("core args.bannerclick")
                if counter != 0 and counter % SAVE_PROFILE_STEP == 0 and SAVE_PROFILE:
                    print("counter != 0 and counter % SAVE_PROFILE_STEP == 0 and SAVE_PROFILE")
                    print(f"{counter} != 0 and {counter} % {SAVE_PROFILE_STEP} == 0 and {SAVE_PROFILE}")

                    BannerCategorization(url=site, sleep=SLEEP_TIME, index=site_index, choice=CHOICE, goal="stateful_phase")
            
            error_count = 0
        except:
            if error_count >= 10:
                raise
            error_count += 1
        finally:
            counter += 1
    print("all tasks are completed, and the 'with' block has exited.")
except Exception as e:
    try:
        print("=" * 60)
        print(traceback.format_exc())
        print(f"{type(e)}, {str(e)}")
        print("Exception in manager 2")
        print("=" * 60)
    except:
        pass
finally:
    print("run finished")
    
    print("last finally block to close manager")

    time.sleep(TERMINATION_SLEEP_TIME)

    print("closing the manager")

    print("manager closed")

    finish_time = datetime.now()
    completion_time = finish_time - start_time
    
    with open(log_file, "a+") as f:
        init_str = (
            "finished at: " + finish_time.strftime("%H-%M-%S").__str__()
            + "\n"
            "completion time(min): "+ str(completion_time.total_seconds() / 60)
        )
        print(init_str, file=f)

    exit()
