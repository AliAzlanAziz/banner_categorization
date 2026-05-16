import pandas as pd
from pathlib import Path
import os

COMPLETE_RUN = True     # perform the run for two stateless and stateful phase

INTRACTABLE = True

HEADLESS = False
SLEEP_AFTER_INTERACTION = False         # enable to initiate the sleep after interaction (not after loading the page)
WAITANYWAY = True
# Translate the page using "Google Translate"; Turned off since Google detect the tool as bot
JS_RUN = False
TRANSLATION = False
BANNERCLICK = True
DNSMPI_DETECTION = False
SCREENSHOT = True      # take screenshot
NOBANNER_SC = True      # store screenshot of websites with no banner in another folder
SAVE_HTML = True       # save HTML of the banner in "htmls" table
SAVE_BODY = True       # save HTML of the body in "visits" table
# using chrome as the browser, available just for Banner Detection module (Not for OpenWPM)
CHROME = True         # use Chrome browser; this was for partitioned cookies measurement
WATCHDOG = True
EXTRACT_JSON = True     # Get CMPs list from URL rather than scraping IAB.eu
# enabling searching for works inside the HTML also, for example search for 'accept' in the class names of a element
NON_EXPLICIT = True

SIMPLE_DETECTION = True     # enabling direct rejection for reject
NC_ADDON = True        # enabling using neverconsent addon for rejection
REJ_IN_SET = True       # enabling try to reject by searching in setting
MODIFIED_ADDON = True       # using modified neverconsent addon
MOBILE_AGENT = False        # change the useragent to mobile
GPC_SIGNAL = False             # enabling GPC signal
HTTP_INSTRUMENT = False      # enabling recording HTTP requests and responses
JS_INSTRUMENT = False       # enabling recording JS events
COOKIE_INSTRUMENT = False    # enabling recording cookies
NAV_INSTRUMENT = False      # enabling recording navigation events
DNS_INSTRUMENT = False      # enabling recording navigation events

START_POINT = 0                      # the index of the first website to start from in the target list
STEP_SIZE = 400                      # the number of websites to crawl started from the start point
URL_MODE = 1     # prepending: 1. https, 2. http
NUM_BROWSERS = 1               # number of browsers to run in parallel
SLEEP_TIME = 60         # the amount of time waits after loading the website
TEST_MODE_SLEEP = 0      # used for debugging
ATTEMPTS = 1       # number of new try for finding banner
ATTEMPT_STEP_SLEEP_TIME = 3      # time to wait before trying again
CHOICE = 0     # interact_mode: 0. no interaction, 1. accept, 2. reject

# urls_file = "blocking_banner.csv"
# urls_file = "blocking_banner_with_option_to_close.csv"
# urls_file = "static_non_blocking_banner_stays_until_action.csv"
# urls_file = "floating_non_blocking_banner_stays_until_action_close_option_given.csv"
urls_file = "floating_non_blocking_banner_stays_until_action.csv"
# urls_file = "undetected_banners.csv"
# urls_file = "simple_non_blocking_banner.csv"
# urls_file = "banners_sorted_exist.csv"
# urls_file = "testing.csv"
# urls_file = "testing_all_floating.csv"
# urls_file = "no_banner.csv"
# urls_file = "retest_wrong.csv"

run_name = "test-artifact"

# directories path
season_dir = "./" + urls_file.split(".")[0] + "-datadir/" + run_name + "/" # ./datadir/test-artifact/
data_dir = season_dir + "1-Starting_Point_" + str(START_POINT) # ./datadir/test-artifact/1-Starting_Point_0/
sc_dir = data_dir + "/banner_screenshots/" # ./datadir/test-artifact/1-Starting_Point_0/banner_screenshots/
nobanner_sc_dir = sc_dir + "nobanner/" # ./datadir/test-artifact/1-Starting_Point_0/banner_screenshots/nobanner/

log_file = data_dir + '/logs.txt' # ./datadir/test-artifact/1-Starting_Point_0/logs.txt

# initial values
counter = 0
driver = None
domains = []
this_index = None
this_domain = ""
this_url = None
this_run_url = None
this_status = 0  # -1: error, 0: loaded, 1: time out, 2: unreachable, 3: translated
this_lang = None
this_banner_lang = None
this_start_time = None
num_banners = None
file = None


