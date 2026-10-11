"""banner detection (from BannerClick) and run_site() for one site"""
import time
import traceback
import sys
from datetime import datetime
from types import SimpleNamespace

from PIL import Image

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    JavascriptException,
    NoAlertPresentException,
    NoSuchFrameException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
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
    from . import banner_probe
except ImportError:
    import banner_probe


def MyExceptionLogger(err, file):
    # return
    traceback_details = traceback.format_exc()
    print(traceback_details, file=file)
    exc_type, exc_value, exc_traceback = sys.exc_info()
    print(f"Exception type: {exc_type}, Value: {exc_value}", file=file)
    traceback.print_tb(exc_traceback, file=file)


def log(message):
    print(message)
    try:
        with open(log_file, 'a+') as f:
            print(message, file=f)
    except OSError:
        pass


def set_output_paths(input_name):
    """output folders for this input file"""
    global season_dir, data_dir, sc_dir, nobanner_sc_dir, log_file
    paths = output_paths(input_name)
    season_dir, data_dir, sc_dir = paths["season_dir"], paths["data_dir"], paths["sc_dir"]
    nobanner_sc_dir, log_file = paths["nobanner_sc_dir"], paths["log_file"]
    for d in (season_dir, data_dir, sc_dir):
        os.makedirs(d, exist_ok=True)


def run_webdriver():
    options = Options()
    if FIREFOX_BINARY and os.path.exists(FIREFOX_BINARY):
        options.binary_location = FIREFOX_BINARY  # snap Firefox binary on the original machine

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

    # keep popup blocker on, popunders open extra windows
    options.set_preference("dom.disable_open_during_load", True)

    # "Leave page?" prompts would block link clicks and quitting
    options.set_preference("dom.disable_beforeunload", True)
    options.set_preference("browser.sessionstore.resume_from_crash", False)

    # Deny all unknown permission requests by default
    options.set_preference("permissions.default.image", 1)  # (1=allow, 2=block if needed)

    # eager: driver.get returns at DOMContentLoaded
    options.page_load_strategy = "eager"
    options.set_capability("unhandledPromptBehavior", "dismiss")

    driver = webdriver.Firefox(options=options)

    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    driver.set_script_timeout(30)
    driver.set_window_size(*WINDOW_SIZE)

    return driver


def start_browser(tries=3):
    """start firefox, retry if the window is hidden or has the wrong size"""
    drv = None
    for attempt in range(tries):
        drv = run_webdriver()
        if HEADLESS:
            return drv
        time.sleep(1)
        try:
            visibility, width = drv.execute_script("return [document.visibilityState, window.outerWidth]")
        except WebDriverException:
            visibility, width = "unknown", 0
        if visibility == "visible" and abs(width - WINDOW_SIZE[0]) <= 60:
            return drv
        log("browser window came up %s with width %s (attempt %d), starting a new one" % (visibility, width, attempt + 1))
        if attempt < tries - 1:
            try:
                drv.quit()
            except WebDriverException:
                pass
            time.sleep(2)
    return drv


def candidate_urls(domain):
    domain = domain.strip()
    if domain.startswith(("http://", "https://")):
        return [domain]
    urls = ["https://" + domain]
    if not domain.startswith("www."):
        urls.append("https://www." + domain)
    return urls


def page_has_content(drv):
    try:
        return drv.execute_script(
            "return location.href.indexOf('about:') !== 0 && !!document.body && "
            "(document.body.innerText.trim().length > 30 || document.images.length > 0);")
    except WebDriverException:
        return False


def open_site(drv, domain):
    """Loads https://domain, then https://www.domain. Returns (url, status) or (None, error)."""
    last = "unreachable"
    for url in candidate_urls(domain):
        try:
            drv.get(url)
            return url, "ok"
        except TimeoutException:
            # timeout: stop loading, use the page if it has content
            try:
                drv.execute_script("window.stop();")
            except WebDriverException:
                pass
            if page_has_content(drv):
                return url, "slow"
            last = "timeout"
        except WebDriverException as ex:
            last = banner_probe.short_error(ex)
            log("failed to get: " + url + " " + last)
    return None, last


