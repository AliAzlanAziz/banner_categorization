import random
import time
import pyperclip

import html.parser
import threading
from datetime import datetime
from PIL import Image
import traceback
import sys
import requests

import cv2
import numpy as np

from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    MoveTargetOutOfBoundsException,
    InvalidSessionIdException
)
from selenium.webdriver.firefox.options import Options

try:
    from .utility.utilityMethods import *
except ImportError:
    try:
        from utility.utilityMethods import *
    except ImportError:
        raise ImportError("Failed to import utilityMethods")

try:
    from .config import *
except ImportError:
    try:
        from config import *
    except ImportError:
        raise ImportError("Failed to import config")
    
    
try:
    from .utility.runUtils import get_domains_set_global_domains
except ImportError:
    try:
        from utility.runUtils import get_domains_set_global_domains
    except ImportError:
        raise ImportError("Failed to import utility.runUtils")

rej_flag = False


def MyExceptionLogger(err, file):
    # return
    traceback_details = traceback.format_exc()
    print(traceback_details, file=file)
    exc_type, exc_value, exc_traceback = sys.exc_info()
    print(f"Exception type: {exc_type}, Value: {exc_value}", file=file)
    traceback.print_tb(exc_traceback, file=file)


def reset():
    global counter, driver, visit_db, domains, this_domain, this_url, banner_db, html_db, this_lang, this_banner_lang, this_run_url
    counter = 0
    driver = None
    visit_db = None
    banner_db = None
    html_db = None
    domains = []
    this_domain = None
    this_url = None
    this_run_url = None
    this_lang = None
    this_banner_lang = None


def set_zoom(driver, zoom_level):
    # Ensure the zoom level is a decimal like 0.8 for 80%, 1.0 for 100%, etc.
    driver.execute_script(f"document.body.style.zoom='{zoom_level}';")


def run_webdriver():
    options = Options()
    options.binary_location = "/snap/firefox/current/usr/lib/firefox/firefox" # Mozilla Firefox 149.0.2, gecko 36
        
    if HEADLESS:
        options.add_argument("--headless")

    # Notifications
    options.set_preference("dom.webnotifications.enabled", False)
    options.set_preference("dom.push.enabled", False)

    # Microphone / 🎥 Camera
    options.set_preference("media.navigator.permission.disabled", True)
    options.set_preference("permissions.default.microphone", 2)
    options.set_preference("permissions.default.camera", 2)

    # Location (Geolocation)
    options.set_preference("geo.enabled", False)
    options.set_preference("permissions.default.geo", 2)

    # Screen sharing
    options.set_preference("permissions.default.desktop-notification", 2)

    # Persistent storage / IndexedDB prompts
    options.set_preference("permissions.default.persistent-storage", 2)

    # Autoplay (audio/video)
    options.set_preference("media.autoplay.default", 5)

    # Clipboard access
    options.set_preference("dom.events.asyncClipboard.readText", False)
    options.set_preference("dom.events.asyncClipboard.writeText", False)

    # WebRTC (IP leak + device access)
    options.set_preference("media.peerconnection.enabled", False)

    # DRM / protected content
    options.set_preference("media.eme.enabled", False)

    # Disable password save prompts
    options.set_preference("signon.rememberSignons", False)

    # Disable popup blocking UI (optional)
    options.set_preference("dom.disable_open_during_load", False)

    # Deny all unknown permission requests by default
    options.set_preference("permissions.default.image", 1)  # (1=allow, 2=block if needed)

    driver = webdriver.Firefox(options=options)

    driver.set_page_load_timeout(120)
    # driver.set_window_size(1854, 1048)
    driver.maximize_window()
    
    return driver


driver_ref = {"driver": None, "done": False, "restart": False, "in_processing": False, "watchdog_thread": None}


def quit_current_driver_and_start_new_webdriver(data):
    try:
        global driver, this_domain, driver_ref

        print('quit_current_driver_and_start_new_webdriver  driver_ref["in_processing"] = True')
        driver_ref["in_processing"] = True

        if driver_ref["watchdog_thread"] and driver_ref["watchdog_thread"].is_alive():
            driver_ref["done"] = True
            time.sleep(3)
            driver_ref["watchdog_thread"].join()
            driver_ref["done"] = False
            try:
                driver_ref["driver"].quit()
            except Exception as ex:
                print("Exception while quiting driver in quite_current_driver_and_start_new_webdriver")
                pass

        print("starting new driver")
        driver = run_webdriver()
        driver_ref["driver"] = driver

        print("starting new thread for new driver")
        driver_ref["watchdog_thread"] = threading.Thread(target=watchdog, args=(this_domain,))
        driver_ref["watchdog_thread"].start()

        print("navigating to same data url for new driver to stay consistent")
        error_flag = reopen_domain_page(data.url, driver_ref["driver"])

        driver_ref["in_processing"] = False
        if error_flag:
            print("error while reopening domain page after starting new driver")
            return None

        return driver
    except Exception as ex:
        driver_ref["in_processing"] = False
        print("Exception in quit_current_driver_and_start_new_webdriver")
        print(f"{traceback.format_exc()}")
        return None
    

def get_webdriver_after_tab_restart():
    time.sleep(1)
    global driver

    if not driver or driver is None:
        print("get_webdriver_after_tab_restart: waiting for driver to be available")
        time.sleep(5)

    return driver


def init_pc(headless=HEADLESS, num_browsers=NUM_BROWSERS, num_repetitions=1):  # initialize bannerdetection by setting url file and webdriver instance
    global domains, file
    
    create_data_dirs()

    file = "./input-files/" + urls_file
    if os.path.isfile(file):
        domains = get_domains_set_global_domains(file)

    init_str = f"""Crawl initialized for: {file} in {datetime.now().strftime("%H-%M-%S").__str__()}
    START_POINT:STEP_SIZE: {START_POINT}:{STEP_SIZE}
    headless: {headless}
    num_browsers: {num_browsers}
    num_repetitions: {num_repetitions}
    translation: {TRANSLATION}
    delay_time: {SLEEP_TIME}
    ATTEMPTS: ATTEMPT_STEP_SLEEP_TIME: {ATTEMPTS}: {ATTEMPT_STEP_SLEEP_TIME}
    Chrome: {CHROME}
    Watchdog: {WATCHDOG}
    interaction choice: {"ALL"}
    non explicit: {NON_EXPLICIT}
    SIMPLE_DETECTION: {SIMPLE_DETECTION}
    search for reject btn in setting: {REJ_IN_SET}
    NC_ADDON: {NC_ADDON}
    mobile agent: {MOBILE_AGENT}\n\n""" + "__"*30 + "\n"
    print(init_str)

    try:
        with open(log_file, 'a+') as f:
            print(init_str, file=f)
    except:
        pass


def create_data_dirs():
    if not os.path.exists(season_dir):
        os.makedirs(season_dir)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    if not os.path.exists(sc_dir):
        os.makedirs(sc_dir)
    if not os.path.exists(nobanner_sc_dir):
        os.makedirs(nobanner_sc_dir)


def reopen_domain_page(url, driver):
    error_flag = False

    try:
        driver.get(url)
    except TimeoutException as ex:
        error_flag = True
        with open(log_file, 'a+') as f:
            print("failed to get (TimeOut): " + url + " " + traceback.format_exc(), file=f)
    except WebDriverException as ex:
        error_flag = True
        with open(log_file, 'a+') as f:
            print("failed to get (unreachable): " + url + " " + traceback.format_exc(), file=f)

    if not error_flag:
        time.sleep(10) # let the page load

        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        ActionChains(driver).send_keys(Keys.ESCAPE).pause(random.uniform(0.5, 1)).perform()
        ActionChains(driver).send_keys(Keys.ESCAPE).pause(random.uniform(0.5, 1)).perform()

        # Close modal dialog if exists
        try:
            WebDriverWait(driver, 2).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            alert.dismiss()
            time.sleep(0.1)
        except (TimeoutException, WebDriverException):
            pass

    return error_flag


def open_domain_page(domain):
    global driver, this_url, this_domain, this_status
    mode = 1
    while True:
        url = make_url(domain, mode)

        if url == '' or mode > 3:
            break

        try:
            driver.get(url)
            this_status = 0
            break
        except TimeoutException as ex:
            with open(log_file, 'a+') as f:
                print("failed to get (TimeOut): " + url + "\n" + traceback.format_exc(), file=f)
                MyExceptionLogger(err=ex, file=f)
            this_status = 1
        except WebDriverException as ex:
            with open(log_file, 'a+') as f:
                print("failed to get (unreachable): " + url + "\n" + traceback.format_exc(), file=f)
                MyExceptionLogger(err=ex, file=f)
            this_status = 2
        except Exception as ex:
            with open(log_file, 'a+') as f:
                print("failed to get (Exception): " + url + "\n" + traceback.format_exc(), file=f)
                MyExceptionLogger(err=ex, file=f)
            this_status = 2
        finally:
            mode += 1

    this_domain = domain
    this_url = url
    
    if this_status == 0:
        time.sleep(10) # let the page load
        
        # Close modal dialog if exists
        try:
            WebDriverWait(driver, 2).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            alert.dismiss()
            time.sleep(0.1)
        except (TimeoutException, WebDriverException):
            pass
    
    return url


