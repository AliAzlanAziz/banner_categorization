import logging
import time
from datetime import datetime
import pandas as pd
import random

from selenium.webdriver import Firefox
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException, MoveTargetOutOfBoundsException

from .config import log_file
from .banner_detection import bc

# Constants for bot mitigation
NUM_MOUSE_MOVES = 10  # Times to randomly move the mouse
RANDOM_SLEEP_LOW = 1  # low (in sec) for random sleep between page loads
RANDOM_SLEEP_HIGH = 7  # high (in sec) for random sleep between page loads


def init(headless, num_browsers, num_repetitions):
    bc.init(headless, num_browsers, num_repetitions, web_driver=1)


def scroll_down(driver):
    at_bottom = False
    while random.random() > 0.20 and not at_bottom:
        driver.execute_script(
            "window.scrollBy(0,%d)" % (10 + int(200 * random.random()))
        )
        at_bottom = driver.execute_script(
            "return (((window.scrollY + window.innerHeight ) + 100 "
            "> document.body.clientHeight ))"
        )
        time.sleep(0.5 + random.random())


def bot_mitigation(webdriver):
    """Performs three optional commands for bot-detection mitigation when getting a site"""

    # bot mitigation 1: move the randomly around a number of times
    window_size = webdriver.get_window_size()
    num_moves = 0
    num_fails = 0
    while num_moves < NUM_MOUSE_MOVES + 1 and num_fails < NUM_MOUSE_MOVES:
        try:
            if num_moves == 0:  # move to the center of the screen
                x = int(round(window_size["height"] / 2))
                y = int(round(window_size["width"] / 2))
            else:  # move a random amount in some direction
                move_max = random.randint(0, 500)
                x = random.randint(-move_max, move_max)
                y = random.randint(-move_max, move_max)
            action = ActionChains(webdriver)
            action.move_by_offset(x, y)
            action.perform()
            num_moves += 1
        except MoveTargetOutOfBoundsException:
            num_fails += 1
            pass

    # bot mitigation 2: scroll in random intervals down page
    scroll_down(webdriver)

    # bot mitigation 3: randomly wait so page visits happen with irregularity
    time.sleep(random.randrange(RANDOM_SLEEP_LOW, RANDOM_SLEEP_HIGH))


def close_other_windows(webdriver):
    """
    close all open pop-up windows and tabs other than the current one
    """
    main_handle = webdriver.current_window_handle
    windows = webdriver.window_handles
    if len(windows) > 1:
        for window in windows:
            if window != main_handle:
                webdriver.switch_to.window(window)
                webdriver.close()
        webdriver.switch_to.window(main_handle)


def tab_restart_browser(webdriver):
    """kills the current tab and creates a new one to stop traffic"""
    # note: this technically uses windows, not tabs, due to problems with
    # chrome-targeted keyboard commands in Selenium 3 (intermittent
    # nonsense WebDriverExceptions are thrown). windows can be reliably
    # created, although we do have to detour into JS to do it.
    close_other_windows(webdriver)

    if webdriver.current_url.lower() == "about:blank":
        return

    # Create a new window.  Note that it is not practical to use
    # noopener here, as we would then be forced to specify a bunch of
    # other "features" that we don't know whether they are on or off.
    # Closing the old window will kill the opener anyway.
    webdriver.execute_script("window.open('')")

    # This closes the _old_ window, and does _not_ switch to the new one.
    webdriver.close()

    # The only remaining window handle will be for the new window;
    # switch to it.
    assert len(webdriver.window_handles) == 1
    webdriver.switch_to.window(webdriver.window_handles[0])