def dismiss_alert(drv):
    try:
        drv.switch_to.alert.dismiss()
        time.sleep(0.1)
    except (NoAlertPresentException, WebDriverException):
        pass


def wait_for_page(drv, extra_wait=None):
    """Waits (at most 20 s) for document.readyState == 'complete', then lets late banners render."""
    end = time.time() + 20
    while time.time() < end:
        try:
            if drv.execute_script("return document.readyState") == "complete":
                break
        except WebDriverException:
            pass
        time.sleep(0.5)
    time.sleep(POST_LOAD_WAIT if extra_wait is None else extra_wait)
    dismiss_alert(drv)


def wait_for_body():
    # not fatal, search anyway
    try:
        WebDriverWait(driver, 4).until(ec.presence_of_element_located((By.TAG_NAME, "body")))
    except TimeoutException:
        pass
    time.sleep(1)
    try:
        WebDriverWait(driver, 2).until(lambda d: d.execute_script('return document.readyState') == 'complete')
    except TimeoutException:
        pass


def find_cookie_banners(origin_el=None, translate=False, stale_flag=False):
    global driver, this_lang
    try:
        banners = []
        banners_map = dict()

        if origin_el is None:
            wait_for_body()
            origin_el = driver.find_element(By.TAG_NAME, "body")
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

        if not banners or len(banners) == 0:
            origin_el = driver.find_element(By.TAG_NAME, "body")

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


def find_shadowdom_banners(driver):
    banners = []
    root_copy_pairs = add_shadow_dom_to_body(driver)
    for root_copy_pair in root_copy_pairs:
        shadow_dom_banner = find_cookie_banners(origin_el=root_copy_pair[1])
        # keep only banners inside this host's copy
        shadow_dom_banner = [b for b in shadow_dom_banner if not isinstance(b, tuple) and
                             driver.execute_script("return arguments[0].contains(arguments[1]);", root_copy_pair[1], b)]
        if shadow_dom_banner:
            banners.append((root_copy_pair[0], shadow_dom_banner[0]))

    return banners


def detect_banners(data, running_for_category_detection=False):  # return banners of the current running url
    global driver, this_url, this_domain, this_status, this_lang, this_index
    banners = []
    if not running_for_category_detection:
        inc_counter()
    if not data.url:
        return banners
    if not running_for_category_detection:
        this_index = data.index
        this_url = data.url
        this_domain = data.domain
        this_lang = None
    time.sleep(3)
    # first search + ATTEMPTS retries
    for attempt in range(ATTEMPTS + 1):
        if attempt > 0:
            time.sleep(ATTEMPT_STEP_SLEEP_TIME)
            if not running_for_category_detection:
                data.ttw = attempt * ATTEMPT_STEP_SLEEP_TIME
        try:
            banners = find_cookie_banners()
        except Exception as ex:
            banners = []
            with open(log_file, 'a+') as f:
                print("failed detecting banner (attempt %d) for domain: %s %s" % (attempt, data.domain, traceback.format_exc()), file=f)
            try:
                driver.switch_to.default_content()
            except WebDriverException:
                pass
        if banners:
            break
    if not running_for_category_detection:
        try:
            this_lang = page_lang(driver)
        except Exception:
            this_lang = None
        data.lang = this_lang
    return banners


def get_sc_file_name(index=None, url=None):
    global driver, this_url
    if url is None:
        url = this_url
    return str(index + 1) + " " + get_current_domain(driver, url)


def take_current_page_sc(data=None, suffix=""):
    global driver, SCREENSHOT
    if not SCREENSHOT:
        return None
    if data is None:
        index = this_index
        url = this_url
    else:
        index = data.index
        url = data.url
    path = sc_dir + get_sc_file_name(index, url) + suffix + ".png"
    try:
        driver.switch_to.default_content()
        driver.save_screenshot(path)
        return path
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("failed to take screenshot for url: " + url + " " + traceback.format_exc(), file=f)
    return None


