"""Banner categorization: escape, click outside, scroll, keyboard and link probes. classify() gives the category."""
import os
import random
import re
import time
from urllib.parse import urldefrag, urlparse

from selenium.common.exceptions import (
    JavascriptException,
    MoveTargetOutOfBoundsException,
    NoSuchFrameException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from selenium.webdriver.common.keys import Keys

try:
    import tldextract
    _TLD = tldextract.TLDExtract(suffix_list_urls=())  # bundled public suffix list, no network access
except Exception:
    _TLD = None

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "banner_probe.js"), encoding="utf-8") as _f:
    PROBE_JS = _f.read()

SIMPLE, STATIC, FIXED, BLOCKING = "Simple banner", "Static banner", "Fixed banner", "Blocking banner"
UNDETERMINED = "Undetermined"

GRID_COLS, GRID_ROWS, GRID_MARGIN = 16, 10, 16
MIN_SCROLL = 60          # px the page must move before scroll behaviour is judged
PAGE_CHANGED = "page changed"
RISKY_LINK = re.compile(r"logout|log-out|signout|sign-out|abmelden|unsubscribe|delete|download", re.I)
_WORD = re.compile(r"\w{3,}", re.UNICODE)

# element or frame is gone
_GONE_ERRORS = (StaleElementReferenceException, NoSuchFrameException, JavascriptException)


class Target:
    """detected banner (dom, iframe or shadow)"""

    def __init__(self, kind, frames, element, text="", html=""):
        self.kind = kind            # 'dom' | 'iframe' | 'shadow'
        self.frames = frames
        self.element = element
        self.text = text or ""
        self.html = html or ""
        self.info = {}
        self.url = ""

    def adopt(self, other):
        self.kind, self.frames, self.element, self.info = other.kind, other.frames, other.element, other.info
        self.url = other.url


def js(driver, call, *args):
    return driver.execute_script(PROBE_JS + "\nreturn window.__bp." + call + ";", *args)


def to_top(driver):
    driver.switch_to.default_content()


def to_frames(driver, frames):
    driver.switch_to.default_content()
    for frame in frames:
        driver.switch_to.frame(frame)


def short_error(ex):
    return (str(ex).strip().splitlines() or [type(ex).__name__])[0][:200]


def text_similarity(signature, candidate):
    """Share of the original banner's words found in the candidate text."""
    a = {w.lower() for w in _WORD.findall(signature or "")}
    b = {w.lower() for w in _WORD.findall(candidate or "")}
    if not a or not b:
        return 0.0
    return len(a & b) / len(a)


def registered_domain(host):
    host = (host or "").lower().strip(".")
    if _TLD is not None:
        try:
            ext = _TLD(host)
            if ext.domain and ext.suffix:
                return ext.domain + "." + ext.suffix
        except Exception:
            pass
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def same_page(url_a, url_b):
    return urldefrag(url_a or "")[0].rstrip("/") == urldefrag(url_b or "")[0].rstrip("/")


def intersect(a, b):
    x, y = max(a["x"], b["x"]), max(a["y"], b["y"])
    r, btm = min(a["x"] + a["w"], b["x"] + b["w"]), min(a["y"] + a["h"], b["y"] + b["h"])
    if r <= x or btm <= y:
        return None
    return {"x": x, "y": y, "w": r - x, "h": btm - y}


def same_box(a, b, tol):
    return all(abs(a[k] - b[k]) <= tol for k in ("x", "y", "w", "h"))


def prepare_target(driver, item, text="", html=""):
    """detection result -> Target"""
    to_top(driver)
    if isinstance(item, tuple):
        first = item[0]
        if first.tag_name.lower() in ("iframe", "frame"):
            frames, inner = [first], item[1]
            if isinstance(inner, tuple):
                frames.append(inner[0])
                inner = inner[1]
            target = Target("iframe", frames, inner, text, html)
            js(driver, "setAnchor(arguments[0], 'iframe')", first)
            to_frames(driver, frames)
            target.info = js(driver, "setAnchor(arguments[0], 'dom')", inner)
            to_top(driver)
        else:
            target = Target("shadow", [], first, text, html)
            target.info = js(driver, "setAnchor(arguments[0], 'shadow')", first)
    else:
        target = Target("dom", [], item, text, html)
        target.info = js(driver, "setAnchor(arguments[0], 'dom')", item)
    # use the dialog text, the detected element can be a page wrapper
    target.text = target.info.get("text") or target.text
    target.url = driver.current_url
    return target