def find_cookie_banners(origin_el=None, translate=False, stale_flag=False):
    # TODO: WITHOUT EXCEPTION HANDLING
    global driver, this_lang
    try:
        banners = []
        banners_map = dict()

        if origin_el is None:
            wait = WebDriverWait(driver, 2)
            body_el = wait.until(ec.visibility_of_element_located((By.TAG_NAME, "body")))

            time.sleep(1)
            WebDriverWait(driver, 1).until(lambda d: d.execute_script('return document.readyState') == 'complete')

            origin_el = body_el
            shadowdom_flag = False
        else:
            shadowdom_flag = True

        if translate:
            detected_lang = this_lang
            els_with_cookie = find_els_with_cookie(origin_el, detected_lang)
        else:
            detected_lang = "en"
            els_with_cookie = find_els_with_cookie(origin_el)
        if els_with_cookie:
            banners_map = find_fixed_ancestors(els_with_cookie)
            if not banners_map:
                banners_map = find_by_zindex(els_with_cookie)
            if not banners_map:
                banners_map[origin_el] = find_deepest_el(els_with_cookie)
            for item in banners_map.items():
                optimal_el = find_optimal(driver, item)
                if is_inside_viewport(optimal_el) and has_enough_word(optimal_el) and not is_signin_banner(optimal_el):
                    banners.append(optimal_el)
        # check all the iframes to detect cookie banners
        frame_pairs = find_CMP_cookies_iframes(driver, detected_lang)
        for frame_pair in frame_pairs:
            # check if the banner is in viewport
            if is_inside_viewport(frame_pair[0]):
                banners.append(frame_pair)
        if not banners and not shadowdom_flag:
            shadowdom_banners = find_shadowdom_banners(driver)
            for dom_pair in shadowdom_banners:
                banners.append(dom_pair)
                # if is_inside_viewport(dom_pair[0]):  # check if the banner is in viewport

        if not banners or len(banners) == 0:
            wait = WebDriverWait(driver, 2)
            body_el = wait.until(ec.visibility_of_element_located((By.TAG_NAME, "body")))

            time.sleep(1)
            WebDriverWait(driver, 1).until(lambda d: d.execute_script('return document.readyState') == 'complete')

            origin_el = body_el
            
            if translate:
                detected_lang = this_lang
                els_with_cookie = find_els_with_cookie2(origin_el, detected_lang)
            else:
                detected_lang = "en"
                els_with_cookie = find_els_with_cookie2(origin_el)
            if els_with_cookie:
                banners_map = find_fixed_ancestors(els_with_cookie)
                if not banners_map:
                    banners_map = find_by_zindex(els_with_cookie)
                if not banners_map:
                    banners_map[origin_el] = find_deepest_el(els_with_cookie)
                for item in banners_map.items():
                    optimal_el = find_optimal(driver, item)
                    if is_inside_viewport(optimal_el) and has_enough_word(optimal_el) and not is_signin_banner(optimal_el):
                        banners.append(optimal_el)

        return banners
    except StaleElementReferenceException as e:  # handle specific exception
        time.sleep(1)
        if not stale_flag:
            return find_cookie_banners(stale_flag=True)
        raise e
    except Exception as e:  # Catch any other exceptions
        raise e
        # return banners


def find_shadowdom_banners(driver):
    banners = []
    # root_copy_pairs_js = add_shadow_dom_to_body(driver)
    root_copy_pairs = add_shadow_dom_to_body(driver)
    for root_copy_pair in root_copy_pairs:
        shadow_dom_banner = find_cookie_banners(origin_el=root_copy_pair[1])
        if shadow_dom_banner:
            banners.append((root_copy_pair[0], shadow_dom_banner[0]))

    return banners


def detect_banners(data, running_for_category_detection=False):  # return banners of the current running url
    global driver, this_url, this_domain, this_status, this_lang, this_index
    banners = []
    if not running_for_category_detection:
        inc_counter()
    try:
        if not data.url:
            return banners
        if not running_for_category_detection:
            this_index = data.index
            this_url = data.url
            this_domain = data.domain
            this_lang = None
        time.sleep(3)
        banners = find_cookie_banners()
        if not running_for_category_detection:
            this_lang = page_lang(driver)
        data.lang = this_lang
        if ATTEMPTS:
            for att in range(ATTEMPTS):
                if banners:
                    break
                time.sleep(ATTEMPT_STEP_SLEEP_TIME)
                if not banners:
                    banners = find_cookie_banners()
                else:
                    return banners
                
                if not running_for_category_detection:
                    data.ttw = (att + 1) * ATTEMPT_STEP_SLEEP_TIME
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("failed to continue detecting banner for domain: " + data.domain + " " + traceback.format_exc(), file=f)
            # MyExceptionLogger(err=ex, file=f)
        if not running_for_category_detection:
            this_status = 3
            data.status = this_status
    return banners


def suffix(choice):
    global rej_flag
    if choice == 1:
        return "_XX" + 'acc'
    elif choice == 2:
        return "_XX" + 'rej' + ('INset' if rej_flag else '')
    elif choice == 3:
        return "_X" + 'set'
    elif choice == 4:
        return "_X" + 'log'
    elif choice == 5:
        return "_XX" + 'conbtn'
    elif choice == 6:
        return "_X" + 'log'
    elif choice == 7:
        return "_XX" + 'login'


def get_banner_obj(banner_item):
    global driver
    shadow_host = None
    if type(banner_item) is tuple:
        frame = banner_item[0]
        banner = banner_item[1]
        try:
            driver.switch_to.frame(frame)
            if type(banner) is tuple:
                frame = banner[0]
                banner = banner[1]
                driver.switch_to.frame(frame)
        except:  # for shadow root
            banner = banner_item[1]
            shadow_host = banner_item[0]
    else:
        banner = banner_item
    return banner, shadow_host


def get_sc_file_name(index=None, url=None):
    global driver, visit_db, this_url
    if url is None:
        url = this_url
    if index is None:
        return str(visit_db.shape[0]) + " " + get_current_domain(driver, url)
    else:
        return str(index+1) + " " + get_current_domain(driver, url)


def take_current_page_sc(data=None, suffix=""):
    global driver, SCREENSHOT
    if SCREENSHOT:
        if data is None:
            index = this_index
            url = this_url
        else:
            index = data.index
            url = data.url
        try:
            driver.save_screenshot(sc_dir + get_sc_file_name(index, url) + suffix + ".png")
        except Exception as ex:
            if "cross-origin" in  traceback.format_exc():
                try:
                    driver.switch_to.default_content()
                    driver.save_screenshot(sc_dir + get_sc_file_name(index, url) + suffix + ".png")
                    return
                except Exception as ex:
                    pass
            with open(log_file, 'a+') as f:
                print("failed to take screenshot for url: " + url + " " + traceback.format_exc(), file=f)


def inc_counter():
    global counter
    counter += 1


def take_banner_sc(banner_item, data, j=None):
    if banner_item:
        try:
            banner, _ = get_banner_obj(banner_item)
        except Exception as ex:
            with open(log_file, 'a+') as f:
                print("failed in switching in banner_sc section for : " + this_url + " " + traceback.format_exc(), file=f)
                MyExceptionLogger(err=ex, file=f)
            return
        try:
            if j is not None:
                if CHROME:
                    # chrome does not have built-in function for taking screenshot of an element.
                    chrome_element_sc(banner, data.index, data.url, j)
                else:
                    banner.screenshot(sc_dir + get_sc_file_name(this_index) + "_banner" + str(j + 1) + ".png")
            else:
                banner.screenshot(sc_dir + get_sc_file_name(this_index) + "_banner" + ".png")
            if type(banner_item) is tuple:
                driver.switch_to.default_content()
        except Exception as ex:
            with open(log_file, 'a+') as f:
                print("failed in switching in banner_sc section for : " + this_url + " " + traceback.format_exc(), file=f)
                # MyExceptionLogger(err=ex, file=f)
        return banner


def chrome_element_sc(banner, index, url, j):
    print("taking sc for banner element chrome way")
    location = banner.location
    size = banner.size
    ax = location['x']
    ay = location['y']
    width = location['x'] + size['width']
    height = location['y'] + size['height']
    crop_image = Image.open(sc_dir + get_sc_file_name(index, url) + ".png")
    with open(log_file, 'a+') as f:
        print(f"chrome_element_sc Banner coordinates for url: {url} (ax: {ax}, ay: {ay}, width: {width}, height: {height})", file=f)
        print(f"chrome_element_sc Banner coordinates for url: {url} (ax: {ax}, ay: {ay}, width: {width}, height: {height})")
    crop_image = crop_image.crop((ax, ay, width, height))
    crop_image.save(sc_dir + get_sc_file_name(index) + "_banner" + str(j + 1) + ".png")


class EssentialHTMLParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.essential_html = ""
        self.in_footer = False
        self.in_img = False
        self.in_script = False
        self.in_hidden = False

    def handle_starttag(self, tag, attrs):
        if tag in ['footer', 'img', 'script', 'hidden']:
            self.in_footer = tag == 'footer'
            self.in_img = tag == 'img'
            self.in_script = tag == 'script'
            self.in_hidden = tag == 'hidden'
            return

        if not self.in_footer and not self.in_img and not self.in_script and not self.in_hidden:
            attributes = []
            for attr, value in attrs:
                if attr in ['id', 'name']:
                    attributes.append(f'{attr}="{value}"')
                elif attr == 'class' and ('btn' in value or 'button' in value):
                    attributes.append(f'{attr}="{value}"')

            self.essential_html += f"<{tag} {' '.join(attributes)}>".replace(" ", " ")

    def handle_endtag(self, tag):
        if tag in ['footer', 'img', 'script', 'hidden']:
            self.in_footer = False
            self.in_img = False
            self.in_script = False
            self.in_hidden = False
            return

        if not self.in_footer and not self.in_img and not self.in_script and not self.in_hidden:
            self.essential_html += f"</{tag}>"

    def handle_data(self, data):
        if not self.in_footer and not self.in_img and not self.in_script and not self.in_hidden:
            self.essential_html += data