def inc_counter():
    global counter
    counter += 1


def banner_item_info(item):
    """text, html and kind of a detected banner"""
    info = {"kind": "dom", "text": "", "html": ""}
    try:
        if isinstance(item, tuple):
            first, inner = item
            if first.tag_name.lower() in ("iframe", "frame"):
                info["kind"] = "iframe"
                driver.switch_to.frame(first)
                if isinstance(inner, tuple):
                    driver.switch_to.frame(inner[0])
                    inner = inner[1]
            else:
                info["kind"] = "shadow"
            element = inner
        else:
            element = item
        info["text"] = element.text or ""
        info["html"] = (to_html(element) or "")[:300000]
    except WebDriverException as ex:
        info["error"] = banner_probe.short_error(ex)
    finally:
        try:
            driver.switch_to.default_content()
        except WebDriverException:
            pass
    return info


def detect_items(data, for_category=True):
    """detect banners and remove the shadow dom copies"""
    items = detect_banners(data, running_for_category_detection=for_category)
    infos = [banner_item_info(item) for item in items]
    # remove the shadow dom copies from the page
    del_cloned_shadow_hosts(driver)
    return items, infos


def choose_primary(items, infos):
    """pick the banner to categorize"""
    best, best_score = None, -1.0
    for k, (item, info) in enumerate(zip(items, infos)):
        try:
            target = banner_probe.prepare_target(driver, item, info.get("text", ""), info.get("html", ""))
            st = banner_probe.get_state(driver, target)
        except (StaleElementReferenceException, JavascriptException, NoSuchFrameException) as ex:
            log("could not locate detected banner %d: %s" % (k, banner_probe.short_error(ex)))
            continue
        score = 0.0
        # located text must match the detected text
        match = banner_probe.text_similarity(target.text, info.get("text", ""))
        if st.get("status") == "visible" and match >= 0.3:
            box = st["box"]
            score = box["w"] * box["h"] * st["vis"] * match * (2.0 if target.info.get("how") == "button" else 1.0)
        if score > best_score:
            best, best_score = k, score
    if best is None:
        return None
    # attach to the chosen banner again
    return banner_probe.prepare_target(driver, items[best], infos[best].get("text", ""), infos[best].get("html", ""))


def clear_site_state():
    try:
        driver.delete_all_cookies()
    except WebDriverException:
        pass
    try:
        driver.execute_script("try { localStorage.clear(); } catch (e) {} try { sessionStorage.clear(); } catch (e) {}")
    except WebDriverException:
        pass


def make_reload_fn(data):
    def reload_site(target):
        """reload the site and find the same banner again"""
        try:
            clear_site_state()
            try:
                driver.get(data.url)
            except TimeoutException:
                driver.execute_script("window.stop();")
            wait_for_page(driver, extra_wait=5)
            items, infos = detect_items(data)
            best, best_sim = None, 0.0
            for item, info in zip(items, infos):
                sim = banner_probe.text_similarity(target.text, info.get("text", ""))
                if sim > best_sim:
                    best, best_sim = (item, info), sim
            if best is None or best_sim < 0.5:
                log("reload: banner not found again for " + data.url)
                return False
            target.adopt(banner_probe.prepare_target(driver, best[0], target.text, target.html))
            log("reload: banner found again for " + data.url)
            return True
        except (TimeoutException, StaleElementReferenceException, JavascriptException, NoSuchFrameException) as ex:
            log("reload failed for %s: %s" % (data.url, banner_probe.short_error(ex)))
            return False
    return reload_site