# Schema of the tables used in BannerClick
visit_db = pd.DataFrame({
    'visit_id': pd.Series([], dtype='int'),
    'domain': pd.Series([], dtype='str'),
    'url': pd.Series([], dtype='str'),
    'run_url': pd.Series([], dtype='str'),
    'status': pd.Series([], dtype='int'),
    'lang': pd.Series([], dtype='str'),
    'banners': pd.Series([], dtype='int'),
    'btn_status': pd.Series([], dtype='int'),
    'btn_set_status': pd.Series([], dtype='int'),
    'interact_time': pd.Series([], dtype='int'),
    'ttw': pd.Series([], dtype='int'),
    '__cmp': pd.Series([], dtype='bool'),
    '__tcfapi': pd.Series([], dtype='bool'),
    '__tcfapiLocator': pd.Series([], dtype='bool'),
    'cmp_id': pd.Series([], dtype='int'),
    'cmp_name': pd.Series([], dtype='str'),
    'pv': pd.Series([], dtype='bool'),
    'nc_cmp_name': pd.Series([], dtype='str'),
    'dnsmpi': pd.Series([], dtype='str'),
    'body_html': pd.Series([], dtype='str'),
})
banner_db = pd.DataFrame({
    'banner_id': pd.Series([], dtype='int'),
    'visit_id': pd.Series([], dtype='int'),
    'domain': pd.Series([], dtype='str'),
    'lang': pd.Series([], dtype='str'),
    'iFrame': pd.Series([], dtype='bool'),
    'shadow_dom': pd.Series([], dtype='bool'),
    'captured_area': pd.Series([], dtype='float'),
    'x': pd.Series([], dtype='int'),
    'y': pd.Series([], dtype='int'),
    'w': pd.Series([], dtype='int'),
    'h': pd.Series([], dtype='int'),
})
html_db = pd.DataFrame({
    'banner_id': pd.Series([], dtype='int'),
    'visit_id': pd.Series([], dtype='int'),
    'domain': pd.Series([], dtype='str'),
    'html': pd.Series([], dtype='str'),
})


# demo.py
HOME_DIR = os.environ.get("HOME")
SAVE_LAST = True
SAVE_PROFILE = True
SAVE_PROFILE_STEP = 50
LOAD_PROFILE_START = False
PROFILE_DUMP_URL_START = r'Profile-Dump-'
PROFILE_COMPRESS = False
PROFILE_EXTENSION = r'.tar.gz' if PROFILE_COMPRESS else r'.tar'
DEFAULT_PROFILE_PATH = False  # use default directory for profile

# path to the profile file
STATE_RUN_PATH = Path("./statefiles/") / run_name # ./statefiles/test-artifact/
PROFILE_NAME = "cookiejar.tar" # the name of the profile file, for example "cookiejar.tar"
DB_PATH = Path(data_dir + "/crawl-data.sqlite") # "./datadir/test-artifact/1-Starting_Point_0/crawl-data.sqlite"
# path to the initial db file
BC_TEMP_DIR = f'{HOME_DIR}/tmp/' # the directory to store the temporary profile and database files, for example "/home/$user/tmp/"
PROFILES_PATH = Path(data_dir + "/profiles") # "./datadir/test-artifact/1-Starting_Point_0/profiles/"
DBBACKUP_PATH = Path(data_dir + "/DBBackup") # "./datadir/test-artifact/1-Starting_Point_0/DBBackup/"
DB_NAME = "cookiejar" # the name of the database file
TASK_COUNT_SLEEP = True  # sleep if more than 200 tasks
TASK_COUNT_MAX = 200

BLOCKING = True  # thread block synchronization
# 10_000_000 & 20_000_000 offset for reject and index, banner categorization run
USE_OFFSET = False

RUN_TYPE = 'LOCAL'
RUN_TYPES = {
    'LOCAL': 8_000,
    'MULTI_RUN': 3_500,
    'RK_RUN': 20_000,
    'SINGLE_RUN': 13_000,
    'DEFAULT': 2_500,
}
BROWSER_MEMORY_LIMIT = RUN_TYPES.get(RUN_TYPE, 2_500)  # in MB

DUMP_PROFILE_SLEEP_TIME = 60 * 5
REPETETIVE_FAILURE_LIMIT = 10
USERLIKE_PASSED_WEBSITES = -1

SPAWN_TIMEOUT = 60 * 20
SPAWN_TIMEOUT_INCREASE = 60 * 5
UNSUCCESSFUL_SPAWN_LIMIT = 5

TERMINATION_SLEEP_TIME = 1 # 60 * 2