def clear_all_browser_data(webdriver: Firefox):
    # Delete all cookies
    webdriver.delete_all_cookies()

    # Clear cache (Firefox-specific via about:config / devtools workaround)
    webdriver.execute_script("""
        try {
            caches.keys().then(function(names) {
                for (let name of names)
                    caches.delete(name);
            });
        } catch(e) {}
    """)

    # 2. Storage + advanced cleanup (can fail depending on context)
    try:
        webdriver.execute_script("""
            // local/session storage
            window.localStorage.clear();
            window.sessionStorage.clear();

            // IndexedDB
            if (window.indexedDB && indexedDB.databases) {
                indexedDB.databases().then(dbs => {
                    dbs.forEach(db => indexedDB.deleteDatabase(db.name));
                });
            }

            // Cache API
            if (window.caches) {
                caches.keys().then(names => {
                    names.forEach(name => caches.delete(name));
                });
            }

            // Service workers
            if (navigator.serviceWorker) {
                navigator.serviceWorker.getRegistrations().then(regs => {
                    regs.forEach(reg => reg.unregister());
                });
            }
        """)
    except WebDriverException:
        pass  # ignore script execution issues


class Data:
    url = ""
    ttw = 0
    sql_addr = None
    status = None
    index = None
    banners = []
    banners_data = []
    CMP = {}