def get_state(driver, t):
    """visible / offscreen / gone, with the banner box"""
    try:
        to_top(driver)
        top = js(driver, "state()")
        if t.kind != "iframe" or top.get("status") == "gone":
            return top
        ox, oy = top["frame"]["x"], top["frame"]["y"]
        driver.switch_to.frame(t.frames[0])
        for frame in t.frames[1:]:
            off = js(driver, "frameOffsetOf(arguments[0])", frame)
            ox, oy = ox + off["x"], oy + off["y"]
            driver.switch_to.frame(frame)
        inner = js(driver, "state()")
        to_top(driver)
        if inner.get("status") == "gone":
            return {"status": "gone", "why": "frame_" + str(inner.get("why"))}
        b = inner["box"]
        box = {"x": b["x"] + ox, "y": b["y"] + oy, "w": b["w"], "h": b["h"]}
        box = intersect(box, top["box"]) or box
        view = {"x": 0, "y": 0, "w": top["vw"], "h": top["vh"]}
        on_screen = intersect(box, view)
        vis = (on_screen["w"] * on_screen["h"]) / max(1.0, box["w"] * box["h"]) if on_screen else 0.0
        on_screen_area = on_screen["w"] * on_screen["h"] if on_screen else 0.0
        return {"status": "visible" if (vis > 0.02 or on_screen_area >= 15000) else "offscreen", "box": box, "vis": vis,
                "vw": top["vw"], "vh": top["vh"], "frame": {"x": ox, "y": oy}}
    except _GONE_ERRORS as ex:
        try:
            to_top(driver)
        except WebDriverException:
            pass
        return {"status": "gone", "why": "error: " + short_error(ex)}


def settle(driver, t, max_wait=5.0):
    """wait until the banner stops moving"""
    end = time.time() + max_wait
    prev, stable, st = None, 0, None
    while True:
        st = get_state(driver, t)
        if (st.get("status") == "visible" and prev and prev.get("status") == "visible"
                and same_box(prev["box"], st["box"], 2)):
            stable += 1
            if stable >= 2:
                return st
        else:
            stable = 0
        if time.time() >= end:
            return st
        prev = st
        time.sleep(0.35)


def scroll_state(driver, x=5, y=5):
    to_top(driver)
    return js(driver, "scrollState(arguments[0], arguments[1])", int(x), int(y))


def at_top(s):
    return s["win"]["top"] <= 2 and (not s.get("inner") or s["inner"]["top"] <= 2)


def press(driver, key, times=1, pause=(0.5, 0.9)):
    for _ in range(times):
        ActionChains(driver).send_keys(key).perform()
        time.sleep(random.uniform(*pause))


def ensure_top(driver, x=5, y=5):
    """scroll back to the top (Home key, js if needed)"""
    s = scroll_state(driver, x, y)
    if at_top(s):
        return True
    js(driver, "blurActive()")
    press(driver, Keys.HOME, 1, pause=(0.5, 0.7))
    if at_top(scroll_state(driver, x, y)):
        return True
    js(driver, "restoreTop()")
    time.sleep(0.5)
    return at_top(scroll_state(driver, x, y))


def _find_banner_in_frames(driver, t, need_visible):
    to_top(driver)
    frames = []
    for f in driver.find_elements("tag name", "iframe")[:30]:
        try:
            size = f.size
            if size["width"] >= 50 and size["height"] >= 30 and f.is_displayed():
                frames.append(f)
        except _GONE_ERRORS:
            continue
    for f in frames[:10]:
        try:
            to_frames(driver, [f])
            res = js(driver, "findBanner(arguments[0], arguments[1])", t.text, need_visible)
            if res and res.get("found"):
                return (f, res["el"])
        except (_GONE_ERRORS + (NoSuchFrameException,)):
            continue
        finally:
            to_top(driver)
    return None