# for blocking-vs-non-blocking thesis
language_paths = {
    # ISO 639-1 two-letter codes
    "aa", "ab", "ae", "af", "ak", "am", "an", "ar", "as", "av", "ay", "az",
    "ba", "be", "bg", "bh", "bi", "bm", "bn", "bo", "br", "bs", "ca", "ce",
    "ch", "co", "cr", "cs", "cu", "cv", "cy", "da", "de", "dv", "dz", "ee",
    "el", "en", "eo", "es", "et", "eu", "fa", "ff", "fi", "fj", "fo", "fr",
    "fy", "ga", "gd", "gl", "gn", "gu", "gv", "ha", "he", "hi", "ho", "hr",
    "ht", "hu", "hy", "hz", "ia", "id", "ie", "ig", "ii", "ik", "io", "is",
    "it", "iu", "ja", "jv", "ka", "kg", "ki", "kj", "kk", "kl", "km", "kn",
    "ko", "kr", "ks", "ku", "kv", "kw", "ky", "la", "lb", "lg", "li", "ln",
    "lo", "lt", "lu", "lv", "mg", "mh", "mi", "mk", "ml", "mn", "mr", "ms",
    "mt", "my", "na", "nb", "nd", "ne", "ng", "nl", "nn", "no", "nr", "nv",
    "ny", "oc", "oj", "om", "or", "os", "pa", "pi", "pl", "ps", "pt", "qu",
    "rm", "rn", "ro", "ru", "rw", "sa", "sc", "sd", "se", "sg", "si", "sk",
    "sl", "sm", "sn", "so", "sq", "sr", "ss", "st", "su", "sv", "sw", "ta",
    "te", "tg", "th", "ti", "tk", "tl", "tn", "to", "tr", "ts", "tt", "tw",
    "ty", "ug", "uk", "ur", "uz", "ve", "vi", "vo", "wa", "wo", "xh", "yi",
    "yo", "za", "zh", "zu",

    # ISO 639-2 / ISO 639-3 three-letter codes (partial, common)
    "aar", "abk", "ave", "afr", "aka", "amh", "ara", "arg", "arm", "asm", "ava",
    "ave", "aym", "aze", "bak", "bel", "bul", "bih", "bis", "bam", "ben", "bod",
    "bre", "bos", "cat", "che", "cha", "cos", "cre", "ces", "chu", "chv", "cym",
    "dan", "deu", "div", "dzo", "ewe", "ell", "eng", "epo", "spa", "est", "eus",
    "fas", "ful", "fin", "fij", "fao", "fra", "fry", "gle", "gla", "glg", "grn",
    "guj", "glv", "hau", "heb", "hin", "hmo", "hrv", "hat", "hun", "hye", "her",
    "ina", "ind", "ile", "ibo", "iii", "ipk", "ido", "isl", "ita", "iku", "jpn",
    "jav", "kat", "kon", "kik", "kua", "kaz", "kal", "khm", "kan", "kor", "kau",
    "kas", "kur", "kom", "cor", "kir", "lat", "ltz", "lug", "lim", "lin", "lao",
    "lit", "lub", "lav", "mlg", "mah", "mri", "mkd", "mal", "mon", "mar", "msa",
    "mlt", "mya", "nau", "nob", "nde", "nep", "ndo", "nld", "nno", "nor", "nbl",
    "nav", "nya", "oci", "oji", "orm", "ori", "oss", "pan", "pli", "pol", "pus",
    "por", "que", "roh", "run", "ron", "rus", "kin", "san", "srd", "snd", "sme",
    "sag", "sin", "slk", "slv", "smo", "sna", "som", "alb", "srp", "ssw", "sot",
    "sun", "swe", "swa", "tam", "tel", "tgk", "tha", "tir", "tuk", "tgl", "tsn",
    "ton", "tur", "tso", "tat", "twi", "tah", "uig", "ukr", "urd", "uzb", "ven",
    "vie", "vol", "wln", "wol", "xho", "yid", "yor", "zha", "zho", "zul"
}