def is_missed(html):
    soup = bs(html, "html.parser")
    plain_text = soup.get_text()
    character_count = len(plain_text)
    return character_count < 100


def extract_essential_html(html_dom):
    try:
        parser = EssentialHTMLParser()
        parser.feed(html_dom)
        html = parser.essential_html
        if is_missed(html):
            return html_dom
        return html
    except Exception as ex:
        return html_dom


def simplify_html(dom_html):
    soup = bs(dom_html)
    cmp_main = soup.find(id='cmp-main')
    def simplify_tag(tag):
        # Create a new tag with the same name
        simplified_tag = soup.new_tag(tag.name)

        # Copy the 'id' and 'class' attributes if they exist
        if tag.has_attr('id'):
            simplified_tag['id'] = tag['id']
            if tag['id'] == "cmp-main":
                i = 0
        if tag.has_attr('class'):
            simplified_tag['class'] = tag['class']

        # Preserve text content
        if tag.string:
            simplified_tag.string = tag.string
        children = tag.children
        if children:
            for child in tag.children:
                child_text = child.get_text(strip=True)
                child_name = child.name
                if "cookies" in child_text:
                    print(child_text)
                if "p" == child_name:
                    print(child_text)
                if child_name:  # Check if the child is a tag
                    simplified_tag.append(simplify_tag(child))
                else:
                    simplified_tag.append(child)
        else:
            simplified_tag.text = tag.text

        return simplified_tag

    simplified_soup = simplify_tag(soup)
    return simplified_soup.prettify()


def get_html_short(html):
    html_short = simplify_html(html)
    return html_short


def extract_banner_data(banner_item):
    global driver
    banner_data = {}

    try:
        banner, shadow_host = get_banner_obj(banner_item)
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("failed in switching frame for : " + this_url + " in exctact banner data. " + traceback.format_exc(), file=f)
            # MyExceptionLogger(err=ex, file=f)
        driver.switch_to.default_content()
        return

    try:
        vh, vw = get_win_inner_size(driver)
        banner_data["vh"] = vh
        banner_data["vw"] = vw
        banner_data["x"] = int(banner.location["x"])
        banner_data["y"] = int(banner.location["y"])
        banner_data["w"] = int(banner.size["width"])
        banner_data["h"] = int(banner.size["height"])
        banner_data["captured_area"] = calc_area([banner_data["w"], banner_data["h"]]) / calc_area([banner_data["vh"], banner_data["vw"]])
        html = to_html(banner)
        banner_data["html"] = html

        buttons_text = extract_tag_texts(html, "button")
        if buttons_text:
            banner_data["buttons_text"] = ", ".join(buttons_text)
        else:
            buttons_text = extract_leaf_strings(html)
            banner_data["buttons_text"] = "[extract_leaf_strings]: " + ", ".join(buttons_text) if buttons_text else "None"

        links_text = extract_tag_texts(html, "a")
        if links_text:
            banner_data["links_text"] = ", ".join(links_text)
        else:
            links_text = extract_leaf_strings(html)
            banner_data["links_text"] = "[extract_leaf_strings]: " + ", ".join(links_text) if links_text else "None"
        
        # html_short = get_html_short(html)
        html_short = extract_essential_html(html)
        banner_data["html_short"] = html_short
        banner_data["lang"] = detect_lang(banner.text)
        if type(banner_item) is tuple:
            if shadow_host is not None:
                banner_data["shadow_dom"] = True
            else:
                banner_data["iFrame"] = True
                driver.switch_to.default_content()
        else:
            banner_data["iFrame"] = False
            banner_data["shadow_dom"] = False
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("failed in extracting banner for : " +this_url + " " + traceback.format_exc(), file=f)
            # MyExceptionLogger(err=ex, file=f)
        return

    return banner_data


def get_data_dicts(banner_data, visit_id):
    global this_domain, visit_db, banner_db, html_db, this_index
    try:
        # visit_id = this_index
        banner_id = random.getrandbits(53)
        
        b_row_dict = {'banner_id': banner_id, 'visit_id': visit_id, 'domain': this_domain}
        b_row_dict.update(banner_data)
        
        h_row_dict = {'banner_id': banner_id, 'visit_id': visit_id, 'domain': this_domain}
        
        h_row_dict['html'] = banner_data["html"]
        h_row_dict['html_short'] = banner_data["html_short"]
        del b_row_dict['html']
        del b_row_dict['html_short']

        try:
            banner_db.loc[banner_db.shape[0], b_row_dict.keys()] = b_row_dict.values()
            html_db.loc[html_db.shape[0], h_row_dict.keys()] = h_row_dict.values()
        except:
            pass
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("failed to continue extracting banner data for domain: " + this_url + " " + traceback.format_exc(), file=f)
            MyExceptionLogger(err=ex, file=f)
    finally:
        return b_row_dict, h_row_dict


def take_banners_sc(banners, data):
    global driver, SCREENSHOT
    if SCREENSHOT:
        if banners:
            for j, banner_item in enumerate(banners):
                try:
                    take_banner_sc(banner_item, data, j)
                except Exception as ex:
                    with open(log_file, 'a+') as f:
                        print("failed to continue in taking banner sc for domain: " + this_url + " " + traceback.format_exc(), file=f)
                        MyExceptionLogger(err=ex, file=f)
        elif NOBANNER_SC:
            take_current_page_sc(data, nobanner_sc_dir)


def extract_banners_data(banners):
    banners_data = []
    for banner_item in banners:
        banner_data = extract_banner_data(banner_item)
        if banner_data:
            banners_data.append(banner_data)
    return banners_data


def set_data_in_db(data):
    global driver, this_url, this_domain, this_status, this_lang, visit_db, this_run_url
    if data.openwpm:
        visit_id = data.visit_id
        site_rank = data.index
        this_status = data.status
        this_url = data.url
        this_domain = get_current_domain(driver, this_url)
        this_lang = data.lang
    else:
        visit_id = visit_db.shape[0] + 1
        site_rank = visit_id
    try:
        run_url = driver.current_url
    except Exception as ex:
        run_url = None

    v_dict = {
        'visit_id': visit_id, 
        'site_rank': site_rank, 
        'domain': this_domain, 
        'url': this_url, 
        'run_url': run_url, 
        'status': this_status, 
        'lang': this_lang, 
        'banners': len(data.banners_data), 
        'interact_mode': data.choice, 
        'interact_time': data.interact_time, 
        'goal': data.goal,  
        'ttw': data.start_time.timestamp() * 1000, 
        '__tcfapi': False, 
        '__tcfapiLocator': False, 
        'pv': False, 
        'nc_cmp_name': data.nc_cmp_name
    }

    v_dict.update(data.btn_status)
    try:
        body_html = to_html(driver.find_element(By.TAG_NAME, "body"))
    except:
        body_html = None
    if DNSMPI_DETECTION:
        v_dict['dnsmpi'] = dnsmpi_detection(body_html)
    else:
        v_dict['dnsmpi'] = None
    if SAVE_BODY:
        v_dict['body_html'] = body_html
    else:
        v_dict['body_html'] = None
    v_dict['with_sub'] = False

    b_dict = {}
    h_dict = {}
    # not equal with: visit_db = visit_db.append(row_dict, ignore_index=True), using second one, new dataframe with new address will be created.

    try:
        for banner_data in data.banners_data:
            b_dict, h_dict = get_data_dicts(banner_data, visit_id)
            if b_dict['is_sub']:
                v_dict['with_sub'] = True
            if data.openwpm:
                data.save_record_in_sql("banners", b_dict)
                if SAVE_HTML:
                    data.save_record_in_sql("htmls", h_dict)
    except:
        pass
    
    if data.openwpm:
        data.save_record_in_sql("visits", v_dict)
    else:
        visit_db.loc[visit_db.shape[0], v_dict.keys()] = v_dict.values()

    return v_dict, b_dict, h_dict


# make the program halt until the time to wait is passed since the start time, then return the current time
def halt_for_sleep(start_time, time_to_wait):
    if start_time:
        while True:
            cur_time = datetime.now()
            completion_time = cur_time - start_time
            completion_time_seconds = completion_time.total_seconds()
            if completion_time_seconds < time_to_wait:
                time.sleep(1)
            else:
                return cur_time


def run_banner_detection(data):
    global num_banners, driver
    data.domain = get_current_domain(driver, data.url)
    take_current_page_sc(data)
    banners = detect_banners(data)
    take_banners_sc(banners, data)

    return banners


def save_database():
    global visit_db, banner_db, html_db
    if visit_db is not None: # data_dir=./datadir/test-artifact/1-Starting_Point_0/
        visit_db.to_csv(data_dir + '/visits.csv', index=False, header=False)
        banner_db.to_csv(data_dir + '/banners.csv', index=False, header=False)
        html_db.to_csv(data_dir + '/htmls.csv', index=False, header=False)

        init_str = "(saving) visits_db id is: {},\n db is: {}".format(id(visit_db), visit_db)
        
        with open(data_dir + "/sites.txt", 'a+') as f:
            print(init_str, file=f)