def relocate(driver, t, need_visible=True):
    """find the banner again by its text, True if found"""
    item = None
    try:
        to_top(driver)
        res = js(driver, "findBanner(arguments[0], arguments[1])", t.text, need_visible)
        if res and res.get("found"):
            item = (res["host"], res["el"]) if res.get("host") else res["el"]
        elif t.kind == "iframe":
            item = _find_banner_in_frames(driver, t, need_visible)
        if item is None:
            return False
        new = prepare_target(driver, item, t.text, t.html)
    except _GONE_ERRORS:
        return False
    st = get_state(driver, new)
    if st.get("status") == "gone" or (need_visible and st.get("status") != "visible"):
        return False
    t.adopt(new)
    return True


def wait_for_document(driver, timeout=15, settle_time=4):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if driver.execute_script("return document.readyState") == "complete":
                break
        except WebDriverException:
            pass
        time.sleep(0.5)
    time.sleep(settle_time)


def wait_closed(driver, t, timeout=3.0):
    """True if the banner is closed"""
    end = time.time() + timeout
    restored = False
    while True:
        st = get_state(driver, t)
        if st.get("status") == "visible":
            if time.time() >= end:
                return False, "still visible"
            time.sleep(0.4)
            continue
        if st.get("status") == "offscreen" and not restored and not at_top(scroll_state(driver)):
            # page scrolled, not the banner
            js(driver, "restoreTop()")
            restored = True
            time.sleep(0.4)
            continue
        time.sleep(0.7)                                   # let close animations finish
        st = get_state(driver, t)
        if st.get("status") == "visible":
            continue
        if st.get("why") == "no_anchor":
            # page reloaded: same url without the banner counts as closed
            wait_for_document(driver)
            for _ in range(3):
                if relocate(driver, t):
                    return False, PAGE_CHANGED
                time.sleep(2)
            if same_page(t.url, driver.current_url):
                return True, "page reloaded without the banner"
            return False, PAGE_CHANGED
        if relocate(driver, t):
            return False, "re-rendered"
        return True, st.get("why") or st.get("status")


def hit_grid(driver, t, st):
    """hit test on a grid around the banner"""
    to_top(driver)
    box = st.get("box")
    grid = js(driver, "hitGrid(arguments[0], %d, %d, %d)" % (GRID_COLS, GRID_ROWS, GRID_MARGIN), box)
    if t.kind == "iframe" and st.get("frame"):
        _verify_frame_backdrop(driver, t, grid, st["frame"])
    counts = grid.get("counts", {})
    n = grid.get("n", 0)
    grid["reachable"] = round((counts.get("content", 0) + counts.get("bare", 0)) / n, 3) if n else None
    return grid


def _verify_frame_backdrop(driver, t, grid, offset):
    """check grey area points inside the banner iframe"""
    candidates = sorted((p for p in grid["points"] if p.get("frame")), key=lambda p: -p.get("dist", 0))[:12]
    if not candidates:
        return
    try:
        to_frames(driver, t.frames)
        for p in candidates:
            info = js(driver, "pointInfo(arguments[0], arguments[1])", p["x"] - offset["x"], p["y"] - offset["y"])
            p["backdrop"] = bool(info and not info.get("none") and not info.get("inDialog")
                                 and not info.get("interactive") and info.get("ownText", 0) < 20)
            p["frame_desc"] = info.get("desc") if info else None
    except _GONE_ERRORS:
        pass
    finally:
        to_top(driver)


def compact_grid(grid):
    pts = [{k: p.get(k) for k in ("x", "y", "cls", "desc", "safe", "backdrop")} for p in grid.get("points", [])]
    return {"n": grid.get("n"), "counts": grid.get("counts"), "reachable": grid.get("reachable"), "points": pts}


def click_at(driver, x, y):
    """A real left click at viewport coordinates (x, y)."""
    ab = ActionBuilder(driver)
    ab.pointer_action.move_to_location(int(x), int(y)).pause(random.uniform(0.15, 0.3)) \
        .pointer_down().pause(random.uniform(0.06, 0.14)).pointer_up()
    ab.perform()