forbidden_paths = {
    "about", "privacy", "cookie", "consent", "terms", "policy", "optin", "optout", "opt-in", "opt-out", "tos", "statement",
    "notice", "third-party", "thirdparty", "third_party", "cookies", "consents", "term", "policies", "statements",
    "notices", "thirdparties", "third_parties", "third-parties", "partner", "vendor", "preference", "partners",
    "vendors", "preferences", "data_protection", "data-protection", "learn_more", "learnmore", "learn-more", 
    "more_info", "moreinfo", "more-info", "manage_settings", "manage-settings", "manage", "settings", "setting",
    "manage", "imprint", "login", "signin", "sign-in", "log-in", "register", "signup", "sign-up", "create-account", 
    "account", "sign_in", "sign_up", "create_account", "myaccount", "my_account", "my-account", "createaccount", "log_in",
    "register-account", "register_account", "cookiemanagement", "cookie_management", "cookie-management", "more_info", "moreinfo",
    "legal", "compliance", "support",
    "Datenschutz", "Cookie", "Einwilligung", "Bedingungen", "Richtlinie", "Optin", "Optout", "Opt-In", "Opt-Out", "Tos", "Erklärung", 
    "Hinweis", "Drittanbieter", "Drittanbieter", "Drittanbieter", "Cookies", "Einwilligungen", "Begriff", "Richtlinien", "Erklärungen", 
    "notices", "thirdparties", "third_parties", "third-partys", "partner", "vendor", "preference", "partners", 
    "vendors", "preferences", "data_protection", "data-protection", "learn_more", "learnmore", "learn-more", 
    "more_info", "moreinfo", "more-info", "manage_settings", "manage-settings", "manage", "settings", "setting", 
    "verwalten", "Impressum", "Anmelden", "Anmelden", "Anmelden", "Anmelden", "Registrieren", "Anmelden", "Anmelden", "Konto erstellen", 
    "account", "sign_in", "sign_up", "create_account", "myaccount", "my_account", "my-account", "createaccount", "log_in", 
    "register-account", "register_account", "cookiemanagement", "cookie_management", "cookie-management", "more_info", "moreinfo", 
    "Recht", "Compliance", "Unterstützung",
    "privacidad", "cookie", "consentimiento", "términos", "política", "optar", "optar por no participar", "optar por participar", "optar por no participar", "tos", "declaración", 
    "aviso", "tercero", "tercero", "tercero_partido", "cookies", "consentimientos", "término", "políticas", "declaraciones", 
    "avisos", "terceros", "terceros", "terceros", "socio", "proveedor", "preferencia", "socios", 
    "proveedores", "preferencias", "protección_datos", "protección-datos", "aprender_más", "aprender más", "aprender-más", 
    "more_info", "moreinfo", "more-info", "manage_settings", "administrar-configuraciones", "administrar", "configuraciones", "configuración", 
    "administrar", "imprimir", "iniciar sesión", "iniciar sesión", "iniciar sesión", "iniciar sesión", "registrarse", "registrarse", "registrarse", "crear cuenta", 
    "cuenta", "iniciar sesión", "registrarse", "crear cuenta", "mi cuenta", "mi_cuenta", "mi-cuenta", "crear cuenta", "iniciar sesión", 
    "cuenta-registro", "cuenta_registro", "administración de cookies", "administración_de cookies", "administración de cookies", "más_información", "más información", 
    "legal", "cumplimiento", "soporte",
    "privacy", "cookie", "consenso", "termini", "policy", "optin", "optout", "opt-in", "opt-out", "tos", "informativa", 
    "informativa", "terza parte", "terza parte", "terza_parte", "cookie", "consensi", "termine", "politiche", "dichiarazioni", 
    "informazioni", "terze parti", "terze_parti", "terze parti", "partner", "venditore", "preferenza", "partner", 
    "vendor", "preferences", "data_protection", "data-protection", "learn_more", "learnmore", "learn-more", 
    "more_info", "moreinfo", "more-info", "manage_settings", "gestisci-impostazioni", "gestisci", "impostazioni", "impostazione", 
    "gestisci", "imprint", "login", "signin", "sign-in", "log-in", "registrati", "registrati", "registrati", "crea-account", 
    "account", "sign_in", "sign_up", "create_account", "myaccount", "my_account", "my-account", "createaccount", "log_in", 
    "register-account", "register_account", "cookiemanagement", "cookie_management", "cookie-management", "more_info", "moreinfo", 
    "legale", "conformità", "supporto",
    "privacidade", "cookie", "consentimento", "termos", "política", "optin", "optout", "opt-in", "opt-out", "tos", "declaração", 
    "aviso", "terceiro", "terceiro", "terceiro_parte", "cookies", "consentimentos", "termo", "políticas", "declarações", 
    "avisos", "terceiros", "terceiros_partes", "terceiros", "parceiro", "fornecedor", "preferência", "parceiros", 
    "fornecedores", "preferências", "proteção de dados", "proteção de dados", "learn_more", "learnmore", "learn-more", 
    "more_info", "moreinfo", "mais informações", "manage_settings", "gerenciar configurações", "gerenciar", "configurações", "configuração", 
    "gerenciar", "imprimir", "login", "login", "login", "login", "registrar", "inscrever-se", "inscrever-se", "criar conta", 
    "conta", "sign_in", "sign_up", "create_account", "myaccount", "my_account", "my-account", "createaccount", "log_in", 
    "register-account", "register_account", "cookiemanagement", "cookie_management", "cookie-management", "more_info", "moreinfo", 
    "legal", "conformidade", "suporte",
    # chineese
    "privacy", "隐私", "cookie", "Cookie", "consent", "同意", "terms", "条款", "policy", "政策", "optin", "选择加入", "optout", "选择退出", "opt-in", "选择加入", "opt-out", "选择退出", "tos", "服务条款", "statement", "声明", "notice", "通知", "third-party", "第三方", "thirdparty", "第三方", "third_party", "第三方", "cookies", "Cookies", "consents", "同意", "term", "条款", "policies", "政策", "statements", "声明", "notices", "通知", "thirdparties", "第三方", "third_parties", "第三方", "third-parties", "第三方", "partner", "合作伙伴", "vendor", "供应商", "preference", "偏好", "partners", "合作伙伴", "vendors", "供应商", "preferences", "偏好设置", "data_protection", "数据保护", "data-protection", "数据保护", "learn_more", "了解更多", "learnmore", "了解更多", "learn-more", "了解更多", "more_info", "更多信息", "moreinfo", "更多信息", "more-info", "更多信息", "manage_settings", "管理设置", "manage-settings", "管理设置", "manage", "管理", "settings", "设置", "setting", "设置", "manage", "管理", "imprint", "法律声明", "login", "登录", "signin", "登录", "sign-in", "登录", "log-in", "登录", "register", "注册", "signup", "注册", "sign-up", "注册", "create-account", "创建账户", "account", "账户", "sign_in", "登录", "sign_up", "注册", "create_account", "创建账户", "myaccount", "我的账户", "my_account", "我的账户", "my-account", "我的账户", "createaccount", "创建账户", "log_in", "登录", "register-account", "注册账户", "register_account", "注册账户", "cookiemanagement", "Cookie管理", "cookie_management", "Cookie管理", "cookie-management", "Cookie管理", "more_info", "更多信息", "moreinfo", "更多信息", "legal", "法律信息", "compliance", "合规", "support", "支持",
    # russian
    "privacy", "конфиденциальность", "рекомендательные технологии", "cookie", "cookie", "consent", "согласие", "terms", "условия", "policy", "политика", "optin", "согласие", "optout", "отказ", "opt-in", "включение", "opt-out", "отключение", "tos", "условия использования", "statement", "заявление", "notice", "уведомление", "third-party", "третья сторона", "thirdparty", "третья сторона", "third_party", "третья сторона", "cookies", "cookie", "consents", "согласия", "term", "условие", "policies", "политики", "statements", "заявления", "notices", "уведомления", "thirdparties", "третьи стороны", "third_parties", "третьи стороны", "third-parties", "третьи стороны", "partner", "партнёр", "vendor", "поставщик", "preference", "предпочтение", "partners", "партнёры", "vendors", "поставщики", "preferences", "настройки предпочтений", "data_protection", "защита данных", "data-protection", "защита данных", "learn_more", "узнать больше", "learnmore", "узнать больше", "learn-more", "узнать больше", "more_info", "дополнительная информация", "moreinfo", "дополнительная информация", "more-info", "дополнительная информация", "manage_settings", "управление настройками", "manage-settings", "управление настройками", "manage", "управлять", "settings", "настройки", "setting", "настройка", "manage", "управлять", "imprint", "правовая информация", "login", "вход", "signin", "вход", "sign-in", "вход", "log-in", "вход", "register", "регистрация", "signup", "регистрация", "sign-up", "регистрация", "create-account", "создать аккаунт", "account", "учётная запись", "sign_in", "вход", "sign_up", "регистрация", "create_account", "создать аккаунт", "myaccount", "мой аккаунт", "my_account", "мой аккаунт", "my-account", "мой аккаунт", "createaccount", "создать аккаунт", "log_in", "вход", "register-account", "регистрация аккаунта", "register_account", "регистрация аккаунта", "cookiemanagement", "управление cookie", "cookie_management", "управление cookie", "cookie-management", "управление cookie", "more_info", "дополнительная информация", "moreinfo", "дополнительная информация", "legal", "правовая информация", "compliance", "соответствие", "support", "поддержка",
    # japan
    "privacy", "プライバシー", "cookie", "クッキー", "consent", "同意", "terms", "利用規約", "policy", "ポリシー", "optin", "オプトイン", "optout", "オプトアウト", "opt-in", "オプトイン", "opt-out", "オプトアウト", "tos", "利用規約", "statement", "声明", "notice", "通知", "third-party", "第三者", "thirdparty", "第三者", "third_party", "第三者", "cookies", "クッキー", "consents", "同意", "term", "規約", "policies", "ポリシー", "statements", "声明", "notices", "通知", "thirdparties", "第三者", "third_parties", "第三者", "third-parties", "第三者", "partner", "パートナー", "vendor", "ベンダー", "preference", "設定", "partners", "パートナー", "vendors", "ベンダー", "preferences", "設定", "data_protection", "データ保護", "data-protection", "データ保護", "learn_more", "詳細はこちら", "learnmore", "詳細はこちら", "learn-more", "詳細はこちら", "more_info", "詳細情報", "moreinfo", "詳細情報", "more-info", "詳細情報", "manage_settings", "設定管理", "manage-settings", "設定管理", "manage", "管理", "settings", "設定", "setting", "設定", "manage", "管理", "imprint", "特定商取引法に基づく表記", "login", "ログイン", "signin", "ログイン", "sign-in", "ログイン", "log-in", "ログイン", "register", "登録", "signup", "登録", "sign-up", "登録", "create-account", "アカウント作成", "account", "アカウント", "sign_in", "ログイン", "sign_up", "登録", "create_account", "アカウント作成", "myaccount", "マイアカウント", "my_account", "マイアカウント", "my-account", "マイアカウント", "createaccount", "アカウント作成", "log_in", "ログイン", "register-account", "アカウント登録", "register_account", "アカウント登録", "cookiemanagement", "クッキー管理", "cookie_management", "クッキー管理", "cookie-management", "クッキー管理", "more_info", "詳細情報", "moreinfo", "詳細情報", "legal", "法的情報", "compliance", "コンプライアンス", "support", "サポート",
    # french
    "privacy", "confidentialité", "cookie", "cookie", "consent", "consentement", "terms", "conditions", "policy", "politique", "optin", "adhésion", "optout", "désinscription", "opt-in", "adhésion", "opt-out", "désinscription", "tos", "conditions d’utilisation", "statement", "déclaration", "notice", "avis", "third-party", "tiers", "thirdparty", "tiers", "third_party", "tiers", "cookies", "cookies", "consents", "consentements", "term", "terme", "policies", "politiques", "statements", "déclarations", "notices", "avis", "thirdparties", "tiers", "third_parties", "tiers", "third-parties", "tiers", "partner", "partenaire", "vendor", "fournisseur", "preference", "préférence", "partners", "partenaires", "vendors", "fournisseurs", "preferences", "préférences", "data_protection", "protection des données", "data-protection", "protection des données", "learn_more", "en savoir plus", "learnmore", "en savoir plus", "learn-more", "en savoir plus", "more_info", "plus d’informations", "moreinfo", "plus d’informations", "more-info", "plus d’informations", "manage_settings", "gérer les paramètres", "manage-settings", "gérer les paramètres", "manage", "gérer", "settings", "paramètres", "setting", "paramètre", "manage", "gérer", "imprint", "mentions légales", "login", "connexion", "signin", "connexion", "sign-in", "connexion", "log-in", "connexion", "register", "inscription", "signup", "inscription", "sign-up", "inscription", "create-account", "créer un compte", "account", "compte", "sign_in", "connexion", "sign_up", "inscription", "create_account", "créer un compte", "myaccount", "mon compte", "my_account", "mon compte", "my-account", "mon compte", "createaccount", "créer un compte", "log_in", "connexion", "register-account", "inscription du compte", "register_account", "inscription du compte", "cookiemanagement", "gestion des cookies", "cookie_management", "gestion des cookies", "cookie-management", "gestion des cookies", "more_info", "plus d’informations", "moreinfo", "plus d’informations", "legal", "juridique", "compliance", "conformité", "support", "assistance",
    # turkey
    "privacy", "gizlilik", "cookie", "çerez", "consent", "onay", "terms", "şartlar", "policy", "politika", "optin", "katılma", "optout", "çıkma", "opt-in", "katılma", "opt-out", "çıkma", "tos", "kullanım şartları", "statement", "beyan", "notice", "bildirim", "third-party", "üçüncü taraf", "thirdparty", "üçüncü taraf", "third_party", "üçüncü taraf", "cookies", "çerezler", "consents", "onaylar", "term", "şart", "policies", "politikalar", "statements", "beyanlar", "notices", "bildirimler", "thirdparties", "üçüncü taraflar", "third_parties", "üçüncü taraflar", "third-parties", "üçüncü taraflar", "partner", "ortak", "vendor", "satıcı", "preference", "tercih", "partners", "ortaklar", "vendors", "satıcılar", "preferences", "tercihler", "data_protection", "veri koruma", "data-protection", "veri koruma", "learn_more", "daha fazla bilgi", "learnmore", "daha fazla bilgi", "learn-more", "daha fazla bilgi", "more_info", "daha fazla bilgi", "moreinfo", "daha fazla bilgi", "more-info", "daha fazla bilgi", "manage_settings", "ayarları yönet", "manage-settings", "ayarları yönet", "manage", "yönet", "settings", "ayarlar", "setting", "ayar", "manage", "yönet", "imprint", "yasal uyarı", "login", "giriş", "signin", "giriş", "sign-in", "giriş", "log-in", "giriş", "register", "kayıt", "signup", "kayıt", "sign-up", "kayıt", "create-account", "hesap oluştur", "account", "hesap", "sign_in", "giriş", "sign_up", "kayıt", "create_account", "hesap oluştur", "myaccount", "hesabım", "my_account", "hesabım", "my-account", "hesabım", "createaccount", "hesap oluştur", "log_in", "giriş", "register-account", "hesap kaydı", "register_account", "hesap kaydı", "cookiemanagement", "çerez yönetimi", "cookie_management", "çerez yönetimi", "cookie-management", "çerez yönetimi", "more_info", "daha fazla bilgi", "moreinfo", "daha fazla bilgi", "legal", "yasal", "compliance", "uyum", "support", "destek",
    # iran/persian
    "privacy", "حریم خصوصی", "cookie", "کوکی", "consent", "رضایت", "terms", "شرایط", "policy", "سیاست", "optin", "پیوستن", "optout", "انصراف", "opt-in", "پیوستن", "opt-out", "انصراف", "tos", "شرایط استفاده", "statement", "بیانیه", "notice", "اعلان", "third-party", "شخص ثالث", "thirdparty", "شخص ثالث", "third_party", "شخص ثالث", "cookies", "کوکی‌ها", "consents", "رضایت‌ها", "term", "شرط", "policies", "سیاست‌ها", "statements", "بیانیه‌ها", "notices", "اعلان‌ها", "thirdparties", "اشخاص ثالث", "third_parties", "اشخاص ثالث", "third-parties", "اشخاص ثالث", "partner", "شریک", "vendor", "فروشنده", "preference", "ترجیح", "partners", "شرکا", "vendors", "فروشندگان", "preferences", "ترجیحات", "data_protection", "حفاظت از داده‌ها", "data-protection", "حفاظت از داده‌ها", "learn_more", "بیشتر بدانید", "learnmore", "بیشتر بدانید", "learn-more", "بیشتر بدانید", "more_info", "اطلاعات بیشتر", "moreinfo", "اطلاعات بیشتر", "more-info", "اطلاعات بیشتر", "manage_settings", "مدیریت تنظیمات", "manage-settings", "مدیریت تنظیمات", "manage", "مدیریت", "settings", "تنظیمات", "setting", "تنظیم", "manage", "مدیریت", "imprint", "اطلاعات حقوقی", "login", "ورود", "signin", "ورود", "sign-in", "ورود", "log-in", "ورود", "register", "ثبت‌نام", "signup", "ثبت‌نام", "sign-up", "ثبت‌نام", "create-account", "ایجاد حساب", "account", "حساب کاربری", "sign_in", "ورود", "sign_up", "ثبت‌نام", "create_account", "ایجاد حساب", "myaccount", "حساب من", "my_account", "حساب من", "my-account", "حساب من", "createaccount", "ایجاد حساب", "log_in", "ورود", "register-account", "ثبت حساب", "register_account", "ثبت حساب", "cookiemanagement", "مدیریت کوکی", "cookie_management", "مدیریت کوکی", "cookie-management", "مدیریت کوکی", "more_info", "اطلاعات بیشتر", "moreinfo", "اطلاعات بیشتر", "legal", "حقوقی", "compliance", "انطباق", "support", "پشتیبانی",
    # swedish
    "privacy", "integritet", "cookie", "kaka", "consent", "samtycke", "terms", "villkor", "policy", "policy", "optin", "godkännande", "optout", "avregistrering", "opt-in", "godkännande", "opt-out", "avregistrering", "tos", "användarvillkor", "statement", "uttalande", "notice", "meddelande", "third-party", "tredje part", "thirdparty", "tredje part", "third_party", "tredje part", "cookies", "kakor", "consents", "samtycken", "term", "villkor", "policies", "policyer", "statements", "uttalanden", "notices", "meddelanden", "thirdparties", "tredje parter", "third_parties", "tredje parter", "third-parties", "tredje parter", "partner", "partner", "vendor", "leverantör", "preference", "preferens", "partners", "partners", "vendors", "leverantörer", "preferences", "inställningar", "data_protection", "dataskydd", "data-protection", "dataskydd", "learn_more", "läs mer", "learnmore", "läs mer", "learn-more", "läs mer", "more_info", "mer information", "moreinfo", "mer information", "more-info", "mer information", "manage_settings", "hantera inställningar", "manage-settings", "hantera inställningar", "manage", "hantera", "settings", "inställningar", "setting", "inställning", "manage", "hantera", "imprint", "impressum", "login", "logga in", "signin", "logga in", "sign-in", "logga in", "log-in", "logga in", "register", "registrera", "signup", "registrera", "sign-up", "registrera", "create-account", "skapa konto", "account", "konto", "sign_in", "logga in", "sign_up", "registrera", "create_account", "skapa konto", "myaccount", "mitt konto", "my_account", "mitt konto", "my-account", "mitt konto", "createaccount", "skapa konto", "log_in", "logga in", "register-account", "kontoregistrering", "register_account", "kontoregistrering", "cookiemanagement", "cookiehantering", "cookie_management", "cookiehantering", "cookie-management", "cookiehantering", "more_info", "mer information", "moreinfo", "mer information", "legal", "juridisk", "compliance", "efterlevnad", "support", "support",
    # korean
    "privacy", "개인정보", "cookie", "쿠키", "consent", "동의", "terms", "약관", "policy", "정책", "optin", "동의", "optout", "거부", "opt-in", "동의", "opt-out", "거부", "tos", "이용약관", "statement", "명세", "notice", "공지", "third-party", "제3자", "thirdparty", "제3자", "third_party", "제3자", "cookies", "쿠키", "consents", "동의", "term", "약관", "policies", "정책", "statements", "명세", "notices", "공지", "thirdparties", "제3자", "third_parties", "제3자", "third-parties", "제3자", "partner", "파트너", "vendor", "공급업체", "preference", "환경설정", "partners", "파트너", "vendors", "공급업체", "preferences", "환경설정", "data_protection", "데이터 보호", "data-protection", "데이터 보호", "learn_more", "자세히 보기", "learnmore", "자세히 보기", "learn-more", "자세히 보기", "more_info", "추가 정보", "moreinfo", "추가 정보", "more-info", "추가 정보", "manage_settings", "설정 관리", "manage-settings", "설정 관리", "manage", "관리", "settings", "설정", "setting", "설정", "manage", "관리", "imprint", "법적 고지", "login", "로그인", "signin", "로그인", "sign-in", "로그인", "log-in", "로그인", "register", "회원가입", "signup", "회원가입", "sign-up", "회원가입", "create-account", "계정 생성", "account", "계정", "sign_in", "로그인", "sign_up", "회원가입", "create_account", "계정 생성", "myaccount", "내 계정", "my_account", "내 계정", "my-account", "내 계정", "createaccount", "계정 생성", "log_in", "로그인", "register-account", "계정 등록", "register_account", "계정 등록", "cookiemanagement", "쿠키 관리", "cookie_management", "쿠키 관리", "cookie-management", "쿠키 관리", "more_info", "추가 정보", "moreinfo", "추가 정보", "legal", "법적 정보", "compliance", "준수", "support", "지원",

}