class BannerCategorization():
    """
    run all the Get, Bannerdetection, BannerCategorization and SetEntry Command in one single command.
    """

    def __init__(self, url, sleep, index, choice, goal="no"):
        self.logger = logging.getLogger("openwpm")
        self.url = url
        self.sleep = sleep
        self.index = index
        self.choice = choice
        self.goal = goal

    def __repr__(self):
        return f"BannerCategorization({self.url},{self.sleep},{self.index},{self.timeout},{self.choice},{self.goal})"

    def init_data(self):
        Data.url = self.url
        Data.index = self.index
        Data.sleep = self.sleep
        Data.choice = self.choice
        Data.goal = self.goal
        Data.ttw = 0
        Data.btn_status = {"btn_status": 0, "btn_set_status": 0}
        Data.nc_cmp_name = None
        Data.banners = []
        Data.banners_data = []
        Data.CMP = {}
        Data.interact_time = 0
        Data.start_time = datetime.now()
        Data.finish_time = 0
        Data.visit_id = self.visit_id
        Data.lang = None
        Data.category = "Unknown Yet"


    def clear_data_and_get_site(self, webdriver):
        print("clearing data and getting site again for url: ", self.url)
        clear_all_browser_data(webdriver)
        tab_restart_browser(webdriver)
        webdriver.get(self.url)
        # Close modal dialog if exists
        try:
            WebDriverWait(webdriver, 2).until(EC.alert_is_present())
            alert = webdriver.switch_to.alert
            alert.dismiss()
            time.sleep(0.1)
        except (TimeoutException, WebDriverException):
            pass

    def execute(
        self,
        webdriver: Firefox,
    ) -> None:
        try:
            error_flag = False
            try:
                tab_restart_browser(webdriver)
                webdriver.set_page_load_timeout(self.timeout)
                bc.set_webdriver(webdriver)
                time.sleep(1)
            except:
                pass

            try:
                webdriver.get(self.url)
                Data.status = 0
            except Exception as E:
                try:
                    if bc.URL_MODE == 3:
                        raise E
                    self.url = self.url.replace('://', '://www.')
                    webdriver.get(self.url)
                    Data.status = 0
                except TimeoutException:  # timeout
                    Data.status = 1
                    error_flag = True
                except Exception as E:  # unreachable
                    Data.status = 2
                    error_flag = True

            # Close modal dialog if exists
            try:
                WebDriverWait(webdriver, 2).until(EC.alert_is_present())
                alert = webdriver.switch_to.alert
                alert.dismiss()
                time.sleep(0.1)
            except (TimeoutException, WebDriverException):
                pass

            try:
                try:
                    try:
                        close_other_windows(webdriver)
                    except:
                        pass
                    Data.start_time = datetime.now()
                    if browser_params.bot_mitigation:
                        print("running bot mitigation for url: ", self.url)
                        bot_mitigation(webdriver)
                    # current_url = webdriver.current_url

                    # Don't run banner detection if choice is 0
                    self.init_data()
                    if not bc.BANNERCLICK:
                        time.sleep(self.sleep)
                except:
                    pass

                # # Run banner detection and interaction
                else:
                    if not error_flag:
                        time.sleep(8) ## wait so the banner loads perfectly for the screenshot
                        
                        banners = []
                        banners = bc.run_banner_detection(Data)
                        
                        if len(banners) == 0:
                            Data.category = "No banner" # if there is no banner, it will not be in the table, simple search by table "visits" column "banners"=0

                        Data.banners = banners
                        Data.banners_data = bc.extract_banners_data(banners)

                        print(f"number of detected banners for url {self.url} is: ", len(Data.banners))
                        print(f"number of detected banners for url {self.url} is: ", len(Data.banners_data))

                        detect_banner_category_start_time = time.perf_counter()

                        if len(banners) > 0:
                            # clear all data, start new tab and navigate to the domain again and dismiss alert if there
                            try:
                                # self.clear_data_and_get_site(webdriver)
                                for i, _ in enumerate(Data.banners):
                                    banner_closed, is_navigated, is_scrolled, is_text_selected, clicked, url_changed, banner_category, branch, z_index, position, pointer_events = bc.detect_banner_category(Data, i)

                                    new_row = pd.DataFrame([
                                        [self.url, banner_category, 
                                        f"banner_closed:{banner_closed}", f"is_navigated:{is_navigated}", 
                                        f"is_scrolled:{is_scrolled}", f"is_text_selected:{is_text_selected}", 
                                        f"clicked:{clicked}", f"url_changed:{url_changed}", f"branch:{branch}", f"z_index:{z_index}", f"position:{position}", f"pointer_events:{pointer_events}"]])
                                    new_row.to_csv("bd_restest_wrong.csv", mode="a", header=False, index=False)

                                    Data.banners_data[i]['category'] = banner_category
                            except Exception as ex:
                                with open(log_file, 'a+') as f:
                                    print("skipping category detection: failed in clear_data_and_get_site for url: " + self.url + " " + ex)
                                    print("skipping category detection: failed in clear_data_and_get_site for url: " + self.url + " " + ex.__str__(), file=f)
                        else:
                            new_row = pd.DataFrame([
                                [self.url, "No banner", "banner_closed:Unknown", "is_navigated:Unknown", "is_scrolled:Unknown", 
                                 "is_text_selected:Unknown", "clicked:Unknown", "url_changed:Unknown", "branch:Unknown", "z_index:Unknown", "position:Unknown", "pointer_events:Unknown"]])
                            new_row.to_csv("bd_restest_wrong.csv", mode="a", header=False, index=False)

                        detect_banner_category_end_time = time.perf_counter()

                        elapsed_seconds = int(detect_banner_category_end_time - detect_banner_category_start_time)
                        print(f"elapsed_seconds: {elapsed_seconds} for url: {self.url}")

                        if elapsed_seconds < 90:
                            # if bc.INTRACTABLE and ("stateful" in self.goal):
                                # Data.finish_time = bc.halt_for_sleep(Data.start_time, 30)
                            # if (bc.WAITANYWAY or self.choice) and banners:
                                # Data.finish_time = bc.halt_for_sleep(Data.start_time, Data.sleep)
                            Data.finish_time = bc.halt_for_sleep(Data.start_time, 91-elapsed_seconds)
                        else:
                            print("elapsed time for category detection is already more than 90 seconds, so not sleeping anymore for url: ", self.url)
                            Data.finish_time = datetime.now()
                    else:
                        bc.take_current_page_sc(Data)

                    bc.set_data_in_db_error(Data)

            except Exception as ex:
                with open(log_file, 'a+') as f:
                    print("failed in BannerCategorization for url (first): " +self.url + " " + ex.__str__(), file=f)
                    bc.MyExceptionLogger(err=ex, file=f)

            if error_flag:
                pass

            try:
                self.logger.info("BannerCategorization command is successfully executed and result for {} is: number of banners {} with index: {}.".format(self.url, len(Data.banners), self.index))
            except Exception as ex:
                with open(log_file, 'a+') as f:
                    print("failed in BannerCategorization for url: " + self.url + " " + ex.__str__(), file=f)
                    # bc.MyExceptionLogger(err=ex, file=f)
        except Exception as ex:
            with open(log_file, 'a+') as f:
                print("failed in BannerCategorization for url: " + self.url + " " + ex.__str__(), file=f)
                bc.MyExceptionLogger(err=ex, file=f)