def close_new_windows(driver, main_handle, before):
    new = [h for h in driver.window_handles if h not in before]
    for handle in new:
        try:
            driver.switch_to.window(handle)
            driver.close()
        except WebDriverException:
            pass
    driver.switch_to.window(main_handle)
    return len(new)


def click_point(driver, pt, kind, wait=1.2):
    """click pt, returns reached / blocked / not_observed"""
    to_top(driver)
    main = driver.current_window_handle
    before = list(driver.window_handles)
    url0 = driver.current_url
    js(driver, "recStart()")
    click_at(driver, pt["x"], pt["y"])
    time.sleep(wait)
    new_windows = close_new_windows(driver, main, before)
    navigated = not same_page(url0, driver.current_url)
    event = None
    if not navigated:
        try:
            events = js(driver, "recEvents()") or []
            order = {"pointerdown": 0, "mousedown": 1, "click": 2}
            events = sorted((e for e in events if e.get("type") in order), key=lambda e: order[e["type"]])
            event = events[0] if events else None
        except _GONE_ERRORS:
            event = None
    if navigated or new_windows:
        result = "reached"
    elif event is None:
        result = "blocked" if pt.get("frame") else "not_observed"   # frame clicks go into the banner's iframe
    elif event.get("cls") in ("content", "bare"):
        result = "reached"
    else:
        result = "blocked"
    return {"kind": kind, "x": pt["x"], "y": pt["y"], "target": pt.get("desc"), "expected": pt.get("cls"),
            "event": event, "result": result, "navigated": navigated, "new_windows": new_windows}


def escape_probe(driver, t):
    out = {"closed": False}
    to_top(driver)
    out["focus_before"] = js(driver, "focusInfo()")
    press(driver, Keys.ESCAPE, 2)
    closed, why = wait_closed(driver, t)
    if closed:
        out.update(closed=True, how="escape", why=why)
        return out
    if why == PAGE_CHANGED:
        out["page_changed"] = True
        return out
    # some banners close on escape only when focused, tab into it
    fi = js(driver, "focusInfo()")
    presses = 0
    while not fi.get("inRoot") and presses < 12:
        press(driver, Keys.TAB, 1, pause=(0.15, 0.3))
        presses += 1
        fi = js(driver, "focusInfo()")
    out["focused_banner"] = bool(fi.get("inRoot"))
    out["tab_presses"] = presses
    if fi.get("inRoot"):
        press(driver, Keys.ESCAPE, 2)
        closed, why = wait_closed(driver, t)
        if closed:
            out.update(closed=True, how="escape_after_focus", why=why)
        elif why == PAGE_CHANGED:
            out["page_changed"] = True
    return out


def pointer_probe(driver, t, grid):
    out = {"closed": False, "clicks": []}
    pts = grid.get("points", [])
    backdrop = sorted((p for p in pts if p.get("backdrop")), key=lambda p: -p.get("dist", 0))
    content = sorted((p for p in pts if p.get("cls") in ("content", "bare") and p.get("safe")),
                     key=lambda p: (not p.get("texty"), -p.get("dist", 0)))
    out["candidates"] = {"backdrop": len(backdrop), "content": len(content)}
    plan = []
    if backdrop:
        plan.append(("backdrop", backdrop[0]))
    if content:
        plan.append(("content", content[0]))
    for kind, pt in plan:
        if get_state(driver, t).get("status") != "visible":
            break
        click = click_point(driver, pt, kind)
        out["clicks"].append(click)
        if click["navigated"]:
            out["navigated"] = True        # page changed
            break
        closed, why = wait_closed(driver, t, timeout=2.5)
        if closed:
            out.update(closed=True, how="click_" + kind, why=why)
            return out
        if why == PAGE_CHANGED:
            out["page_changed"] = True
            break
    return out


