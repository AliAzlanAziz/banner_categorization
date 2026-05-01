import os
import subprocess
from pathlib import Path

try:
    from ..config import *
except ImportError:
    try:
        from config import *
    except ImportError:
        raise ImportError("Failed to import config")

def make_url(domain: str, mode=URL_MODE):
    domain = domain.strip("\n")
    if "https://" in domain or "http://" in domain:
        url = domain
    else:
        if mode == 1:
            url = "https://" + domain
        elif mode == 2:
            url = "http://" + domain
        else:
            url = ""
    return url


def get_domains_set_global_domains(target_file_name):
    global domains, STEP_SIZE
    if ".csv" in target_file_name:
        sites_csv = pd.read_csv(target_file_name, header=None)
        num_rows = sites_csv.shape[0]
        print(f"Number of rows in the csv file: {num_rows}")

        # read from .csv file. from START_POINT to START_POINT + STEP_SIZE
        if num_rows < STEP_SIZE:
            STEP_SIZE = num_rows
        # below code is commented to test manual inspected files from custom csv first
        # domains = [
        #     make_url(sites_csv.iloc[row][1]) for row in range(START_POINT, START_POINT + STEP_SIZE)
        # ]
        domains.clear()
        domains.extend(
            make_url(sites_csv.iloc[row][0]) 
            for row in range(START_POINT, STEP_SIZE)
        )
        print(f"Number of domains to crawl: {len(domains)}")
    return domains


def get_profile_path():
    if DEFAULT_PROFILE_PATH:
        # Get a list of all files in the directory
        profiles_dir_all_files = os.listdir(PROFILES_PATH) # ./datadir/test-artifact/1-Starting_Point_0/profiles/"

        # Filter out directories, leaving only files
        files = [file for file in profiles_dir_all_files if os.path.isfile(os.path.join(PROFILES_PATH, file))]

        if files:
            # Get the most recently modified file
            last_modified_file = max(files, key=lambda x: os.path.getmtime(os.path.join(PROFILES_PATH, x)))

            # Get the full path of the last modified file
            last_modified_file_path = os.path.join(PROFILES_PATH, last_modified_file)
            
            return Path(last_modified_file_path)
    else:
        PROFILE_PATH = STATE_RUN_PATH / PROFILE_NAME # ./statefiles/test-artifact/cookiejar.tar
        # print("PROFILE_PATH: ", PROFILE_PATH)
        return Path(PROFILE_PATH)


def create_dirs_if_do_not_exist():
    try:
        original_umask = os.umask(0)
        if not os.path.exists(data_dir): # ./datadir/test-artifact/1-Starting_Point_0/
            os.makedirs(data_dir, 0o0777)
        if not STATE_RUN_PATH.exists(): # ./statefiles/test-artifact/
            STATE_RUN_PATH.mkdir(mode=0o0777, parents=True)

        if not PROFILES_PATH.exists(): # ./datadir/test-artifact/1-Starting_Point_0/profiles/
            PROFILES_PATH.mkdir(
                parents=True,
                exist_ok=True,
            )
        if not DBBACKUP_PATH.exists(): # ./datadir/test-artifact/1-Starting_Point_0/crawl-data.sqlite
            DBBACKUP_PATH.mkdir(
                parents=True,
                exist_ok=True,
            )
    finally:
        os.umask(original_umask)

    # setting the temp directory
    os.makedirs(name=BC_TEMP_DIR, mode=0o0777, exist_ok=True) # the directory to store the temporary profile and database files, for example "/home/$user/tmp/"
    os.environ['TMPDIR'] = BC_TEMP_DIR
    print(subprocess.check_output("echo $TMPDIR", shell=True, text=True))