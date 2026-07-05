### Setup the banner categorization script

- install conda@26.1.1 <br>
- install Python 3.9.19 <br>
- OS should be linux, it was never tried on windows.

- Then run command at the root of the folder: conda env create -f environment.yml

When running for first time run the command: export FIREFOX_BINARY="$(command -v firefox-esr || command -v firefox)

Must have firefox installed alongside the geckodriver, if some error occur in regards to geckodriver when running for first time then just chatgpt it, most likely it will be some variable (perhaps the above one might need a little modification per your system) that needs to be set in the terminal before running the script.

- Run the script via: python banner_detection.py

In config.py, set the following variables per desired goal:

urls_file = "static_non_blocking_banner_stays_until_action.csv" # set this variable to the csv placed in input file, the first column must contain domains, remaining all will be ignored

XXX <br>
The output file that contains the domain and category will named exactly as the input file name but it will be in the root directory (not inside input-files folder). <br>
For data like screenshot, there will be an output folder with name as of input file name but with -datadir appended in its name.

### Setup the banner sub-categorization script (close button presence)
- you must have already ran the banner_detection.py earlier and therefore must have xyz-datadir folder (where the screenshots are)
- adjust the BASE_NAMES array in the script update_closing_score.py (BASE_NAMES means the xyz part of the xyz-datadir folder)
- you might need to adjut base_url of LLM server and the LLM model itself in the script update_closing_score.py (I setup the LLM server on my other PC with LMStudio that let run any LLM given GPU supports it and let it expose locally on the server)
- then simply run: python update_closing_score.py

#### For my supervisors: contact me any time at my email to set it up on your system for testing or any purpose in case of any error, I will set it up quickly.