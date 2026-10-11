// helpers for banner_probe.py (window.__bp)
(function () {
  if (window.__bp) return;

  var COOKIE_RE = /cookie|kakor|çerez|cerez|ciastecz|evästee|sütik|kolačić|piškotk|consent|einwillig|zustimm|datenschutz|privacy|privacidad|privacidade|confidentialit|riservatezza|personal data|personenbezogen|données|dati personali|datos personales|tracking|gdpr|dsgvo|rgpd|куки|クッキー|쿠키|隐私|隱私|partner/i;
  var COOKIE_WORD_RE = /cookie|kakor|çerez|cerez|ciastecz|evästee|sütik|kolačić|piškotk|куки|クッキー|쿠키/i;
  var ACTION_RE = /accept|agree|allow|consent|got it|\bok\b|okay|understood|i understand|continue|reject|decline|deny|refuse|necessary|essential|only|settings|manage|preferences|options|customi[sz]e|more info|learn more|akzeptier|zustimm|einverstanden|ablehn|einstellung|verstanden|annehmen|erlauben|speichern|weiter|accepter|refuser|continuer|paramètr|aceptar|rechazar|configur|accett|rifiut|aceitar|rejeitar|toestaan|weiger|akcept|odrzu|zgadzam|souhlas|принять|отклон|согла|同意|拒否|接受|拒绝|kabul|reddet|tamam|close|schließen|fermer|cerrar|chiudi/i;
  var INTERACTIVE_SEL = 'a[href],button,input,select,textarea,label,summary,option,video,audio,iframe,frame,embed,object,canvas,' +
    '[role=button],[role=link],[role=checkbox],[role=radio],[role=switch],[role=tab],[role=menuitem],[role=option],' +
    '[role=combobox],[role=slider],[onclick],[contenteditable=""],[contenteditable=true],[tabindex]:not([tabindex="-1"])';
  var CONTROL_SEL = 'a[href],button,input,select,textarea';
  var REAL_BUTTON_SEL = 'button,[role=button],input[type=button],input[type=submit]';
  var LANDMARK_SEL = 'nav,main,article';
  var CONTENT_TAGS = /^(BUTTON|INPUT|SELECT|TEXTAREA|IMG|SVG|VIDEO|CANVAS|IFRAME|A|PICTURE)$/i;

  var bp = {
    anchor: null, dialog: null, top: null, root: null, kind: null, scroller: null
  };

  function norm(s) { return (s || '').replace(/\s+/g, ' ').trim(); }

  // viewport size without scrollbars (quirks mode: body)
  function vp() {
    var de = (document.compatMode === 'BackCompat' && document.body) ? document.body : document.documentElement;
    var w = window.innerWidth, h = window.innerHeight;
    if (de && de.clientWidth > 0.5 * w && de.clientWidth <= w) w = de.clientWidth;
    if (de && de.clientHeight > 0.5 * h && de.clientHeight <= h) h = de.clientHeight;
    return {w: w, h: h};
  }

  function parentFlat(el) {
    if (!el) return null;
    if (el.parentElement) return el.parentElement;
    var r = el.getRootNode && el.getRootNode();
    return (r && r.host) ? r.host : null;
  }

  // true when el is anc or lies below it, crossing shadow boundaries
  function deepContains(anc, el) {
    for (var e = el, i = 0; e && i < 400; e = parentFlat(e), i++) {
      if (e === anc) return true;
    }
    return false;
  }

  // outermost element of the document tree that contains el (the shadow host chain for shadow content)
  function topLight(el) {
    var e = el;
    for (var i = 0; i < 20 && e; i++) {
      var r = e.getRootNode && e.getRootNode();
      if (!r || r === document || !r.host) return e;
      e = r.host;
    }
    return e;
  }

  function rectOf(el) {
    var r = el.getBoundingClientRect();
    return {x: r.left, y: r.top, w: r.width, h: r.height};
  }
  function area(r) { return r ? Math.max(0, r.w) * Math.max(0, r.h) : 0; }
  function intersect(a, b) {
    if (!a || !b) return null;
    var x = Math.max(a.x, b.x), y = Math.max(a.y, b.y);
    var r = Math.min(a.x + a.w, b.x + b.w), btm = Math.min(a.y + a.h, b.y + b.h);
    if (r <= x || btm <= y) return null;
    return {x: x, y: y, w: r - x, h: btm - y};
  }
  function union(a, b) {
    if (!a) return b;
    if (!b) return a;
    var x = Math.min(a.x, b.x), y = Math.min(a.y, b.y);
    return {x: x, y: y, w: Math.max(a.x + a.w, b.x + b.w) - x, h: Math.max(a.y + a.h, b.y + b.h) - y};
  }
  function viewRect() { var v = vp(); return {x: 0, y: 0, w: v.w, h: v.h}; }
  function coverFraction(r) { var v = vp(); return area(intersect(r, viewRect())) / Math.max(1, v.w * v.h); }

  function describe(el) {
    if (!el || !el.tagName) return String(el);
    var s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    var cls = (typeof el.className === 'string') ? el.className : (el.getAttribute && el.getAttribute('class')) || '';
    cls = norm(cls).split(' ').filter(Boolean).slice(0, 2);
    if (cls.length) s += '.' + cls.join('.');
    return s.slice(0, 90);
  }

  function ownText(el) {
    var t = '';
    for (var n = el.firstChild; n; n = n.nextSibling) {
      if (n.nodeType === 3) t += n.nodeValue + ' ';
    }
    return norm(t);
  }

  var textCache = null;
  function textLen(el) {
    if (textCache && textCache.has(el)) return textCache.get(el);
    var tc = (el.textContent || '').length;
    var n;
    if (tc <= 30) n = norm(el.innerText).length;
    else if (tc > 20000) n = tc;            // big subtree, skip innerText
    else n = norm(el.innerText).length;
    if (textCache) textCache.set(el, n);
    return n;
  }

  // calls fn for el and every element below it, descending into open shadow roots
  function walkDeep(el, fn, limit) {
    var stack = [el], n = 0;
    limit = limit || 6000;
    while (stack.length) {
      var e = stack.pop();
      if (++n > limit) return;
      if (fn(e) === false) continue;        // false: skip subtree
      var kids = e.children || [];
      for (var i = kids.length - 1; i >= 0; i--) stack.push(kids[i]);
      if (e.shadowRoot) {
        var sk = e.shadowRoot.children;
        for (var j = sk.length - 1; j >= 0; j--) stack.push(sk[j]);
      }
    }
  }

  function deepText(el) {
    var parts = [el.innerText || ''];
    walkDeep(el, function (e) {
      if (e.shadowRoot) {
        var sk = e.shadowRoot.children;
        for (var i = 0; i < sk.length; i++) parts.push(sk[i].innerText || '');
      }
    }, 3000);
    return norm(parts.join(' '));
  }

  function cs(el) { return window.getComputedStyle(el); }

  function isRenderedCheap(el) {
    if (!el.getClientRects || el.getClientRects().length === 0) return false;
    var s = cs(el);
    return s.visibility === 'visible' && s.display !== 'none';
  }

  // an ancestor (or el) is display:none or fully transparent
  function ancestorHidden(el) {
    for (var e = el, i = 0; e && i < 200; e = parentFlat(e), i++) {
      if (e === document.documentElement) break;
      var s = cs(e);
      if (s.display === 'none') return true;
      if (parseFloat(s.opacity) < 0.05) return true;
      if (s.contentVisibility === 'hidden') return true;
    }
    return false;
  }

  function hasPaint(s) {
    var bg = s.backgroundColor || '';
    var alpha = 1;
    if (bg === 'transparent') alpha = 0;
    var m = bg.match(/rgba?\(([^)]+)\)/);
    if (m) {
      var p = m[1].split(/[\s,\/]+/).filter(Boolean);
      alpha = p.length > 3 ? parseFloat(p[3]) : 1;
      if (p.length > 3 && /%$/.test(p[3])) alpha = parseFloat(p[3]) / 100;
    }
    if (alpha > 0.1) return true;
    if (s.backgroundImage && s.backgroundImage !== 'none') return true;
    if (s.boxShadow && s.boxShadow !== 'none') return true;
    if (parseFloat(s.borderTopWidth) > 0 && s.borderTopStyle !== 'none') return true;
    if (parseFloat(s.borderBottomWidth) > 0 && s.borderBottomStyle !== 'none') return true;
    return false;
  }

  // union of the painted rects inside el, clipped by overflow
  function contentBox(el) {
    var v = vp(), maxPaint = 0.6 * v.w * v.h, box = null, count = 0;
    function visit(e, clip) {
      if (++count > 5000) return;
      var s = cs(e);
      if (s.display === 'none' || s.contentVisibility === 'hidden') return;
      if (parseFloat(s.opacity) < 0.05) return;
      var r = rectOf(e);
      if (s.display !== 'contents' && s.visibility === 'visible' && r.w >= 1 && r.h >= 1) {
        var counts = CONTENT_TAGS.test(e.tagName) || ownText(e).length > 0 || (area(r) < maxPaint && hasPaint(s));
        if (counts) {
          var c = clip ? intersect(r, clip) : r;
          if (c && c.w >= 1 && c.h >= 1) box = union(box, c);
        }
      }
      var childClip = clip;
      if (s.display !== 'contents' && (s.overflowX !== 'visible' || s.overflowY !== 'visible') && r.w >= 1 && r.h >= 1) {
        childClip = clip ? intersect(clip, r) : r;
        if (!childClip) return;
      }
      var kids = e.children || [];
      for (var i = 0; i < kids.length; i++) visit(kids[i], childClip);
      if (e.shadowRoot) {
        var sk = e.shadowRoot.children;
        for (var j = 0; j < sk.length; j++) visit(sk[j], childClip);
      }
    }
    visit(el, null);
    return box;
  }

  function isControlLabel(e) {
    // also check aria-label and title
    var labels = [e.innerText, e.value, e.getAttribute('aria-label'), e.getAttribute('title')];
    for (var i = 0; i < labels.length; i++) {
      var label = norm(labels[i] || '');
      if (label.length >= 1 && label.length <= 60 && ACTION_RE.test(label)) return true;
    }
    return false;
  }

  function countButtons(el, realOnly) {
    var n = 0;
    walkDeep(el, function (e) {
      if (n >= 5) return false;
      var isBtn = e.matches && (e.matches(REAL_BUTTON_SEL) || (!realOnly && e.matches('a')));
      if (isBtn && isControlLabel(e) && isRenderedCheap(e)) { n++; return false; }
    }, 4000);
    return n;
  }

  function hasLandmarkInside(el) {
    return !!(el.querySelector && el.querySelector(LANDMARK_SEL));
  }

  function hasOutsideLandmark(p, inner) {
    if (!p.querySelectorAll) return false;
    var ls = p.querySelectorAll(LANDMARK_SEL);
    for (var i = 0; i < ls.length; i++) {
      if (!deepContains(inner, ls[i]) && !deepContains(ls[i], inner)) return true;
    }
    return false;
  }

  // longest cookie/consent text inside the anchor
  function findSeed(anchor) {
    var best = null, bestScore = 0;
    walkDeep(anchor, function (e) {
      var s = cs(e);
      if (s.display === 'none') return false;
      var t = ownText(e);
      if (t.length < 8 || !COOKIE_RE.test(t)) return;
      if (!isRenderedCheap(e)) return;
      var score = t.length + (COOKIE_WORD_RE.test(t) ? 100000 : 0);
      if (score > bestScore) { best = e; bestScore = score; }
    }, 6000);
    return best;
  }

  // smallest ancestor of seed that also holds a consent-like control
  function buttonAncestor(seed, realOnly) {
    var el = seed;
    for (var i = 0; i < 14 && el; i++) {
      if (el === document.body || el === document.documentElement) return null;
      if (i > 0 && hasLandmarkInside(el)) return null;
      if ((el.textContent || '').length > 30000) return null;
      if (deepText(el).length > 6000) return null;
      if (countButtons(el, realOnly) >= 1) return el;
      el = parentFlat(el);
    }
    return null;
  }

  // visible area of el and its painted children
  function visualBox(el) {
    var box = null, count = 0, view = viewRect();
    function visit(e) {
      if (++count > 3000) return;
      var s = cs(e);
      if (s.display === 'none' || s.contentVisibility === 'hidden' || parseFloat(s.opacity) < 0.05) return;
      var r = rectOf(e);
      if (s.display !== 'contents' && s.visibility === 'visible' && r.w >= 1 && r.h >= 1 &&
          (CONTENT_TAGS.test(e.tagName) || ownText(e).length > 0 || hasPaint(s))) {
        var c = intersect(r, view);
        if (c) box = union(box, c);
      }
      var kids = e.children || [];
      for (var i = 0; i < kids.length; i++) visit(kids[i]);
      if (e.shadowRoot) {
        var sk = e.shadowRoot.children;
        for (var j = 0; j < sk.length; j++) visit(sk[j]);
      }
    }
    visit(el);
    return box;
  }

  // grow the dialog up to the banner card
  function cardExpand(d) {
    var v = vp(), va = v.w * v.h;
    var ad = area(visualBox(d));
    for (var i = 0; i < 10; i++) {
      var p = parentFlat(d);
      if (!p || p === document.body || p === document.documentElement || p.nodeType !== 1) break;
      var ap = area(visualBox(p));
      if (ap > 0.6 * va && ad <= 0.6 * va) break;      // parent is a backdrop or page section
      if (ad > 0 && ap > 4 * ad + 4000) break;
      if (deepText(p).length - deepText(d).length > 150) break;
      if (hasOutsideLandmark(p, d)) break;
      d = p;
      ad = ap;
    }
    return d;
  }

  function extraControls(p, root) {
    var n = 0, list = p.querySelectorAll(CONTROL_SEL);
    for (var i = 0; i < list.length && i < 400; i++) {
      if (root.contains(list[i])) continue;
      if (!isRenderedCheap(list[i])) continue;
      if (++n > 2) break;
    }
    return n;
  }

  // the banner plus any text-free wrappers/backdrops around it (light DOM only)
  function expandRoot(top) {
    var root = top;
    for (var i = 0; i < 12; i++) {
      var p = root.parentElement;
      if (!p || p === document.body || p === document.documentElement) break;
      if (textLen(p) - textLen(root) > 40) break;
      if (hasOutsideLandmark(p, root)) break;
      if (extraControls(p, root) > 2) break;
      root = p;
    }
    return root;
  }

  // anchor is a page wrapper, not the banner
  function tooBigForBanner(anchor, dialog) {
    if (hasLandmarkInside(anchor)) return true;
    var at = deepText(anchor).length, dt = deepText(dialog).length;
    if (at > 8 * dt + 1000) return true;
    var v = vp();
    return area(visualBox(anchor)) > 0.9 * v.w * v.h && at > 3 * dt;
  }

  function locateDialog(anchor, kind) {
    var seed = findSeed(anchor);
    if (!seed) return {dialog: anchor, how: 'no_seed'};
    var b = buttonAncestor(seed, true), how = 'button';
    if (!b) { b = buttonAncestor(seed, false); how = 'link'; }
    if (!b) { b = seed; how = 'seed_only'; }
    var d = cardExpand(b);
    // keep the anchor unless it is a page wrapper
    if (kind === 'dom' && d !== anchor && deepContains(anchor, d) && !tooBigForBanner(anchor, d)) {
      return {dialog: cardExpand(anchor), how: how + '+anchor'};
    }
    return {dialog: d, how: how};
  }

  function positioning(el) {
    for (var e = el, i = 0; e && i < 200; e = parentFlat(e), i++) {
      if (e === document.documentElement) break;
      var p = cs(e).position;
      if (p === 'fixed') return 'fixed';
      if (p === 'sticky') return 'sticky';
    }
    // static wrapper with a fixed child counts as fixed
    var own = area(visualBox(el)), found = 'flow';
    walkDeep(el, function (e) {
      if (found !== 'flow') return false;
      var p = cs(e).position;
      if ((p === 'fixed' || p === 'sticky') && area(visualBox(e)) >= 0.5 * own) { found = p; return false; }
    }, 400);
    return found;
  }

  function frameOffset(f) {
    var r = f.getBoundingClientRect(), s = cs(f);
    return {
      x: r.left + f.clientLeft + (parseFloat(s.paddingLeft) || 0),
      y: r.top + f.clientTop + (parseFloat(s.paddingTop) || 0)
    };
  }

  function inRoot(el) {
    if (!el || !bp.root) return false;
    if (el === bp.anchor) return true;
    if (deepContains(bp.root, el)) return true;
    return !!(bp.layer && deepContains(bp.layer, el));
  }

  // fixed/sticky container that belongs to the banner
  function bannerLayer(d) {
    var base = deepText(d).length;
    for (var e = d, i = 0; e && i < 60; e = parentFlat(e), i++) {
      if (e === document.body || e === document.documentElement) return null;
      var p = cs(e).position;
      if (p !== 'fixed' && p !== 'sticky') continue;
      if (deepText(e).length > base + 300) return null;
      if (hasOutsideLandmark(e, d)) return null;
      return e;
    }
    return null;
  }

  function deepPoint(x, y) {
    var el = document.elementFromPoint(x, y);
    for (var i = 0; i < 10 && el && el.shadowRoot; i++) {
      var inner = el.shadowRoot.elementFromPoint(x, y);
      if (!inner || inner === el) break;
      el = inner;
    }
    return el;
  }

  function isInteractive(el) {
    if (!el || !el.closest) return true;
    if (el.closest(INTERACTIVE_SEL)) return true;
    var s = cs(el);
    if (s.cursor === 'pointer') return true;
    // an interactive element in an enclosing shadow host counts too
    var host = el.getRootNode && el.getRootNode().host;
    return host ? isInteractive(host) : false;
  }

  // real controls only
  var CONTROL_LIKE_SEL = 'a[href],button,input,select,textarea,label,summary,option,iframe,frame,video,' +
    '[role=button],[role=link],[role=checkbox],[role=radio],[role=switch],[role=tab],[role=menuitem],[onclick]';
  function isControl(el) {
    if (!el || !el.closest) return true;
    if (el.closest(CONTROL_LIKE_SEL)) return true;
    return cs(el).cursor === 'pointer';
  }

  function zIndexOf(el) {
    for (var e = el, i = 0; e && i < 50; e = parentFlat(e), i++) {
      var z = parseInt(cs(e).zIndex, 10);
      if (!isNaN(z)) return z;
    }
    return 0;
  }

  // elements under the point other than `layer` and its own ancestors/descendants
  function coversSomething(layer, x, y) {
    var stack = document.elementsFromPoint(x, y), seen = false;
    for (var i = 0; i < stack.length; i++) {
      var s = stack[i];
      if (s === layer) { seen = true; continue; }
      if (!seen) continue;
      if (s === document.body || s === document.documentElement) continue;
      if (s.contains(layer) || layer.contains(s)) continue;
      return true;
    }
    return false;
  }

  // large empty layer that catches clicks
  function isOverlay(el, x, y) {
    var body = document.body, bodyNone = body && cs(body).pointerEvents === 'none';
    for (var a = el, i = 0; a && a !== body && a !== document.documentElement && i < 60; a = parentFlat(a), i++) {
      var pos = cs(a).position;
      if (pos !== 'fixed' && pos !== 'absolute' && pos !== 'sticky') continue;
      if (coverFraction(rectOf(a)) < 0.5) continue;
      if (textLen(a) > 30 || a.querySelector(CONTROL_SEL)) return false;
      if (pos === 'absolute' && zIndexOf(a) < 1 && !coversSomething(a, x, y)) return false;
      return coversSomething(a, x, y) || zIndexOf(a) >= 1 || bodyNone;
    }
    return false;
  }

  // el can be inside a shadow root
  function classifyEl(el, x, y) {
    if (!el) return 'none';
    if (el === document.documentElement) return 'none';
    if (el === document.body) return 'bare';
    if (inRoot(el)) return 'banner';
    var top = topLight(el);
    if (top !== el && inRoot(top)) return 'banner';
    if (isOverlay(el, x, y)) return 'overlay';
    return 'content';
  }

  function classifyPoint(x, y, box) {
    var el = document.elementFromPoint(x, y);
    var deep = deepPoint(x, y) || el;
    var cls = classifyEl(deep, x, y);
    var p = {x: x, y: y, cls: cls, desc: describe(deep), safe: false, backdrop: false, frame: false, texty: false};
    if (box) {
      var dx = Math.max(box.x - x, 0, x - (box.x + box.w)), dy = Math.max(box.y - y, 0, y - (box.y + box.h));
      p.dist = Math.round(Math.sqrt(dx * dx + dy * dy));
    }
    if (!deep) return p;
    var interactive = isInteractive(deep);
    if (cls === 'content' || cls === 'bare') {
      p.safe = !interactive;
      p.texty = ownText(deep).length > 0;
      var a = deep.closest && deep.closest('a[href]');
      if (a && !inRoot(a)) {
        p.link = {href: a.href, target: a.target || '', text: norm(a.innerText).slice(0, 60),
                  download: a.hasAttribute('download')};
      }
    } else if (cls === 'banner') {
      if (deep === bp.anchor && (deep.tagName === 'IFRAME' || deep.tagName === 'FRAME')) {
        p.frame = true;   // checked inside the frame later
      } else if (!isControl(deep) && ownText(deep).length < 20 && coverFraction(rectOf(deep)) >= 0.5) {
        // banner backdrop
        p.backdrop = true;
      }
    } else if (cls === 'overlay') {
      p.backdrop = !isControl(deep);
    }
    return p;
  }

  // called from banner_probe.py

  bp.setAnchor = function (el, kind) {
    textCache = new Map();
    bp.anchor = el; bp.kind = kind; bp.scroller = null;
    var how = 'iframe';
    if (kind === 'iframe') {
      bp.dialog = el;
    } else {
      var loc = locateDialog(el, kind);
      bp.dialog = loc.dialog; how = loc.how;
    }
    bp.top = topLight(bp.dialog);
    bp.root = expandRoot(bp.top);
    bp.layer = kind === 'iframe' ? null : bannerLayer(bp.dialog);
    var shown = kind === 'iframe' ? [] : visibleWords(bp.dialog);
    bp.sig = kind === 'iframe' ? null : new Set(shown);
    textCache = null;
    try { bp.root.setAttribute('data-bp-root', '1'); bp.top.setAttribute('data-bp-top', '1'); } catch (e) {}
    var box = kind === 'iframe' ? rectOf(el) : contentBox(bp.dialog);
    return {
      how: how, anchor: describe(el), dialog: describe(bp.dialog), root: describe(bp.root),
      layer: bp.layer ? describe(bp.layer) : null,
      // text used by findBanner
      text: (shown.length ? shown.join(' ') : deepText(bp.dialog)).slice(0, 5000),
      box: box, positioning: positioning(bp.dialog)
    };
  };

  bp.frameOffsetOf = function (f) { return frameOffset(f); };

  // words shown inside d (skips opacity:0 text)
  function visibleWords(d) {
    var words = [];
    walkDeep(d, function (e) {
      var s = cs(e);
      if (s.display === 'none' || parseFloat(s.opacity) < 0.05) return false;
      var t = ownText(e);
      if (!t || s.visibility !== 'visible' || !e.getClientRects().length) return;
      var w = t.toLowerCase().match(WORD_RE) || [];
      for (var i = 0; i < w.length; i++) words.push(w[i]);
    }, 6000);
    return words;
  }

  // share of the banner words still shown
  function textCoverage(d) {
    if (!bp.sig || !bp.sig.size) return 1;
    var covered = new Set(visibleWords(d).filter(function (w) { return bp.sig.has(w); }));
    return covered.size / bp.sig.size;
  }

  bp.state = function () {
    var a = bp.anchor, d = bp.dialog;
    if (!a || !d) return {status: 'gone', why: 'no_anchor'};
    if (!a.isConnected || !d.isConnected) return {status: 'gone', why: 'detached'};
    if (ancestorHidden(d)) return {status: 'gone', why: 'hidden'};
    var box = bp.kind === 'iframe' ? rectOf(a) : contentBox(d);
    if (!box || area(box) < 100) return {status: 'gone', why: 'no_visible_content'};
    var coverage = textCoverage(d);
    if (coverage < 0.3) return {status: 'gone', why: 'text_gone', textCoverage: coverage};
    var v = vp(), inter = intersect(box, viewRect());
    var vis = inter ? area(inter) / area(box) : 0;
    // visible: >2% of the box or >=15000 px2 on screen
    var onScreen = inter ? area(inter) : 0;
    var out = {status: (vis > 0.02 || onScreen >= 15000) ? 'visible' : 'offscreen', box: box, vis: vis, vw: v.w, vh: v.h};
    if (bp.kind === 'iframe') out.frame = frameOffset(a);
    return out;
  };

  bp.hitGrid = function (box, cols, rows, margin) {
    textCache = new Map();
    var v = vp(), pts = [], counts = {};
    for (var j = 0; j < rows; j++) {
      for (var i = 0; i < cols; i++) {
        var x = Math.round((i + 0.5) * v.w / cols), y = Math.round((j + 0.5) * v.h / rows);
        if (box && x >= box.x - margin && x <= box.x + box.w + margin &&
            y >= box.y - margin && y <= box.y + box.h + margin) continue;
        var p = classifyPoint(x, y, box);
        counts[p.cls] = (counts[p.cls] || 0) + 1;
        pts.push(p);
      }
    }
    textCache = null;
    return {vw: v.w, vh: v.h, n: pts.length, counts: counts, points: pts};
  };

  // visible page links outside the banner, each with a point where the hit test lands on the link itself
  bp.linkPoints = function (box, margin) {
    textCache = new Map();
    var v = vp(), out = [], links = document.querySelectorAll('a[href]');
    for (var i = 0; i < links.length && out.length < 80; i++) {
      var a = links[i];
      if (inRoot(a)) continue;
      var rects = a.getClientRects();
      if (!rects.length) continue;
      var r = rects[0];
      if (r.width < 4 || r.height < 4) continue;
      var x = Math.round(r.left + Math.min(r.width / 2, 20)), y = Math.round(r.top + r.height / 2);
      if (x < 2 || y < 2 || x > v.w - 2 || y > v.h - 2) continue;
      if (box && x >= box.x - margin && x <= box.x + box.w + margin &&
          y >= box.y - margin && y <= box.y + box.h + margin) continue;
      var el = deepPoint(x, y);
      if (!el || !(el === a || a.contains(el))) continue;      // link is covered
      var dx = box ? Math.max(box.x - x, 0, x - (box.x + box.w)) : 0, dy = box ? Math.max(box.y - y, 0, y - (box.y + box.h)) : 0;
      out.push({x: x, y: y, cls: 'content', desc: describe(el), dist: Math.round(Math.sqrt(dx * dx + dy * dy)),
                link: {href: a.href, target: a.target || '', text: norm(a.innerText).slice(0, 60),
                       download: a.hasAttribute('download')}});
    }
    textCache = null;
    return out;
  };

  // find the banner again by its words (40% of them)
  var WORD_RE = /[\p{L}\p{N}]{3,}/gu;
  bp.findBanner = function (signature, needOnScreen) {
    var sig = new Set((String(signature || '').toLowerCase().match(WORD_RE) || []));
    if (!sig.size) return {found: false, coverage: 0};
    var view = viewRect(), cands = [], covered = new Set();
    walkDeep(document.documentElement, function (e) {
      var tag = e.tagName;
      if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT' || tag === 'TEMPLATE') return false;
      var t = ownText(e);
      if (t.length < 15) return;
      var words = t.toLowerCase().match(WORD_RE) || [];
      if (words.length < 3) return;
      var hit = 0;
      for (var i = 0; i < words.length; i++) if (sig.has(words[i])) hit++;
      if (hit / words.length < 0.7) return;
      if (!isRenderedCheap(e) || ancestorHidden(e)) return;
      if (needOnScreen && !intersect(rectOf(e), view)) return;
      cands.push({el: e, hit: hit});
      for (var j = 0; j < words.length; j++) if (sig.has(words[j])) covered.add(words[j]);
    }, 40000);
    if (!cands.length) return {found: false, coverage: 0};
    cands.sort(function (a, b) { return b.hit - a.hit; });
    var best = cands[0].el, host = topLight(best);
    var coverage = covered.size / sig.size;
    return {found: coverage >= 0.4, coverage: Math.round(coverage * 100) / 100, el: best,
            host: host !== best ? host : null, desc: describe(best)};
  };

  // used inside a banner iframe to check a candidate grey-area point
  bp.pointInfo = function (x, y) {
    var el = deepPoint(x, y);
    if (!el) return {none: true};
    return {inDialog: deepContains(bp.dialog, el) && coverFraction(rectOf(el)) < 0.5, interactive: isControl(el),
            ownText: ownText(el).length, desc: describe(el)};
  };

  bp.recStart = function () {
    var rec = window.__bpRec;
    if (!rec) {
      rec = window.__bpRec = {events: []};
      var handler = function (e) {
        var t = (e.composedPath && e.composedPath()[0]) || e.target;
        if (t && t.nodeType !== 1) t = t.parentElement || document.documentElement;
        var info = {type: e.type, x: e.clientX, y: e.clientY, trusted: e.isTrusted, desc: describe(t), cls: 'unknown'};
        try { info.cls = window.__bp.classifyTarget(t, e.clientX, e.clientY); } catch (err) {}
        rec.events.push(info);
        setTimeout(function () { info.prevented = e.defaultPrevented; }, 0);
      };
      ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(function (type) {
        window.addEventListener(type, handler, true);
      });
    }
    rec.events = [];
    return true;
  };

  bp.recEvents = function () { return window.__bpRec ? window.__bpRec.events : null; };

  bp.classifyTarget = function (t, x, y) {
    textCache = new Map();
    try { return classifyEl(t, x, y); } finally { textCache = null; }
  };

  bp.focusInfo = function () {
    var top = document.activeElement, a = top;
    for (var i = 0; i < 10 && a && a.shadowRoot && a.shadowRoot.activeElement; i++) a = a.shadowRoot.activeElement;
    if (!top || top === document.body || top === document.documentElement) return {none: true};
    var inside = inRoot(a) || inRoot(top);
    var r = a.getBoundingClientRect();
    var label = norm(a.innerText || a.value || (a.getAttribute && (a.getAttribute('aria-label') || a.getAttribute('href'))) || '');
    return {none: false, inRoot: !!inside, tag: a.tagName.toLowerCase(), desc: describe(a), label: label.slice(0, 60),
            visible: r.width > 0 && r.height > 0 && !ancestorHidden(a),
            frame: top.tagName === 'IFRAME' || top.tagName === 'FRAME'};
  };

  bp.blurActive = function () {
    var a = document.activeElement;
    if (a && a !== document.body && a.blur) a.blur();
    return true;
  };

  // clear focus so tab starts from the top
  bp.resetFocusStart = function () {
    bp.blurActive();
    try {
      var sel = window.getSelection();
      if (sel && document.body) sel.collapse(document.body, 0);
    } catch (e) {}
    return true;
  };

  function findScroller(el) {
    for (var e = el, i = 0; e && e !== document.documentElement && i < 200; e = parentFlat(e), i++) {
      if (inRoot(e)) return null;          // over the banner
      var s = cs(e);
      if (/(auto|scroll|overlay)/.test(s.overflowY) && e.scrollHeight > e.clientHeight + 4) return e;
    }
    return null;
  }

  // remember the scroll container under the point
  bp.pinScroller = function (x, y) {
    bp.scroller = findScroller(deepPoint(x, y));
    return bp.scroller ? describe(bp.scroller) : null;
  };

  bp.scrollState = function (x, y) {
    var se = document.scrollingElement || document.documentElement;
    var out = {win: {top: se.scrollTop, max: se.scrollHeight - se.clientHeight}};
    var s = (bp.scroller && bp.scroller.isConnected) ? bp.scroller : findScroller(deepPoint(x, y));
    if (s && s !== se) out.inner = {top: s.scrollTop, max: s.scrollHeight - s.clientHeight, desc: describe(s)};
    return out;
  };

  bp.restoreTop = function () {
    var se = document.scrollingElement || document.documentElement;
    se.scrollTop = 0;
    window.scrollTo(0, 0);
    if (bp.scroller && bp.scroller.isConnected) bp.scroller.scrollTop = 0;
    return true;
  };

  bp.passive = function () {
    var html = document.documentElement, body = document.body;
    var hs = cs(html), bs = body ? cs(body) : null;
    var lock = /hidden|clip/.test(hs.overflowY) || /hidden|clip/.test(hs.overflow) ||
      !!(bs && (/hidden|clip/.test(bs.overflowY) || bs.position === 'fixed'));
    var modal = false;
    try { modal = !!document.querySelector('dialog:modal'); } catch (e) {}
    var ariaModal = false;
    try { ariaModal = !!(bp.root && (bp.root.closest('[aria-modal="true"]') || bp.root.querySelector('[aria-modal="true"]'))); } catch (e) {}
    var inert = 0;
    try {
      var list = document.querySelectorAll('[inert]');
      for (var i = 0; i < list.length; i++) {
        if (!inRoot(list[i]) && coverFraction(rectOf(list[i])) > 0.3) inert++;
      }
    } catch (e) {}
    // content with pointer-events:none
    var big = 0, none = 0;
    if (body) {
      for (var k = 0; k < body.children.length; k++) {
        var c = body.children[k];
        if (inRoot(c) || coverFraction(rectOf(c)) < 0.1) continue;
        big++;
        if (cs(c).pointerEvents === 'none') none++;
      }
    }
    var se = document.scrollingElement || html, v = vp();
    return {
      scrollLock: lock, htmlOverflow: hs.overflowY, bodyOverflow: bs ? bs.overflowY : null,
      bodyPosition: bs ? bs.position : null, bodyPointerNone: !!(bs && bs.pointerEvents === 'none'),
      contentPointerNone: big > 0 && none === big,
      docScrollMax: se.scrollHeight - se.clientHeight, modalDialog: modal, ariaModal: ariaModal,
      inertOutside: inert, positioning: positioning(bp.kind === 'iframe' ? bp.anchor : bp.dialog),
      dpr: window.devicePixelRatio, vw: v.w, vh: v.h, innerW: window.innerWidth, innerH: window.innerHeight,
      visibility: document.visibilityState
    };
  };

  bp.pageInfo = function () {
    var body = document.body;
    return {
      title: document.title || '', readyState: document.readyState, url: location.href,
      text: body ? norm(body.innerText).slice(0, 6000) : '', textLength: body ? norm(body.innerText).length : 0,
      images: document.images ? document.images.length : 0
    };
  };

  window.__bp = bp;
})();