def _wheel_point(grid, st):
    pts = grid.get("points", [])
    for pick in (lambda p: p.get("cls") == "content" and p.get("safe"),
                 lambda p: p.get("cls") in ("content", "bare"),
                 lambda p: p.get("cls") == "overlay" or p.get("backdrop")):
        cand = sorted((p for p in pts if pick(p)), key=lambda p: -p.get("dist", 0))
        if cand:
            return cand[0]["x"], cand[0]["y"]
    box = st["box"]
    x = st["vw"] // 2
    y = max(5, int(box["y"]) - 20) if box["y"] > st["vh"] / 2 else min(st["vh"] - 5, int(box["y"] + box["h"]) + 20)
    return x, y


def _scrolled(s0, s1):
    moved = abs(s1["win"]["top"] - s0["win"]["top"])
    if s0.get("inner") and s1.get("inner") and s0["inner"].get("desc") == s1["inner"].get("desc"):
        moved = max(moved, abs(s1["inner"]["top"] - s0["inner"]["top"]))
    return moved


def scroll_probe(driver, t, grid):
    out = {}
    ensure_top(driver)
    st0 = get_state(driver, t)
    if st0.get("status") != "visible":
        return {"verdict": "error", "why": "banner not visible before scrolling"}
    box0, vh = st0["box"], st0["vh"]
    # hidden page (minimized window, locked screen) does not scroll
    out["visibility"] = driver.execute_script("return document.visibilityState")
    x, y = _wheel_point(grid, st0)
    out["scroller"] = js(driver, "pinScroller(arguments[0], arguments[1])", int(x), int(y))
    s0 = scroll_state(driver, x, y)
    need = min(max(box0["y"] + box0["h"] + 80, 0.9 * vh), 2.5 * vh)
    moved, stalls, steps = 0, 0, 0
    while moved < need and steps < 25 and stalls < 3:
        try:
            ActionChains(driver).scroll_from_origin(
                ScrollOrigin.from_viewport(int(x), int(y)), 0, random.randint(150, 230)).perform()
        except MoveTargetOutOfBoundsException:
            break
        steps += 1
        time.sleep(random.uniform(0.25, 0.45))
        m = _scrolled(s0, scroll_state(driver, x, y))
        stalls = stalls + 1 if m <= moved + 2 else 0
        moved = max(moved, m)
    time.sleep(0.6)
    moved = _scrolled(s0, scroll_state(driver, x, y))
    out.update(method="wheel", wheel_point=[x, y], steps=steps)
    if moved < MIN_SCROLL:
        js(driver, "blurActive()")
        press(driver, Keys.PAGE_DOWN, 3, pause=(0.4, 0.6))
        time.sleep(0.4)
        moved = _scrolled(s0, scroll_state(driver, x, y))
        out["method"] = "keyboard"
    out["scrolled_px"] = moved
    out["scroll_start"] = s0

    st1 = get_state(driver, t)
    if st1.get("status") == "gone" and relocate(driver, t, need_visible=False):
        st1 = get_state(driver, t)
    out["after"] = st1

    # scroll back up, then Home
    for _ in range(steps + 3):
        if at_top(scroll_state(driver, x, y)):
            break
        try:
            ActionChains(driver).scroll_from_origin(
                ScrollOrigin.from_viewport(int(x), int(y)), 0, -random.randint(250, 350)).perform()
        except MoveTargetOutOfBoundsException:
            break
        time.sleep(random.uniform(0.2, 0.35))
    back_at_top = ensure_top(driver, x, y)
    time.sleep(1.0)
    st2 = get_state(driver, t)
    if st2.get("status") == "gone" and relocate(driver, t):
        st2 = get_state(driver, t)
    out["back"] = st2
    out["back_at_top"] = back_at_top

    if st2.get("status") == "visible":
        out["reappeared"] = True
    elif back_at_top:
        out["reappeared"] = False
    else:
        out["reappeared"] = None          # not back at the top, unknown

    out["before"] = st0
    if moved >= MIN_SCROLL and st1.get("box"):
        shift = box0["y"] - st1["box"]["y"]
        out["banner_shift_px"], out["ratio"] = round(shift, 1), round(shift / moved, 3)
    out["verdict"] = scroll_verdict(out)
    return out


