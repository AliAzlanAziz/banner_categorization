### Setup the script

- install conda@26.1.1 <br>
- install Python 3.9.19 <br>
- OS should be linux, it was never tried on windows.

- Then run command at the root of the folder: conda env create -f environment.yml

When running for first time run the command: export FIREFOX_BINARY="$(command -v firefox-esr || command -v firefox)

Must have firefox installed alongside the geckodriver, if some error occur in regards to geckodriver when running for first time then just chatgpt it, most likely it will be some variable (perhaps the above one might need a little modification per your system) that needs to be set in the terminal before running the script.

- Run the script via: python banner_detection.py

In config.py, set the following variables per desired goal:

urls_file = "simple_non_blocking_banner.csv" # set this variable to the csv placed in input file, the first column must contain domains, remaining all will be ignored

XXX <br>
The output file that contains the domain and category will named exactly as the input file name but it will be in the root directory (not inside input-files folder). <br>
For data like screenshot, there will be an output folder with name as of input file name but with -datadir appended in its name.

#### For my supervisors: contact me any time at my email to set it up on your system for testing or any purpose in case of any error, I will set it up quickly.