def run_all_pc():  # this function is used for run the banner detection module only (Not through OpenWPM)
    global driver, counter, driver_ref

    init_pc(headless=False, num_browsers=1, num_repetitions=1)

    step = 0
    driver = run_webdriver()  # Start initial driver
    driver_ref["driver"] = driver

    for domain in domains:
        tab_restart_browser(driver)
        print("step: ", step, " domain: ", domain)

        driver_ref["done"] = False
        driver_ref["restart"] = False

        driver_ref["watchdog_thread"] = threading.Thread(target=watchdog, args=(domain,))
        driver_ref["watchdog_thread"].start()

        try:
            url = open_domain_page(domain)
            run_all_for_domains(domain, url)
            driver_ref["done"] = True  # Mark as completed
        except TimeoutException:
            print(f"Timeout Error: {domain} took too long to load! Skipping...")
        except WebDriverException as e:
            print(f"WebDriver Error: {e}. Restarting Firefox...")
            print(f"{traceback.format_exc()}")
            driver_ref["restart"] = True
        except Exception as e:
            print(f"Error processing {domain}: {e}")
            print(f"{traceback.format_exc()}")
        finally:
            driver_ref["done"] = True  # Mark as completed

        if driver_ref["watchdog_thread"] and driver_ref["watchdog_thread"].is_alive():
            driver_ref["done"] = True
            time.sleep(3)
            driver_ref["watchdog_thread"].join() # it was always there
            driver_ref["done"] = False

        if driver_ref["restart"]:
            print(f"Restarting Selenium driver for next domain...")
            try:
                driver_ref["driver"].quit()
            except:
                print("Failed to quit driver in run_all_pc")
                pass  # Ignore errors if already closed
            driver = run_webdriver()  # Start new driver session
            driver_ref["driver"] = driver

        time.sleep(1)

        step += 1
    else:
        time.sleep(1)
        close_driver()


def run_all_for_domains(DMN, URL):
    global counter, SLEEP_TIME, this_domain
    this_domain = DMN
    try:
        class Data:
            url = URL
            domain = DMN
            choice = CHOICE
            banners = []
            banners_data = []
            index = None
            sleep = SLEEP_TIME
            ttw = 0   # time to wait (to show the banner)
            status = None
            openwpm = False
            btn_status = {"btn_status": 0, "btn_set_status": 0}
            nc_cmp_name = None
            interact_time = None
            goal = "something"
            start_time = datetime.now()
            finish_time = 0
            category = "Unknown Yet"

        Data.index = visit_db.shape[0]
        Data.visit_id = visit_db.shape[0]
        Data.start_time = datetime.now()

        if BANNERCLICK:
            banners = run_banner_detection(Data)

            Data.banners = banners
            Data.banners_data = extract_banners_data(banners)

            detect_banner_category_start_time = time.perf_counter()

            if len(banners) > 0:
                # clear all data, start new tab and navigate to the domain again and dismiss alert if there
                try:
                    # self.clear_data_and_get_site(webdriver)
                    for i, _ in enumerate(Data.banners):
                        banner_closed, is_navigated, is_scrolled, is_text_selected, clicked, url_changed, banner_category, branch, closing_score = detect_banner_category(Data, i)

                        new_row = pd.DataFrame([
                            [Data.url.split("//")[-1], Data.url, banner_category, f"closing_score:{closing_score}",f"banner_closed:{banner_closed}", f"is_navigated:{is_navigated}", 
                            f"is_scrolled:{is_scrolled}", f"is_text_selected:{is_text_selected}", f"clicked:{clicked}", 
                            f"url_changed:{url_changed}", f"branch:{branch}"]])
                        new_row.to_csv(urls_file, mode="a", header=False, index=False)

                        Data.banners_data[i]['category'] = banner_category
                except Exception as ex:
                    with open(log_file, 'a+') as f:
                        print("skipping category detection: failed in clear_data_and_get_site for url: " + Data.url + " " + ex)
                        print("skipping category detection: failed in clear_data_and_get_site for url: " + Data.url + " " + ex.__str__(), file=f)
            else:
                Data.category = "No banner" # if there is no banner, it will not be in the table, simple search by table "visits" column "banners"=0
                new_row = pd.DataFrame([
                    [Data.url.split("//")[-1], Data.url, "No banner", f"closing_score:Unknown", "banner_closed:Unknown", "is_navigated:Unknown", "is_scrolled:Unknown", 
                    "is_text_selected:Unknown", "clicked:Unknown", "url_changed:Unknown", "branch:Unknown"]])
                new_row.to_csv(urls_file, mode="a", header=False, index=False)

            detect_banner_category_end_time = time.perf_counter()

            elapsed_seconds = int(detect_banner_category_end_time - detect_banner_category_start_time)
            print(f"elapsed_seconds: {elapsed_seconds} for url: {Data.url}")

        set_data_in_db(Data)
        halt_for_sleep(Data.start_time, 10)

    except MemoryError as ex:
        visit_db.loc[visit_db.index[-1], 'status'] = -1
        with open(log_file, 'a+') as f:
            print('Memory Error happened for: ' + DMN + "  " + traceback.format_exc(), file=f)
            MyExceptionLogger(err=ex, file=f)
    except InvalidSessionIdException as ex:
        visit_db.loc[visit_db.index[-1], 'status'] = -1
        with open(log_file, 'a+') as f:
            print('InvalidSessionIdException happened for: ' + DMN + "  " + traceback.format_exc(), file=f)
            MyExceptionLogger(err=ex, file=f)
        raise
    except Exception as ex:
        visit_db.loc[visit_db.index[-1], 'status'] = -1
        with open(log_file, 'a+') as f:
            print('Exception happened for: ' + DMN + "  " + traceback.format_exc(), file=f)
            MyExceptionLogger(err=ex, file=f)



def watchdog(domain):
    """ Kills the driver if it takes too long on a domain. """
    global driver_ref

    start_time = time.time()
    WATCHDOG_TIMEOUT = 60 * 8 # 5 minutes

    while (time.time() - start_time) < WATCHDOG_TIMEOUT:
        time.sleep(0.5) # Check every second
        if driver_ref["done"]:  # If main thread finished, exit watchdog
            print('driver_ref["done"] is True, ending watch dog')
            return

    # If execution time exceeds timeout, kill driver and restart
    print(f"{domain} is stuck! Forcing driver restart...")

    try:
        if not driver_ref["in_processing"]:
            driver_ref["restart"] = True  # Signal main thread to restart driver
            print("killing driver in watchdog")
            driver_ref["driver"].quit()  # Kill Selenium driver
    except:
        print("Error in quiting driver in watchdog")
        pass  # Ignore errors if already closed


def close_driver():
    global driver
    save_database()
    driver.quit()
    reset()


def extract_tags(html: str, tag_name: str):
    soup = bs(html, "html.parser")
    tags = soup.find_all(tag_name)
    return [str(tag) for tag in tags]


def extract_tag_texts(html: str, tag_name: str):
    soup = bs(html, "html.parser")
    tags = soup.find_all(tag_name)
    return [tag.get_text(strip=True) for tag in tags]


def extract_leaf_strings(html):
    soup = bs(html, "html.parser")
    result = []

    for tag in soup.find_all(True):
        # leaf = no direct child tags
        if not tag.find_all(True, recursive=False):
            text = tag.get_text(strip=True)
            if text and len(text.split()) <= 4:
                result.append(text)

    return result


def extract_full_leaf_strings(html, words_threshold=1):
    soup = bs(html, "html.parser")
    result = []

    for tag in soup.find_all(True):
        # leaf = no direct child tags
        if not tag.find_all(True, recursive=False):
            text = tag.get_text(strip=True)
            if text and len(text.split()) >= words_threshold:
                result.append(text)

    return result


def navigate_to_data_url(data, driver):
    data_url = data.url
    error_flag = False

    try:
        driver.get(data_url)
    except Exception as E:
        try:
            data_url = data_url.replace('://', '://www.')
            driver.get(data_url)
        except TimeoutException:  # timeout
            error_flag = True
        except Exception as E:  # unreachable
            error_flag = True

    return error_flag