def _on_screen_area(st):
    box = (st or {}).get("box")
    if not box or not st.get("vw"):
        return 0.0
    inter = intersect(box, {"x": 0, "y": 0, "w": st["vw"], "h": st["vh"]})
    return inter["w"] * inter["h"] if inter else 0.0


def scroll_verdict(sc):
    """no_scroll / disappeared / moved_with_page / stayed"""
    if (sc.get("scrolled_px") or 0) < MIN_SCROLL:
        return "no_scroll"
    after = sc.get("after") or {}
    if after.get("status") == "gone":
        return "disappeared"
    if "ratio" not in sc:
        return sc.get("verdict")
    ratio, area_after = sc["ratio"], _on_screen_area(after)
    on_screen = after.get("vis", 0) > 0.02 or area_after >= 15000
    if ratio >= 0.6 or not on_screen:
        return "moved_with_page"
    if ratio <= 0.25:
        return "stayed"
    return "stayed" if area_after >= 0.5 * _on_screen_area(sc.get("before")) else "moved_with_page"


def keyboard_probe(driver, t, max_presses=40):
    """tab through the page, recorded only"""
    ensure_top(driver)
    js(driver, "resetFocusStart()")
    seen = {}
    for i in range(max_presses):
        press(driver, Keys.TAB, 1, pause=(0.12, 0.25))
        fi = js(driver, "focusInfo()")
        if fi.get("none"):
            continue
        if not fi.get("inRoot") and fi.get("visible"):
            return {"escapes": True, "trapped": False, "presses": i + 1, "first_outside": fi.get("desc")}
        key = (fi.get("desc"), fi.get("label"))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] >= 3:
            return {"escapes": False, "trapped": True, "presses": i + 1}
    return {"escapes": False, "trapped": False, "presses": max_presses}


def _usable_link(link, page_url, site_domain):
    href = (link or {}).get("href") or ""
    if not href or link.get("download"):
        return False
    parsed = urlparse(href)
    if parsed.scheme not in ("http", "https") or same_page(href, page_url):
        return False
    if RISKY_LINK.search(href + " " + (link.get("text") or "")):
        return False
    site_host = urlparse(site_domain).hostname if "://" in site_domain else site_domain.split("/")[0]
    rd = registered_domain(parsed.hostname)
    return rd in (registered_domain(urlparse(page_url).hostname), registered_domain(site_host))


def link_probe(driver, t, st, site_domain):
    """Clicks a same-site link outside the banner and waits for the page to navigate."""
    to_top(driver)
    page_url = driver.current_url
    candidates = js(driver, "linkPoints(arguments[0], %d)" % GRID_MARGIN, st.get("box")) or []
    links = [p for p in candidates if _usable_link(p.get("link"), page_url, site_domain)]
    if not links:
        return {"result": "no_candidate", "visible_links": len(candidates)}
    links.sort(key=lambda p: (p["link"].get("target") == "_blank",
                              not (2 <= len(p["link"].get("text") or "") <= 40), -p.get("dist", 0)))
    pt = links[0]
    to_top(driver)
    main = driver.current_window_handle
    before = list(driver.window_handles)
    js(driver, "recStart()")
    click_at(driver, pt["x"], pt["y"])
    navigated, new_windows = False, 0
    for _ in range(16):
        time.sleep(0.5)
        if len(driver.window_handles) > len(before):
            time.sleep(0.5)
            new_windows = close_new_windows(driver, main, before)
            break
        if not same_page(page_url, driver.current_url):
            navigated = True
            break
    out = {"href": pt["link"]["href"], "text": pt["link"].get("text"), "x": pt["x"], "y": pt["y"],
           "navigated": navigated, "new_windows": new_windows}
    if navigated or new_windows:
        out["result"] = "navigated"
        return out
    try:
        events = [e for e in (js(driver, "recEvents()") or []) if e.get("type") in ("pointerdown", "mousedown", "click")]
    except _GONE_ERRORS:
        events = []
    out["events"] = events
    click = next((e for e in events if e["type"] == "click"), events[0] if events else None)
    if click is None:
        out["result"] = "not_observed"
    elif click.get("cls") not in ("content", "bare"):
        out["result"] = "blocked"
    elif click.get("type") == "click" and click.get("prevented"):
        out["result"] = "prevented"
    else:
        out["result"] = "reached"
    return out


