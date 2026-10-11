### Setup the banner categorization script

- install conda@26.1.1 <br>
- install Python 3.9.19 <br>
- OS should be linux, it was never tried on windows.

- Then run command at the root of the folder: conda env create -f environment.yml

When running for first time run the command: export FIREFOX_BINARY="$(command -v firefox-esr || command -v firefox)

Must have firefox installed alongside the geckodriver, if some error occur in regards to geckodriver when running for first time then just chatgpt it, most likely it will be some variable (perhaps the above one might need a little modification per your system) that needs to be set in the terminal before running the script.

- Run the script via: python run_crawl.py (python banner_detection.py does the same)

Input files are csv files inside input-files/, the first column must contain domains, remaining all will be ignored.

- python run_crawl.py crawls all files in URLS_FILES (config.py)
- python run_crawl.py blocking_banner.csv simple_non_blocking_banner.csv crawls only these files
- options: --workers N, --timeout S (seconds per site), --headless, --no-retry

Firefox windows are visible by default (HEADLESS in config.py). Don't minimize them or lock the screen while it runs, otherwise the pages stop scrolling (those sites are retried at the end).

Each site has a time limit (SITE_TIMEOUT), sites that time out or crash are retried once at the end of each file.

The output file will be named exactly as the input file but it will be in the root directory (not inside input-files folder). Columns: domain, url, category, closing_score, ..., branch (reason for the category), confidence, closed_by, scroll, reachable, keyboard, kind, secs. <br>
Screenshots etc. go to a folder named as the input file with -datadir appended. Inside 1-Starting_Point_0/:
- results/ one json file per site (sites that already have one are skipped, delete the -datadir folder for a fresh run)
- site_logs/ console output per site
- banner_screenshots/ "N domain.png" (used by update_closing_score.py) and "N domain_banner1.png"
- run.log one line per site

Categories: Simple, Static, Fixed, Blocking banner, plus "No banner", "Unreachable" (site did not load) and "Undetermined" (see the reason column).

### How a banner is categorized (banner_probe.py, banner_probe.js)
Order of the checks:
1. Escape (also after tabbing into the banner): closed -> Simple
2. Click on the grey backdrop / next to the banner: closed -> Simple
3. Scroll down and back up: scrolls away and comes back -> Static, gone -> Simple
4. Tab through the page (only recorded, keyboard column)
5. Clicks next to the banner and on a link outside it: reach the page -> Fixed, otherwise Blocking

- python run_crawl.py --reclassify [files] re-runs classify() on the saved json results and rebuilds the csv files (no browser)

### Evaluation
- python category_stats/evaluate.py compares the output csv files with the labels in input-files/, wrong ones go to category_stats/misclassified.csv

### Setup the banner sub-categorization script (close button presence)
- you must have already ran the banner_detection.py earlier and therefore must have xyz-datadir folder (where the screenshots are)
- adjust the BASE_NAMES array in the script update_closing_score.py (BASE_NAMES means the xyz part of the xyz-datadir folder)
- you might need to adjut base_url of LLM server and the LLM model itself in the script update_closing_score.py (I setup the LLM server on my other PC with LMStudio that let run any LLM given GPU supports it and let it expose locally on the server)
- then simply run: python update_closing_score.py

#### For my supervisors: contact me any time at my email to set it up on your system for testing or any purpose in case of any error, I will set it up quickly.