def detect_banner_category(data, i):
    global driver
    banner_closed, is_navigated, is_scrolled, is_text_selected, clicked, url_changed, banner_category, branch, closing_score = False, False, False, False, False, False, None, "", -1
    try:
        print("detecting banner category for: ", data.domain)
        driver.maximize_window()
        try:
            WebDriverWait(driver, 2).until(ec.visibility_of_element_located((By.TAG_NAME, "body")))
            WebDriverWait(driver, 2).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        except Exception as ex:
            try:
                WebDriverWait(driver, 4).until(ec.visibility_of_element_located((By.TAG_NAME, "body")))
                WebDriverWait(driver, 4).until(lambda d: d.execute_script('return document.readyState') == 'complete')
            except Exception as ex:
                with open(log_file, 'a+') as f:
                    print("page might not have loaded completely for : " + this_url + " in interact with banner. " + traceback.format_exc(), file=f)
        time.sleep(5)

        try:
            if user_detected_as_bot(driver):
                return False, False, False, False, False, False, "BOT DETECTED", "BOT DETECTED", -1
            # all the code and the related function calls marked under <> is subject to remove per next weekly
            # meeting discussion 

            # Step: Send Escape key to attempt to close any simple non-blocking banners
            print("Sending Escape key to attempt to close any simple non-blocking banners")
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            ActionChains(driver).send_keys(Keys.ESCAPE).pause(random.uniform(3, 6)).perform()
            ActionChains(driver).send_keys(Keys.ESCAPE).pause(random.uniform(3, 6)).perform()
            ActionChains(driver).send_keys(Keys.ESCAPE).pause(random.uniform(0.5, 1.5)).perform()
            ActionChains(driver).send_keys(Keys.ESCAPE).pause(random.uniform(0.5, 1.5)).perform()
            
            if user_detected_as_bot(driver):
                return False, False, False, False, False, False, "BOT DETECTED", "BOT DETECTED", -1

            # If banner was closed by Escape, it is likely a simple non-blocking banner. 
            if not is_new_ui_area_same_as_old_banner_area(data, i) and not does_banner_exist(data, i):
                banner_closed = True
                banner_category = "Simple non blocking banner"
                closing_score = score_close_button_from_html(data.banners_data[i]["html"])
                data.category = banner_category
                branch = "if not is_new_ui_area_same_as_old_banner_area(data, i) and not does_banner_exist(data, i): driver.find_element('tag name', 'html').send_keys(Keys.ESCAPE)"

                print(branch)

                return banner_closed, is_navigated, is_scrolled, is_text_selected, clicked, url_changed, banner_category, branch, closing_score

            
            # # Step: Check if banner is a static one, static banners remain present in dom but hides when page is scrolled down
            is_scrolled, reason_is_scrolled = scroll_atleast_half_page() # two cases of reason fully scrolled and partially scrolled
            if is_scrolled and reason_is_scrolled != "fully scrolled":
                print(f"Page did not scrolled fully down via mouse scroll so scrolling via keyboard now")
                scroll_to_bottom()

            if user_detected_as_bot(driver):
                return False, False, False, False, False, False, "BOT DETECTED", "BOT DETECTED", -1

            time.sleep(3)
            if not is_new_ui_area_same_as_old_banner_area(data, i) and does_banner_exist(data, i):
                banner_closed = True
                banner_category = "static banner"
                closing_score = score_close_button_from_html(data.banners_data[i]["html"])
                data.category = banner_category
                branch = "if not is_new_ui_area_same_as_old_banner_area(data, i) and does_banner_exist(data, i):"

                print(branch)

                return banner_closed, is_navigated, is_scrolled, is_text_selected, clicked, url_changed, banner_category, branch, closing_score
            scroll_to_top()

            # Step: Select a link via TAB, if a non cookie banner link is selected banner is floating else it is blocking
            tabbed, reason_tabbed = tab_to_select_link_in_banner(data, i)
            if tabbed:
                if user_detected_as_bot(driver):
                    return False, False, False, False, False, False, "BOT DETECTED", "BOT DETECTED", -1
                
                # Step: Scroll at least half page down or full and check if banner is still there
                # two cases of reason fully scrolled and partially scrolled
                is_scrolled, reason_is_scrolled = scroll_atleast_half_page()
                if is_scrolled and reason_is_scrolled != "fully scrolled":
                    print(f"Page did not scrolled fully down via mouse scroll so scrolling via keyboard now")
                    scroll_to_bottom()

                if is_new_ui_area_same_as_old_banner_area(data, i):
                    banner_closed = False
                    banner_category = "floating banner"
                    closing_score = score_close_button_from_html(data.banners_data[i]["html"])
                    data.category = banner_category
                    branch = "if tabbed: if is_new_ui_area_same_as_old_banner_area(data, i):"

                    print(branch)

                    return banner_closed, is_navigated, is_scrolled, is_text_selected, clicked, url_changed, banner_category, branch, closing_score
                else:
                    banner_closed = True
                    banner_category = "static banner"
                    closing_score = score_close_button_from_html(data.banners_data[i]["html"])
                    data.category = banner_category
                    branch = "if tabbed: else:"

                    print(branch)

                    return banner_closed, is_navigated, is_scrolled, is_text_selected, clicked, url_changed, banner_category, branch, closing_score
            else:
                # blocking banner
                banner_closed = False
                banner_category = "blocking banner"
                closing_score = score_close_button_from_html(data.banners_data[i]["html"])
                data.category = banner_category
                branch = "else: (if not tabbed)"

                print(branch)

                return banner_closed, is_navigated, is_scrolled, is_text_selected, clicked, url_changed, banner_category, branch, closing_score
        except Exception as ex:
            with open(log_file, 'a+') as f:
                print("Encountered an error while parsing banner data for url: " + data.url + " " + traceback.format_exc())
                print("Encountered an error while parsing banner data for url: " + data.url + " " + traceback.format_exc(), file=f)
                print(f"banner_closed:{banner_closed}, is_navigated:{is_navigated}, is_scrolled:{is_scrolled}, is_text_selected:{is_text_selected}, clicked:{clicked}, url_changed:{url_changed}, banner_category:{banner_category}")
                print(f"banner_closed:{banner_closed}, is_navigated:{is_navigated}, is_scrolled:{is_scrolled}, is_text_selected:{is_text_selected}, clicked:{clicked}, url_changed:{url_changed}, banner_category:{banner_category}", file=f)

        return banner_closed, is_navigated, is_scrolled, is_text_selected, clicked, url_changed, banner_category, branch, closing_score
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("Encountered an error in detect_banner_category for url: " + data.url + " " + traceback.format_exc())
            print("Encountered an error in detect_banner_category for url: " + data.url + " " + traceback.format_exc(), file=f)


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


def tab_to_select_link_in_banner(data, i):
    global driver
    redirected_url = get_redirected_url(data)

    try:
        links = get_all_links_on_page()
        buttons = get_all_buttons_on_page()

        banners_link = get_banners_links(data, i)
        banner_html = get_banner_html_str(data, i)

        href_count = {}
        button_count = {}

        actions = ActionChains(driver)

        tab_count = len(links) + len(buttons) + int(min(len(links), len(buttons)) * 1.5)

        print("1st loop for tabbing")
        for j in range(0, tab_count):
            actions.send_keys(Keys.TAB).perform()
            time.sleep(random.uniform(1, 2.5))
            # actions.reset_actions()

            active_element = driver.switch_to.active_element
            active_element_tag = active_element.tag_name

            if active_element_tag == "button":
                active_element_text = active_element.text
                print(f"Tabbed to button with text: '{active_element_text}'")

                if active_element_text in button_count:
                    button_count[active_element_text] += 1
                else:
                    button_count[active_element_text] = 1

                if (active_element_text != "" and button_count[active_element_text] >= 4) \
                        or (active_element_text == "" and button_count[active_element_text] >= 15):
                    print(f"Breaking: active_element_text: {active_element_text}")
                    break

            if active_element_tag == "a":
                active_element_href = active_element.get_attribute("href")
                print(f"Tabbed to link with href: '{active_element_href}'")

                if active_element_href in href_count:
                    href_count[active_element_href] += 1
                else:
                    href_count[active_element_href] = 1

                if href_count[active_element_href] >= 4:
                    print(f"Breaking: active_element_href: {active_element_href}")
                    break

                if is_tabbed_href_valid(data, redirected_url, active_element_href) \
                    and active_element_href not in banner_html \
                    and active_element_href not in banners_link:
                    
                    print(f"returning True: active_element_href: {active_element_href}")
                    return True, "tabbed to a valid link in the banner"

        href_count = {}
        button_count = {}

        time.sleep(2)
        driver = quit_current_driver_and_start_new_webdriver(data)
        if not driver:
            print("failed to quit and restart driver or to reopen domain before 2nd loop")
            return False, "Driver failed to restart"

        actions = ActionChains(driver)
        actions.send_keys(Keys.TAB).perform()
        print("2nd loop for tabbing after navigating back to original url")
        for j in range(0, tab_count):
            actions.key_down(Keys.SHIFT).send_keys(Keys.TAB).key_up(Keys.SHIFT).perform()
            time.sleep(random.uniform(1, 2.5))

            active_element = driver.switch_to.active_element
            active_element_tag = active_element.tag_name

            if active_element_tag == "button":
                active_element_text = active_element.text
                print(f"Tabbed to button with text: '{active_element_text}'")

                if active_element_text in button_count:
                    button_count[active_element_text] += 1
                else:
                    button_count[active_element_text] = 1

                if (active_element_text != "" and button_count[active_element_text] >= 4):
                    print(f"Breaking: active_element_text: {active_element_text}")
                    break
                
                if (active_element_text == "" and button_count[active_element_text] >= 15):
                    print(f"Breaking: active_element_text: {active_element_text}")
                    # error_flag = reopen_domain_page(data.url, driver)

                    # if error_flag:
                    #     print("error while reopening domain page after starting new driver")
                    driver = quit_current_driver_and_start_new_webdriver(data)
                    if not driver:
                        print("failed to quit and restart driver or to reopen domain before breaking due to 15 times same tag text")

                    break

            if active_element_tag == "a":
                active_element_href = active_element.get_attribute("href")
                print(f"Tabbed to link with href: '{active_element_href}'")

                if active_element_href in href_count:
                    href_count[active_element_href] += 1
                else:
                    href_count[active_element_href] = 1

                if href_count[active_element_href] >= 4:
                    print(f"Breaking: active_element_href: {active_element_href}")
                    break

                if is_tabbed_href_valid(data, redirected_url, active_element_href) \
                    and active_element_href not in banner_html \
                    and active_element_href not in banners_link:
                    
                    print(f"returning True: active_element_href: {active_element_href}")
                    return True, "tabbed to a valid link in the banner"
                    
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("Encountered an error in tab_to_select_link_in_banner for url: " + this_url + " " + traceback.format_exc())
            print("Encountered an error in tab_to_select_link_in_banner for url: " + this_url + " " + traceback.format_exc(), file=f)
        return False, "exception"

    print(f"returning False: tab_count: {tab_count}")
    for key, value in button_count.items():
        print(f"{key}: {value}")
        
    for key, value in href_count.items():
        print(f"{key}: {value}")
        
    return False, "exhausted valid links to tab to in banner"


def is_element_overlapping_box(driver, element, x, y, w, h):
    # box = (x, y, w, h)
    script = """
        const el = arguments[0];
        const box = arguments[1];

        const rect = el.getBoundingClientRect();

        const elLeft = rect.left;
        const elRight = rect.right;
        const elTop = rect.top;
        const elBottom = rect.bottom;

        const boxLeft = box.x;
        const boxRight = box.x + box.w;
        const boxTop = box.y;
        const boxBottom = box.y + box.h;

        // check overlap
        const overlap = !(elRight < boxLeft ||
                        elLeft > boxRight ||
                        elBottom < boxTop ||
                        elTop > boxBottom);

        return overlap;
    """
    return driver.execute_script(script, element, {"x": x, "y": y, "w": w,"h": h})