def ensure_baseline(driver, t, reload_fn):
    """Puts the page back to the top with the banner shown, reloading the site if the banner got lost."""
    ensure_top(driver)
    st = get_state(driver, t)
    if st.get("status") == "visible":
        return st, False
    if relocate(driver, t):
        st = get_state(driver, t)
        if st.get("status") == "visible":
            return st, False
    if reload_fn(t):
        st = settle(driver, t)
        if st.get("status") == "visible":
            return st, True
    return None, True


def categorize(driver, t, reload_fn, deadline, site_domain):
    """Runs the probes on the banner t and returns the observations; classify(obs) gives the category."""
    obs = {"kind": t.kind, "located": {k: v for k, v in t.info.items() if k != "text"}, "reloads": 0, "timing": {}}
    mark = [time.time()]

    def timed(name):
        now = time.time()
        obs["timing"][name] = round(now - mark[0], 1)
        mark[0] = now

    st = settle(driver, t)
    if st.get("status") != "visible" and relocate(driver, t):
        st = settle(driver, t)
    obs["baseline"] = st
    if st.get("status") != "visible":
        obs["fatal"] = "banner not visible after detection (%s)" % st.get("why", st.get("status"))
        return obs
    to_top(driver)
    obs["passive"] = js(driver, "passive()")
    grid = hit_grid(driver, t, st)
    obs["hit"] = compact_grid(grid)
    timed("baseline")

    # 1. Escape
    obs["escape"] = escape_probe(driver, t)
    if obs["escape"].get("page_changed"):
        # page reloaded during escape, try once more
        st, reloaded = ensure_baseline(driver, t, reload_fn)
        obs["reloads"] += int(reloaded)
        if st is not None:
            obs["escape_interrupted"] = obs["escape"]
            obs["escape"] = escape_probe(driver, t)
    timed("escape")
    if obs["escape"]["closed"]:
        return obs

    # 2. click outside the banner (grey backdrop first, then page content)
    st, reloaded = ensure_baseline(driver, t, reload_fn)
    obs["reloads"] += int(reloaded)
    if st is None:
        obs["fatal"] = "banner lost before the click probe"
        return obs
    obs["pointer"] = pointer_probe(driver, t, hit_grid(driver, t, st))
    timed("pointer")
    if obs["pointer"]["closed"]:
        return obs

    # 3. scroll
    st, reloaded = ensure_baseline(driver, t, reload_fn)
    obs["reloads"] += int(reloaded)
    if st is None:
        obs["scroll"] = {"verdict": "error", "why": "banner lost before the scroll probe"}
        return obs
    obs["scroll"] = scroll_probe(driver, t, hit_grid(driver, t, st))
    timed("scroll")
    category = classify(obs)[0]
    if category == SIMPLE or (category == STATIC and obs["scroll"].get("verdict") in ("moved_with_page", "disappeared")):
        return obs

    # 4. keyboard (recorded only)
    if time.time() < deadline - 60:
        st, reloaded = ensure_baseline(driver, t, reload_fn)
        obs["reloads"] += int(reloaded)
        if st is not None:
            obs["keyboard"] = keyboard_probe(driver, t)
        timed("keyboard")

    # 5. link click outside the banner
    if time.time() < deadline - 40:
        st, reloaded = ensure_baseline(driver, t, reload_fn)
        obs["reloads"] += int(reloaded)
        if st is not None:
            obs["link"] = link_probe(driver, t, st, site_domain)
        timed("link")
    else:
        obs["link"] = {"result": "skipped", "why": "time budget"}
    return obs