forbidden_paths = {fp.lower() for fp in forbidden_paths}
            
common_cookie_banner_words = {
    "privacy policy", "cookie policy", "cookie consent", "cookie settings", "cookie preferences", "cookie management",
    "privacy settings", "privacy preferences", "privacy management", "data protection", "data policy", "data privacy",
    "learn more", "more info", "manage settings", "imprint",

    # common actions
    "accept all", "accept cookies", "accept all cookies", "agree to cookies",
    "reject all", "reject cookies", "decline cookies",
    "save preferences", "confirm choices", "allow all cookies",

    # settings / controls
    "customize cookies", "manage cookies", "cookie options", "advanced settings",
    "essential cookies", "strictly necessary cookies", "functional cookies",
    "performance cookies", "analytics cookies", "marketing cookies", "advertising cookies",

    # legal / compliance
    "legitimate interest", "consent management", "consent management platform",
    "data processing", "third party cookies", "third party services",
    "use of cookies", "cookie usage", "tracking technologies",
    "personal data", "user consent", "data collection",

    # less common / variants
    "your privacy choices", "privacy notice", "privacy overview",
    "cookie declaration", "cookie information", "data usage",
    "site uses cookies", "we use cookies", "this website uses cookies",
    "improve user experience", "enhance your experience",
    "store and access information", "measure audience", "personalised ads"
}