def get_redirected_url(data):
    redirected_url = ""
    try:
        response = requests.get(data.url, timeout=60)
        redirected_url = response.url
    except Exception as ex:
        pass

    return redirected_url


def did_url_change(driver, current_url, redirected_url):        
    def url_check(d):
        current = d.current_url

        if "zoom" in current_url:
            print(f"driver.current (right now): {current}, current_url: {current_url}, redirected_url: {redirected_url}")

        return (
            current != current_url and
            current != redirected_url and
            not current.startswith(redirected_url + "#") and
            not current.startswith(redirected_url + "?")
        )

    url_changed = False
    try:
        WebDriverWait(driver, 3).until(url_check)
        url_changed = True
    except TimeoutException:
        url_changed = False

    return url_changed


def refind_link_by_href_safe(driver, href):
    if not href:
        return None

    try:
        xpath = f"//a[@href={repr(href)}]"
    except Exception:
        print("failed to create xpath in refind_link_by_href_safe")
        return None

    try:
        wait = WebDriverWait(driver, 3)
        element = wait.until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        return element
    except Exception:
        print("failed to find element by href in refind_link_by_href_safe")
        return None


def navigate_to_other_page_and_then_back(data, i, href, redirected_url):
    scroll_to_top()
    global driver

    current_url = driver.current_url
    
    original_window = driver.current_window_handle
    before_handles = driver.window_handles

    print(f"navigate_to_other_page_and_then_back index: {i}")
    bx = data.banners_data[i]['x']
    by = data.banners_data[i]['y']
    bw = data.banners_data[i]['w']
    bh = data.banners_data[i]['h']

    actions = ActionChains(driver)
    for z in range(0, 3):
        link_to_click = refind_link_by_href_safe(driver, href)

        if not link_to_click:
            continue

        try:
            try:
                # ensure element is in viewport
                if z == 0:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", link_to_click)
                elif z == 1:
                    driver.execute_script("arguments[0].scrollIntoView({block:'start', inline:'nearest'});", link_to_click)
                else:
                    driver.execute_script("arguments[0].scrollIntoView({block:'end', inline:'nearest'});", link_to_click)
            except:
                try:
                    # ensure element is in viewport
                    if z == 0:
                        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", link_to_click)
                    elif z == 1:
                        driver.execute_script("arguments[0].scrollIntoView({block:'start', inline:'nearest'});", link_to_click)
                    else:
                        driver.execute_script("arguments[0].scrollIntoView({block:'end', inline:'nearest'});", link_to_click)
                except Exception as ex:
                    with open(log_file, 'a+') as f:
                        print("failed in scrolling into view and waiting for clickable for url: " + data.url)
                        print("failed in scrolling into view and waiting for clickable for url: " + data.url + "\n" + traceback.format_exc(), file=f)
                        continue

                link_to_click = refind_link_by_href_safe(driver, href)

                if not link_to_click:
                    continue

            if is_element_overlapping_box(driver, link_to_click, bx, by, bw, bh):
                print("link_to_click is overlapping with banner area for url: " + data.url)
                continue

            # safe click (no offset)
            try:
                actions.move_to_element(link_to_click).pause(random.uniform(0.3, 0.5)).click().perform()
            except:
                print("click failed for url: " + data.url)
                actions.reset_actions()
                continue
            
            time.sleep(random.uniform(1.5, 2))  # Wait for new tab since new tab could be opened despite the filteration
            new_tab_count = close_other_tabs_if_opened(original_window, before_handles)

            if new_tab_count > 0:
                time.sleep(1)  # Wait for new tab since new tab could be opened despite the filteration
                print(f"tabs were opened during navigate_to_other_page {data.url}")
                reopen_domain_page(data.url, driver)
                return True, "new tabs opened"

            url_changed = did_url_change(driver, current_url, redirected_url)

            actions.reset_actions()
            # ✅ Check if URL changed
            if url_changed:
                print(f"link_to_click.get_attribute('href'): {link_to_click.get_attribute('href')}")
                print(f"if url_changed: same tab for url driver.current_url: {driver.current_url}")
                print(f"if url_changed: same tab for url current_url: {current_url}")
                print(f"if url_changed: same tab for url redirected_url: {redirected_url}")
                reopen_domain_page(data.url, driver)
                return True, "success"
        except Exception as ex:
            with open(log_file, 'a+') as f:
                print("Encountered an error while clicking a link same tab for url: " + data.url)
                print("Encountered an error while clicking a link same tab for url: " + data.url + " " + str(ex), file=f)
                print("Encountered an error while clicking a link same tab for url: " + data.url + " " + traceback.format_exc(), file=f)

            time.sleep(0.5)
            # Clean up extra tabs just in case
            new_tab_count = close_other_tabs_if_opened(original_window, before_handles)

            if new_tab_count > 0:
                time.sleep(1)  # Wait for new tab since new tab could be opened despite the filteration
                reopen_domain_page(data.url, driver)
                return True, "new tabs opened"

    return False, "exhausted valid links"


def scroll_to_top():
    def is_at_top(driver, tolerance=5):
        try:
            # Check vertical scroll position
            scroll_y = driver.execute_script("return window.pageYOffset;")
            page_height = driver.execute_script("return document.body.scrollHeight;")
            return scroll_y >= page_height - tolerance
        except Exception as ex:
            print(f"Exception in is_at_top: {traceback.format_exc()}")
            pass
    
    try:
        actions = ActionChains(driver)
        actions.send_keys(Keys.HOME).perform()
        time.sleep(2)
    except Exception as ex:
        print(f"Exception in actions.send_keys(Keys.HOME).perform(): {traceback.format_exc()}")
        pass

    if not is_at_top(driver):
        try:
            print("Not at top after HOME, trying PAGE_UP...")

            # --- Step 2: Page Up (simulate hold by repeating) ---
            for _ in range(10):  # simulate holding key
                actions.send_keys(Keys.PAGE_UP).perform()
                time.sleep(random.uniform(0.3, 0.5))
                if is_at_top(driver):
                    break
        except Exception as ex:
            print(f"Exception in actions.send_keys(Keys.PAGE_UP).perform(): {traceback.format_exc()}")
            pass

    # --- Step 3: Force via JS if still not at top ---
    if not is_at_top(driver):
        try:
            print("Still not at top, forcing via JavaScript...")
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(random.uniform(0.3, 0.5))
        except Exception as ex:
            print(f"Exception in driver.execute_script('window.scrollTo(0, 0);'): {traceback.format_exc()}")
            pass
        
    # Final check
    if is_at_top(driver):
        print("Reached top of page")
    else:
        print("Failed to reach top")