def save_banner_screenshots(data, state):
    """Full screenshot (used by update_closing_score.py) plus a crop of the banner box."""
    path = take_current_page_sc(data)
    if not path or state.get("status") != "visible":
        return
    try:
        img = Image.open(path)
        scale = img.width / float(max(1, state.get("vw") or img.width))
        box = state["box"]
        crop = (max(0, int(box["x"] * scale)), max(0, int(box["y"] * scale)),
                min(img.width, int((box["x"] + box["w"]) * scale)), min(img.height, int((box["y"] + box["h"]) * scale)))
        if crop[2] > crop[0] and crop[3] > crop[1]:
            img.crop(crop).save(sc_dir + get_sc_file_name(data.index, data.url) + "_banner1.png")
    except (OSError, ValueError) as ex:
        log("failed to crop banner screenshot for %s: %s" % (data.url, ex))


def anti_bot_signature(page):
    text = ((page or {}).get("title", "") + " " + (page or {}).get("text", "")).lower()
    for sig in list(ANTI_BOT_SIGNATURES_MANUALLY_IDENTIFIED) + list(ANTI_BOT_SIGNATURES):
        if sig.lower() in text:
            return sig
    return None


def run_site(task):
    """Visits one site and returns a JSON-serialisable result with the banner category and all observations."""
    global driver, this_index, this_url, this_domain
    set_output_paths(task["urls_file"])
    started = time.time()
    deadline = started + task.get("budget", SITE_TIMEOUT - 30)
    domain = task["domain"]
    result = {"domain": domain, "index": task["index"], "input_file": task["urls_file"],
              "started": datetime.now().isoformat(timespec="seconds"),
              "category": banner_probe.UNDETERMINED, "reason": "", "confidence": "none"}
    data = SimpleNamespace(url="", domain=domain, index=task["index"], lang=None, ttw=0, status=None)
    driver = None
    timing = result["timing"] = {}
    try:
        driver = start_browser()
        timing["browser_start"] = round(time.time() - started, 1)
        url, load_status = open_site(driver, domain)
        result["load_status"] = load_status
        if not url:
            result.update(category="Unreachable", reason=load_status, confidence="high")
            return result
        data.url = result["url"] = url
        this_index, this_url, this_domain = data.index, url, domain
        wait_for_page(driver)
        timing["page_load"] = round(time.time() - started, 1)
        result["final_url"] = driver.current_url
        page = banner_probe.js(driver, "pageInfo()")
        result["anti_bot"] = anti_bot_signature(page)

        items, infos = detect_items(data, for_category=False)
        timing["detection"] = round(time.time() - started, 1)
        result["detected"] = [{"kind": i["kind"], "text": i["text"][:300]} for i in infos]
        if not items:
            take_current_page_sc(data)
            reason = "no cookie banner detected"
            if result["anti_bot"]:
                reason += " (bot check: %s)" % result["anti_bot"]
            result.update(category="No banner", reason=reason, confidence="high")
            return result

        target = choose_primary(items, infos)
        if target is None:
            result.update(reason="banner detected but not found on the page")
            take_current_page_sc(data)
            return result
        result["banner_text"] = target.text[:3000]
        result["banner_html"] = target.html
        state = banner_probe.settle(driver, target)
        save_banner_screenshots(data, state)

        obs = banner_probe.categorize(driver, target, reload_fn=make_reload_fn(data),
                                      deadline=deadline, site_domain=domain)
        category, reason, confidence = banner_probe.classify(obs)
        if "hidden" in ((obs.get("passive") or {}).get("visibility"), (obs.get("scroll") or {}).get("visibility")):
            # hidden window, run_crawl.py retries the site
            result["window_hidden"] = True
            reason += " [window hidden]"
            confidence = "low"
        result.update(category=category, reason=reason, confidence=confidence,
                      closed_by=banner_probe.closed_by(obs), observations=obs)
        log("%s: %s (%s, %s)" % (domain, category, reason, confidence))
    except Exception as ex:
        result.update(category=banner_probe.UNDETERMINED, reason="exception: " + banner_probe.short_error(ex),
                      confidence="none", traceback=traceback.format_exc())
        log("exception for %s:\n%s" % (domain, traceback.format_exc()))
    finally:
        result["secs"] = round(time.time() - started, 1)
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
    return result


if __name__ == '__main__':
    import run_crawl
    run_crawl.main()