ANTI_BOT_SIGNATURES_MANUALLY_IDENTIFIED = {
    "Slide right to secure your access",
    "We detected unusual activity from your device or network",
    "Automated (bot) activity on your network",
    "there is a robot on the same network",
    "Something about the behaviour of the browser has caught our attention",
    "Подозрительная активность. Пожалуйста, подождите.",
    "Подождите, страница обновится автоматически.",
    "Если не помогло — очистите кэш и cookie в браузере, потом перезагрузите страницу.",
    "Возникли сложности с подключением",
    "Пожалуйста, используйте прямое подключение, чтобы сервис работал корректно",
    "Verify you are human",
    "This website uses a security service to protect against malicious bots.",
    "This page is displayed while the website verifies you are not a bot",
}

ANTI_BOT_SIGNATURES = {
    "Pardon Our Interruption",
    "You don't have permission",

    # Cloudflare
    "error code 1020",
    "attention required! | cloudflare",
    "please stand by, while we are checking your browser",
    "checking if the site connection is secure",
    "cloudflare ray id",
    "performance & security by cloudflare",
    "sorry, you have been blocked",
    "you have been blocked",
    "browser integrity check",
    "enable javascript and cookies to continue",
    "challenge-platform",
    "/cdn-cgi/challenge-platform/",
    "cf-chl-bypass",
    "cf-browser-verification",
    "cf_clearance",
    "why do i have to complete a captcha",
    "this website is using a security service to protect itself from online attacks",

    # Cloudflare rate limiting
    "error 1015 ray id",
    "you are being rate limited",
    "the owner of this website has banned you temporarily",

    # Akamai
    "reference #",
    "access denied | akamai",
    "the requested url was rejected",
    "your support id is:",
    "generated by akamai",
    "akamai ghost",
    "access denied. you don't have permission to access",

    # Imperva / Incapsula
    "incapsula incident id",
    "request unsuccessful. incapsula incident id",
    "_incapsula_resource",
    "powered by imperva",
    "imperva incident id",
    "the website encountered an unexpected error",
    "pardon our interruption",

    # DataDome
    "datadome",
    "captcha delivered by datadome",
    "please enable js and disable any ad blocker",
    "protected by datadome",

    # PerimeterX / HUMAN
    "perimeterx",
    "px-captcha",
    "press & hold to confirm you are a human",
    "access to this page has been denied",
    "why have i been blocked?",
    "powered by perimeterx",
    "human security",

    # Sucuri
    "sucuri website firewall",
    "access denied - sucuri website firewall",
    "block id:",
    "sucuri ray id",

    # AWS WAF / Amazon
    "request blocked",
    "generated by cloudfront",
    "the request could not be satisfied",
    "amazon cloudfront distribution is configured to block access",
    "x-amz-cf-id",

    # F5 / BIG-IP ASM
    "the requested url was rejected. please consult with your administrator",
    "support id is:",
    "f5 networks",
    "big-ip",

    # Radware
    "access denied by radware",
    "radware cloud waf service",
    "bot manager",

    # Shape Security / F5 Shape
    "shape_security",
    "shape security",
    "verify you are human",

    # Kasada
    "kasada",
    "kpsdk",
    "x-kpsdk",
    "blocked by kasada",

    # Generic high-confidence challenge markers
    "captcha challenge",
    "automated queries",
    "detected unusual traffic",
    "our systems have detected unusual traffic",
    "unusual traffic from your computer network",
    "to continue, please verify you are not a robot",
    "verify you are human",
    "please verify you are a human",
    "one more step",
    "security check to access",
    "bot detection",
    "automated access to this page has been denied",
    "your request looks automated",
    "suspected automated queries",
}

BLOCK_INDICATORS = {
    # DOM markers
    "#cf-challenge-running",
    "#challenge-form",
    "form#challenge-form",
    "iframe[src*='captcha']",
    "script[src*='challenge-platform']",
    "script[src*='captcha']",
    "script[src*='datadome']",
    "script[src*='perimeterx']",
    "script[src*='px-captcha']",
    "iframe[src*='_Incapsula_Resource']",
}