def scroll_to_bottom():
    def is_at_bottom(driver, tolerance=5):
        try:
            # Check vertical scroll position
            scroll_y = driver.execute_script("return window.pageYOffset;")
            # Get the total height of the page
            page_height = driver.execute_script("return document.body.scrollHeight;")
            # Check if we are at the bottom
            return scroll_y >= page_height - tolerance
        except Exception as ex:
            print(f"Exception in is_at_bottom: {traceback.format_exc()}")
            pass

    try:
        actions = ActionChains(driver)
        actions.send_keys(Keys.END).perform()
        time.sleep(2)
    except Exception as ex:
        print(f"Exception in actions.send_keys(Keys.END).perform(): {traceback.format_exc()}")
        pass

    if not is_at_bottom(driver):
        try:
            print("Not at bottom after END, trying PAGE_DOWN...")

            # --- Step 2: Page Down (simulate hold by repeating) ---
            for _ in range(10):  # simulate holding key
                actions.send_keys(Keys.PAGE_DOWN).perform()
                time.sleep(random.uniform(0.3, 0.5))
                if is_at_bottom(driver):
                    break
        except Exception as ex:
            print(f"Exception in actions.send_keys(Keys.PAGE_DOWN).perform(): {traceback.format_exc()}")
            pass
    
    # --- Step 3: Force via JS if still not at top ---
    if not is_at_bottom(driver):
        try:
            print("Still not at bottom, forcing via JavaScript...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(0.3, 0.5))
        except Exception as ex:
            print(f"Exception in driver.execute_script('window.scrollTo(0, document.body.scrollHeight);'): {traceback.format_exc()}")
            pass
    
    # Final check
    if is_at_bottom(driver):
        print("Reached bottom of page")
    else:
        print("Failed to reach bottom")


def close_other_tabs_if_opened(original_window, before_handles):
    global driver
    count = 0
    try:
        try:
            WebDriverWait(driver, 2).until(
                lambda d: len(d.window_handles) > 1
            )
        except TimeoutException:
            print("lambda d: len(d.window_handles) > 1")
            pass

        # to debug
        if original_window not in driver.window_handles:
            print("Original window is gone. Cannot safely proceed.")
            return count

        if len(before_handles) < len(driver.window_handles):
            time.sleep(1)
            all_windows = driver.window_handles.copy()
            for window in all_windows:
                if window != original_window:
                    try:
                        print(f"original_window: {original_window}, closing window with handle: {window}")
                        driver.switch_to.window(window)
                        driver.close()
                        count += 1
                    except Exception:
                        pass

            print(f"driver.switch_to.window(original_window): {original_window}")
            driver.switch_to.window(original_window)
        else:
            print("No new tabs opened to close.")
            return count

        return count
    except Exception as ex:
        print(f"close_other_tabs exception: {traceback.format_exc()}")
        return count


def get_banners_links(data, i):
    banners_link = []

    try:
        banners_link = list({
            link
            for item in data.banners_data
            for link in extract_links(str(item.get("html", "")))
        })
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("filter_valid_links_for_strict_navigation Encountered an error in banners_link = list({ for url: " + data.url + " " + traceback.format_exc())
            print("filter_valid_links_for_strict_navigation Encountered an error while extracting banner links for url: " + data.url + " " + traceback.format_exc(), file=f)

    return banners_link


def get_banner_html_str(data, i):
    banner_html = ""

    try:
        banner_html = str(data.banners_data[i].get("html")) or ""
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("filter_valid_links_for_strict_navigation Encountered an errorbanner_html = str(data.banners_data[i].get('html')) or "" for url: " + data.url + " " + traceback.format_exc())
            print("filter_valid_links_for_strict_navigation Encountered an errorbanner_html = str(data.banners_data[i].get('html')) or "" for url: " + data.url + " " + traceback.format_exc(), file=f)
        banner_html = ""
    
    return banner_html


def is_tabbed_href_valid(data, redirected_url, href):
    try:
        if not href:
            print('if not href:')
            return False

        parsed = urlparse(href)

        host = parsed.hostname
        # remove port if present
        if not host:
            print("No hostname found")
            return False
        parts = host.split(".")

        try:
            current_domain = urlparse(data.url).hostname.split(".")[-2]
            redirected_url_domain = urlparse(redirected_url).hostname.split(".")[-2]

            link_domain = parts[-2]

            if link_domain != current_domain and link_domain != redirected_url_domain:
                print('if link_domain != current_domain and link_domain != redirected_url_domain:')
                return False
        except Exception as ex:
            pass

        if not parsed.scheme.startswith("http") and not parsed.scheme.startswith("mailto"):
            print('is_tabbed_href_valid: if not parsed.scheme.startswith("http") or not parsed.scheme.startswith("mailto"):')
            return False

        path = parsed.path.strip().lower()

        # skip homepage
        if path in ["", "/"] and not parsed.fragment.strip() and not parsed.query.strip():
            print('is_tabbed_href_valid: if path in ["", "/"]:')
            return False

        clean_path = path.strip("/").lower()

        if clean_path in language_paths:
            print('is_tabbed_href_valid: if clean_path in language_paths:')
            return False

        if any(fp in clean_path for fp in forbidden_paths):
            print("if any(fp in clean_path for fp in forbidden_paths):")
            return False

        fragment = parsed.fragment.strip().lower()
        if any(fp in fragment for fp in forbidden_paths):
            print("if any(fp in fragment for fp in forbidden_paths):")
            return False

        query = parsed.query.strip().lower()
        if any(fp in query for fp in forbidden_paths):
            print("if any(fp in query for fp in forbidden_paths):")
            return False

        # Only proceed if there is a subdomain
        if len(parts) > 2:
            subdomains = parts[:-2]  # everything before domain + TLD

            for sub in subdomains:
                if any(fp in sub.lower() for fp in forbidden_paths):
                    print("Forbidden path found in subdomain")
                    return False

        params = parsed.params.strip().lower()
        if any(fp in params.lower() for fp in forbidden_paths):
            print("if any(fp in params for fp in forbidden_paths):")
            return False
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("filter_valid_links_for_loosy_tabbing Encountered an error in while parsing links for url: " + traceback.format_exc())
            print("filter_valid_links_for_loosy_tabbing Encountered an error in while parsing links for url: " + traceback.format_exc(), file=f)

    return True


def get_all_links_on_page():
    global driver
    try:
        interactable_links = []

        links = driver.find_elements(By.TAG_NAME, "a")
        
        for link in links:
            try:
                if not link.is_displayed() or not link.is_enabled() or link.size['width'] <= 0 or link.size['height'] <= 0:
                    continue
            except Exception as ex:
                continue

            interactable_links.append(link)

        return interactable_links
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("get_all_links_on_page Encountered an error in driver.find_elements(By.TAG_NAME, \"a\") for url: " + traceback.format_exc())
            print("get_all_links_on_page Encountered an error in driver.find_elements(By.TAG_NAME, \"a\") for url: " + traceback.format_exc(), file=f)
        return []


def get_all_buttons_on_page():
    global driver
    try:
        interactable_buttons = []

        buttons = driver.find_elements(By.TAG_NAME, "button")
        
        for button in buttons:
            try:
                if not button.is_displayed() or not button.is_enabled() or button.size['width'] <= 0 or button.size['height'] <= 0:
                    continue
            except Exception as ex:
                continue
            
            interactable_buttons.append(button)

        return interactable_buttons
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("get_all_buttons_on_page Encountered an error in driver.find_elements(By.TAG_NAME, \"button\") for url: " + traceback.format_exc())
            print("get_all_buttons_on_page Encountered an error in driver.find_elements(By.TAG_NAME, \"button\") for url: " + traceback.format_exc(), file=f)
        return []

        
def scroll_atleast_half_page(step = 80):
    global driver
    scrolled = 0
    try:
        actions = ActionChains(driver)

        # Get viewport height using Selenium (not JS)
        page_height = driver.execute_script("return document.body.scrollHeight")
        viewport_height = driver.execute_script("return window.innerHeight")
        max_scroll_possible = page_height - viewport_height

        target_scroll = max_scroll_possible

        # Scroll in small chunks to simulate real mouse wheel behavior pixels per wheel action
        while scrolled < target_scroll:
            actions.scroll_by_amount(0, step).perform()
            scrolled += step
            time.sleep(random.uniform(0.4, 1.4))  # small delay to mimic human scrolling

        return True, "fully scrolled"
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("Encountered an error while scrolling for url: " + this_url + " " + traceback.format_exc())
            print("Encountered an error while scrolling for url: " + this_url + " " + traceback.format_exc(), file=f)

        if scrolled == step:
            return True, "scrolled == step"
        
        if scrolled > step:
            return True, "partially scrolled"
        
        return False, "exception"


CLOSE_WORDS = [
    "close", "x", "exit", "dismiss", "cancel", "quit",
    "schließen", "verlassen", "verwerfen", "abbrechen", "beenden",
    "cerrar", "salir", "descartar", "cancelar", "salir",
    "chiudi", "esci", "ignora", "annulla", "esci",
    "fechar", "sair", "dispensar", "cancelar", "sair",
    "关闭", "退出", "忽略", "取消", "退出",
    "閉じる", "終了", "無視", "キャンセル", "終了",
    "закрыть", "выйти", "отклонить", "отменить", "выйти",
    "kapat", "çık", "reddet", "iptal", "çık",
    "بستن", "خروج", "رد کردن", "لغو", "خروج",
    "stäng", "avsluta", "avvisa", "avbryt", "avsluta",
    "닫기", "종료", "무시", "취소", "종료"
]
ICON_ATTRS = ["src", "href", "xlink:href", "data-src"]


def score_close_button_from_html(html: str) -> int:
    global driver
    score = 0

    try:
        driver.execute_script("""
            var div = document.createElement('div');
            div.id='temp_cookie_banner32141';
            div.style.display='none';
            div.innerHTML = arguments[0];
            document.body.appendChild(div);
        """, html)

        container = driver.find_element(By.ID, "temp_cookie_banner32141")
    except Exception as ex:
        print(f"Failed to create container: {ex}")
        return score

    def is_clickable(element: WebElement) -> bool:
        try:
            tag = element.tag_name.lower()
            role = (element.get_attribute("role") or "").lower()
            onclick = element.get_attribute("onclick")

            return (
                tag in ["button", "a"] or
                role == "button" or
                onclick is not None
            )
        except:
            return False

    def score_element(element: WebElement) -> int:
        s = 0
        s_string = ""

        try:
            tag = element.tag_name.lower()
        except:
            tag = ""

        # Boost real interactive elements
        if is_clickable(element):
            s += 1
            s_string += "s_string:is_clickable "

        # 1. aria-label / title
        try:
            for attr in ["aria-label", "title"]:
                val = element.get_attribute(attr)
                if val and any(w in val.lower() for w in CLOSE_WORDS):
                    s += 1
                    s_string += "s_string:aria-label/title "
        except:
            pass

        # 2. class/id
        try:
            for attr in ["class", "id"]:
                val = element.get_attribute(attr)
                if val:
                    val_lower = val.lower()
                    if any(w in val_lower for w in CLOSE_WORDS):
                        s += 1
                        s_string += "s_string:class/id "
        except:
            pass

        # 3. visible text (better than innerHTML)
        try:
            text = (element.text or "").lower()
            if any(w in text for w in CLOSE_WORDS):
                s += 1
                s_string += "s_string:innerHTML "
        except:
            pass

        # 4. textContent (captures hidden spans etc.)
        try:
            text_content = (element.get_attribute("textContent") or "").lower()
            if any(w in text_content for w in CLOSE_WORDS):
                s += 1
                s_string += "s_string:textContent "
        except:
            pass

        # 5. icon attributes
        try:
            for attr in ICON_ATTRS:
                val = element.get_attribute(attr)
                if val and any(w in val.lower() for w in CLOSE_WORDS):
                    s += 1
                    s_string += "s_string:icon "
        except:
            pass

        # 6. SVG presence heuristic
        try:
            svgs = element.find_elements(By.TAG_NAME, "svg")
            if svgs:
                # Many close buttons are just an icon
                s += 1
                s_string += "s_string:svg "
        except:
            pass
        
        # print(s_string)
        
        return s

    try:
        # 🔥 KEY CHANGE: traverse ALL descendants
        all_elements = container.find_elements(By.XPATH, ".//*")

        for el in all_elements:
            score = max(score, score_element(el))

        driver.execute_script("""
            document.getElementById('temp_cookie_banner32141').remove();
        """)
    except Exception as ex:
        print(f"Scoring failed: {ex}")

    return score


def is_new_ui_area_same_as_old_banner_area(data, i, threshold=0.15):
    try:
        take_current_page_sc(data, suffix="_checking_closed")
        ax = data.banners_data[i]['x']
        ay = data.banners_data[i]['y']
        width = data.banners_data[i]['x'] + data.banners_data[i]['w']
        height = data.banners_data[i]['y'] + data.banners_data[i]['h']
        crop_image = Image.open(sc_dir + get_sc_file_name(data.index, data.url) + "_checking_closed.png")
        with open(log_file, 'a+') as f:
            print(f"is_ui_area_not_same_as_old_banner_area Banner coordinates for url: {data.url} (ax: {ax}, ay: {ay}, width: {width}, height: {height})", file=f)
            print(f"is_ui_area_not_same_as_old_banner_area Banner coordinates for url: {data.url} (ax: {ax}, ay: {ay}, width: {width}, height: {height})")
        crop_image = crop_image.crop((ax, ay, width, height))
        crop_image.save(sc_dir + get_sc_file_name(data.index) + str(i + 1) +  "_banner_checking_closed" +".png")

        try:
            org_banner_image_path = sc_dir + get_sc_file_name(data.index) + "_banner" + str(i + 1) + ".png"
            checking_closed_image_path = sc_dir + get_sc_file_name(data.index) + str(i + 1) +  "_banner_checking_closed" +".png"
            org_banner_image = Image.open(org_banner_image_path)
            checking_closed_image = Image.open(checking_closed_image_path)

            is_similar, max_val = are_images_similar(org_banner_image, checking_closed_image, threshold)

            with open(log_file, 'a+') as f:
                print(f"org_banner_image: {org_banner_image_path}", file=f)
                print(f"checking_closed_image: {checking_closed_image_path}", file=f)
                print(f"Similarity score for url {data.url}: {max_val}", file=f)
                print(f"Similarity score for url {data.url}: {max_val}")
            if is_similar:
                print("banner seems not closed for url: ", data.url)
                with open(log_file, 'a+') as f:
                    print("banner seems not closed for url: " + data.url, file=f)
                return True
            else:
                print("banner seems closed for url: ", data.url)
                with open(log_file, 'a+') as f:
                    print("banner seems closed for url: " + data.url, file=f)
                return False
        except Exception as ex:
            with open(log_file, 'a+') as f:
                print("Encountered an error in comparing banner images for url: " + data.url + " " + traceback.format_exc())
                print("Encountered an error in comparing banner images for url: " + data.url + " " + traceback.format_exc(), file=f)

        return False
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("Encountered an error in is_ui_area_not_same_as_old_banner_area for url: " + data.url + " " + ex)
            print("Encountered an error in is_ui_area_not_same_as_old_banner_area for url: " + data.url + " " + traceback.format_exc(), file=f)
        return False


def does_banner_exist(data, i):
    try:
        # if banner is there but cannot be seen due to scroll (not foolproof)
        not_visible, reason = check_if_element_not_visible(data, i)
        if not_visible:
            print(f"Banner still exists for url: {data.url} since detected by visual/css properties")
            return False

        # extract body text, then search for banners text from earlier detected banners into this bodys html
        try:
            print("looking for banner's text in body element")
            # body 
            body_el = driver.find_element(By.TAG_NAME, "body")
                
            # extract leaf nodes text (innertext) from earlier detected banner text
            extract_leaf_strings_from_earlier_banner = extract_full_leaf_strings(data.banners_data[i]["html"], words_threshold=2)
            for leaf in extract_leaf_strings_from_earlier_banner:
                if any(fp in leaf.lower() for fp in forbidden_paths):
                    continue

                if leaf in body_el.text:
                    print(f"Banner still exists for url: {data.url} since found banner text in body text: {leaf}")
                    return True
        except Exception as ex:
            pass

        # detect banners again
        banners = detect_banners(data, running_for_category_detection=True)
        banners_data = extract_banners_data(banners)

        if i >= len(banners_data):
            print(f"len(banners_data): {len(banners_data)}, i: {i} for url: {data.url}")
            return False

        total_match_count = 0

        extract_leaf_strings_from_banner = extract_full_leaf_strings(banners_data[i]['html'], words_threshold=2)

        print("looking for banner's text in body element")
        for leaf in extract_leaf_strings_from_banner:
            # since cookie banner words are also in body sometimes like privacy policy, learn more and so, so we do below check
            if any(fp in leaf.lower() for fp in forbidden_paths):
                continue
                
            if len(leaf.split(" ")) < 2:
                continue

            if leaf in extract_leaf_strings_from_earlier_banner:
                total_match_count += 1

            if total_match_count >= 2:
                print(f"Banner still exists for url: {data.url} with count: {total_match_count}")
                return True

        return False
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("Encountered an error in does_banner_exist for url: " + data.url + " " + traceback.format_exc())
            print("Encountered an error in does_banner_exist for url: " + data.url + " " + traceback.format_exc(), file=f)
        return False


def get_root_class_or_id(html: str) -> str:
    soup = bs(html, "html.parser")

    root = next((el for el in soup.contents if el.name), None)
    if not root:
        return None

    def longest_class(classes):
        return max(classes, key=len)

    if root.has_attr("class") and root["class"]:
        return f"{root.name}.{longest_class(root['class'])}"

    current = root
    while True:
        children = [c for c in current.children if getattr(c, "name", None)]
        if not children:
            break

        current = children[0]

        if current.has_attr("class") and current["class"]:
            return f"{current.name}.{longest_class(current['class'])}"

    def find_with_id(node):
        if node.has_attr("id"):
            return node
        for child in node.children:
            if getattr(child, "name", None):
                found = find_with_id(child)
                if found:
                    return found
        return None

    found = find_with_id(root)
    if found:
        return f"{found.name}.{found['id']}"

    return None


def is_element_not_visible(data, locator_type, locator_value):
    global driver
    try:
        element = driver.find_element(locator_type, locator_value)

        # Get computed styles
        styles = driver.execute_script("""
            const el = arguments[0];
            const style = window.getComputedStyle(el);

            return {
                display: style.display,
                visibility: style.visibility,
                opacity: style.opacity,
            };
        """, element)

        # Additional DOM state checks
        rect = driver.execute_script("""
            const el = arguments[0];
            const r = el.getBoundingClientRect();
            return {
                width: r.width,
                height: r.height,
            };
        """, element)

        # Basic Selenium visibility check
        is_displayed = element.is_displayed()

        # Visibility classification logic
        not_visible = (
            not is_displayed or
            styles["display"] == "none" or
            styles["visibility"] in ["hidden", "collapse"] or
            float(styles["opacity"]) == 0 or
            rect["width"] == 0 or
            rect["height"] == 0
        )

        print(f"""
            URL: {data.url}
            display: {styles['display']}
            visibility: {styles['visibility']}
            opacity: {styles['opacity']}
            is_displayed: {is_displayed}
            rect: {rect}
            NOT_VISIBLE: {not_visible}
        """)

        return not_visible, "success"
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("Encountered an error in is_element_not_visible for url: " + data.url + " " + traceback.format_exc())
            print("Encountered an error in is_element_not_visible for url: " + data.url + " " + traceback.format_exc(), file=f)

        return False , "exception"
    

def check_if_element_not_visible(data, i):
    try:
        if i >= len(data.banners_data):
            return None, None

        root_locator = get_root_class_or_id(data.banners_data[i]['html'])
        print(f"Root locator for banner {i} for url {data.url}: {root_locator}")
        
        not_visible, reason = is_element_not_visible(data, By.CSS_SELECTOR, root_locator)

        return not_visible, reason
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("Encountered an error in check_if_element_not_visible for url: " + data.url + " " + traceback.format_exc())
            print("Encountered an error in check_if_element_not_visible for url: " + data.url + " " + traceback.format_exc(), file=f)
        return None, None


URL_REGEX = re.compile(
    r'https?://[^\s"\'<>]+|www\.[^\s"\'<>]+',
    re.IGNORECASE
)
ATTRIBUTES_TO_CHECK = [
    "href", "src", "action", "formaction",
    "data-url", "data-href", "data-src",
    "url", "data"
]


def extract_links(html: str, base_url: str = None):
    soup = bs(html, "html.parser")
    links = set()

    # 1. Extract from all tags and all relevant attributes
    for tag in soup.find_all(True):
        for attr in ATTRIBUTES_TO_CHECK:
            if tag.has_attr(attr):
                value = tag.get(attr)

                if isinstance(value, list):
                    value = " ".join(value)

                if value:
                    links.add(value.strip())

        # 2. Inline style or onclick JS (sometimes URLs are hidden here)
        for attr in ["style", "onclick"]:
            if tag.has_attr(attr):
                links.update(URL_REGEX.findall(tag[attr]))

    # 3. Extract from raw text (scripts, comments, etc.)
    text = soup.get_text(" ", strip=False)
    links.update(URL_REGEX.findall(text))

    # 4. Normalize / resolve relative URLs if base_url is provided
    final_links = []
    for link in links:
        if base_url:
            link = urljoin(base_url, link)

        # clean trailing punctuation
        link = link.rstrip(").,;]}'\"")

        final_links.append(link)

    return final_links


def are_images_similar(original_img, current_img, threshold=0.8, tol=1e-3):
    template = cv2.cvtColor(np.array(original_img), cv2.COLOR_RGB2GRAY)
    current = cv2.cvtColor(np.array(current_img), cv2.COLOR_RGB2GRAY)

    res = cv2.matchTemplate(current, template, cv2.TM_CCOEFF_NORMED)
    max_val = res.max()

    is_similar = max_val > threshold or math.isclose(max_val, threshold, abs_tol=tol)

    return is_similar, max_val


if __name__ == '__main__':
    # this function is used for run the banner detection module only (Not through OpenWPM)
    run_all_pc()