def blocking_evidence(obs):
    """(blocked, confidence, reason) from the click, link and hit-test observations."""
    hit = obs.get("hit") or {}
    passive = obs.get("passive") or {}
    n = hit.get("n") or 0
    counts = hit.get("counts") or {}
    # pointer-events:none on the content, body clicks don't count
    dead_body = bool(passive.get("contentPointerNone") or passive.get("bodyPointerNone"))
    reachable_pts = counts.get("content", 0) + (0 if dead_body else counts.get("bare", 0))
    reach = round(reachable_pts / n, 3) if n else None
    clicks = (obs.get("pointer") or {}).get("clicks") or []

    def page_took_it(c):
        if c.get("navigated") or c.get("new_windows"):
            return True
        return c.get("result") == "reached" and not (dead_body and (c.get("event") or {}).get("cls") == "bare")

    reached = [c for c in clicks if page_took_it(c)]
    blocked = [c for c in clicks if not page_took_it(c) and c.get("result") in ("blocked", "reached")]
    link = (obs.get("link") or {}).get("result")
    locked = bool(passive.get("scrollLock")) and (obs.get("scroll") or {}).get("verdict") == "no_scroll"

    if link == "navigated":
        return False, "high", "link outside the banner works"
    # a cancelled link click still reached the page
    link_reached = link in ("reached", "prevented")
    if reached or link_reached:
        conf = "high" if (reached and link_reached) or (reach or 0) >= 0.3 else "medium"
        return False, conf, "page clickable next to the banner"
    if n < 8:
        return True, "medium", "banner covers the viewport"
    if reach is not None and reach < 0.10:
        strong = blocked or locked or passive.get("modalDialog") or passive.get("inertOutside")
        return True, "high" if strong else "medium", "only %d%% of the page around the banner clickable" % round(reach * 100)
    if blocked:
        return True, "medium", "clicks hit the banner or an overlay"
    if link in ("blocked", "not_observed"):
        return True, "low", "link click had no effect"
    if reach is not None and reach >= 0.5:
        return False, "low", "mostly page around the banner (not confirmed by a click)"
    return True, "low", "page around the banner mostly not clickable (%s)" % reach


def classify(obs):
    """Returns (category, reason, confidence) from the probe observations, following the taxonomy order."""
    if obs.get("fatal"):
        return UNDETERMINED, obs["fatal"], "none"
    esc = obs.get("escape") or {}
    if esc.get("closed"):
        how = " (banner focused)" if esc.get("how") == "escape_after_focus" else ""
        return SIMPLE, "closed by Escape" + how, "high"
    ptr = obs.get("pointer") or {}
    if ptr.get("closed"):
        where = "backdrop" if ptr.get("how") == "click_backdrop" else "outside"
        return SIMPLE, "closed by clicking " + where, "high"

    sc = obs.get("scroll") or {}
    verdict = scroll_verdict(sc) if sc.get("scrolled_px") is not None else sc.get("verdict")
    if verdict == "no_scroll" and sc.get("visibility") == "hidden":
        verdict = "error"                 # hidden window, scroll result not usable
    if verdict in ("moved_with_page", "disappeared") and sc.get("reappeared") is False:
        return SIMPLE, "closed by scrolling", "medium"

    blocked, conf, reason = blocking_evidence(obs)
    if verdict in ("moved_with_page", "disappeared") and sc.get("reappeared"):
        if blocked and conf == "high":
            return BLOCKING, reason + "; banner scrolls with the page", "medium"
        return STATIC, "scrolls with the page, back at the top", "high" if verdict == "moved_with_page" else "medium"
    if blocked:
        return BLOCKING, reason, conf
    positioning = (obs.get("passive") or {}).get("positioning")
    if verdict == "stayed":
        return FIXED, reason + "; stays in place on scroll", conf
    if verdict == "no_scroll":
        # page does not scroll, banner stays in view
        return FIXED, reason + "; page does not scroll", "medium" if conf == "high" else "low"
    # scroll probe failed, use the positioning
    if positioning == "flow":
        return STATIC, reason + "; scroll probe failed, banner in page flow", "low"
    return FIXED, reason + "; scroll probe failed, banner is %s" % positioning, "low"


def closed_by(obs):
    if (obs.get("escape") or {}).get("closed"):
        return "escape"
    if (obs.get("pointer") or {}).get("closed"):
        return obs["pointer"].get("how")
    sc = obs.get("scroll") or {}
    if sc.get("verdict") in ("moved_with_page", "disappeared") and sc.get("reappeared") is False:
        return "scroll"
    return ""
