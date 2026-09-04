import re
import time
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urljoin
import requests
from bs4 import BeautifulSoup
import cv2
import numpy as np
import easyocr



LOGIN_URL = "https://login.gitam.edu/Login.aspx"
CAPTCHA_URL = "https://login.gitam.edu/CaptchaImage.ashx"
GSTUDENT_HOME_URL = "https://gstudent.gitam.edu/Home"
NEW_GLEARN_URL = f"{GSTUDENT_HOME_URL}/Newgleanencry"
GLEARN = "https://glearn.gitam.edu"
TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36"
HTML_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"


class PortalError(RuntimeError):
    pass


class InvalidCredentials(PortalError):
    pass

@dataclass
class PortalData:
    subjects: list[dict]
    timetable: list[dict] | None
    timetable_error: str | None = None


def _headers(**extra):
    return {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9", **extra}


def _input(soup: BeautifulSoup, name: str) -> str:
    element = soup.find("input", {"name": name})
    if not element or element.get("value") is None:
        raise PortalError("The college login form changed. Please try again later.")
    return element["value"]

# Initialize OCR reader once (slow to create)
_ocr_reader = None

def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        _ocr_reader = easyocr.Reader(["en"], gpu=False)
    return _ocr_reader

def get_image_text(session: requests.Session, image_url: str) -> str:
    response = session.get(
        image_url,
        headers=_headers(Referer=LOGIN_URL),
        timeout=10
    )
    response.raise_for_status()

    image_bytes = response.content

    image_array = np.frombuffer(
        image_bytes,
        dtype=np.uint8
    )

    image = cv2.imdecode(
        image_array,
        cv2.IMREAD_COLOR
    )

    if image is None:
        raise ValueError("Could not decode image")

    # Preprocess image for better OCR
    # Step 1: Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Step 2: Resize image (make it bigger for better OCR)
    height, width = gray.shape[:2]
    scale = 3
    resized = cv2.resize(gray, (width * scale, height * scale), interpolation=cv2.INTER_CUBIC)

    # Step 3: Apply bilateral filter to remove noise while keeping edges sharp
    filtered = cv2.bilateralFilter(resized, 9, 75, 75)

    # Step 4: Apply Otsu's thresholding
    _, thresh = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Step 5: Morphological operations to clean up
    kernel = np.ones((2, 2), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    # Step 6: Add border (white space) around image for better OCR
    thresh = cv2.copyMakeBorder(thresh, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)

    reader = _get_ocr_reader()
    results = reader.readtext(thresh)

    texts = []
    for bbox, text, confidence in results:
        # Only include text with reasonable confidence
        if confidence > 0.3:
            texts.append(text)

    return " ".join(texts)
def authenticate(
    username: str,
    password: str,
    session: requests.Session | None = None
) -> requests.Session:
    """Authenticate using credentials received from the frontend."""
    max_login_retries = 3

    for login_attempt in range(max_login_retries):
        session = session or requests.Session()

        try:
            # 1. Load login page using the session
            page = session.get(
                LOGIN_URL,
                headers=_headers(Accept=HTML_ACCEPT),
                timeout=TIMEOUT
            )

            page.raise_for_status()

            # 2. CAPTCHA IMAGE REQUEST
            captcha_text = get_image_text(session, CAPTCHA_URL)
            captcha_text = captcha_text.replace(" ", "")

            # 3. Parse login page
            soup = BeautifulSoup(page.text, "html.parser")

            # 4. Build login payload
            payload = {
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
                "__VIEWSTATE": _input(soup, "__VIEWSTATE"),
                "__VIEWSTATEGENERATOR": _input(
                    soup,
                    "__VIEWSTATEGENERATOR"
                ),
                "__VIEWSTATEENCRYPTED": "",
                "__EVENTVALIDATION": _input(
                    soup,
                    "__EVENTVALIDATION"
                ),
                "hiddenCsrfToken": _input(
                    soup,
                    "hiddenCsrfToken"
                ),

                "txtusername": username,
                "password": password,

                # Keep CAPTCHA handling separate from automated login.
                "txtCaptchaInput": captcha_text,

                "Submit": "LOGIN",
            }

            response = session.post(LOGIN_URL, data=payload, headers=_headers(
                **{"Content-Type": "application/x-www-form-urlencoded", "Origin": "https://login.gitam.edu", "Referer": LOGIN_URL}
            ), allow_redirects=False, timeout=TIMEOUT)
            location = response.headers.get("Location")
            if not location:
                if login_attempt == max_login_retries - 1:
                    raise InvalidCredentials("Invalid student ID, password, or an uncompleted portal CAPTCHA.")
                # Wait before retry to allow CAPTCHA to refresh
                time.sleep(2)
                continue
            redirect = urljoin(LOGIN_URL, location)
            redirect_response = session.get(redirect, headers=_headers(Referer=LOGIN_URL), allow_redirects=True, timeout=TIMEOUT)
            home = session.get(GSTUDENT_HOME_URL, headers=_headers(Referer=redirect_response.url), allow_redirects=True, timeout=TIMEOUT)
            if "login.gitam.edu" in home.url.lower():
                if login_attempt == max_login_retries - 1:
                    raise InvalidCredentials("GStudent did not accept the portal login.")
                # Wait before retry to allow CAPTCHA to refresh
                time.sleep(2)
                continue
            sso_page = session.get(NEW_GLEARN_URL, headers=_headers(**{"Accept": "*/*", "X-Requested-With": "XMLHttpRequest", "Referer": GSTUDENT_HOME_URL}), allow_redirects=False, timeout=TIMEOUT)
            match = re.search(r"window\.location\.href\s*=\s*['\"]([^'\"]+)['\"]", sso_page.text)
            if not match:
                raise PortalError("GLearn SSO could not be started. Please try again later.")
            sso = session.get(urljoin(NEW_GLEARN_URL, match.group(1)), headers=_headers(Referer=GSTUDENT_HOME_URL), allow_redirects=True, timeout=TIMEOUT)
            if "glearn.gitam.edu" not in sso.url.lower():
                raise PortalError("GLearn SSO was not accepted.")
            dashboard = session.get(f"{GLEARN}/student/std_dashboard_main", headers=_headers(Referer=sso.url), allow_redirects=True, timeout=TIMEOUT)
            if "std_dashboard_main" not in dashboard.url:
                raise PortalError("GLearn dashboard is not authenticated.")
            return session
        except requests.RequestException as exc:
            raise PortalError("The college portal is temporarily unavailable.") from exc


def _number(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(float(str(value).strip())))
    except (TypeError, ValueError):
        return default


def parse_subjects(payload: Any) -> list[dict]:
    if not isinstance(payload, list):
        raise PortalError("GLearn returned an unexpected attendance response.")
    by_code: dict[str, dict] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        code = str(item.get("subjectcode") or "").strip()
        name = str(item.get("subjectname") or "").strip()
        if not code or not name:
            continue
        total = _number(item.get("total"))
        present = min(_number(item.get("p")), total)
        calculated = round((present / total) * 100, 2) if total else 0.0
        # The underlying counts are authoritative if the portal percentage is stale/missing.
        by_code[code] = {"subjectCode": code, "subjectName": name, "totalClasses": total,
                         "presentClasses": present, "absentClasses": total - present, "percentage": calculated}
    return list(by_code.values())


_SUBJECT_CODE_RE = re.compile(r"\b\d{2}[A-Za-z]{2,}\d{3,}[A-Za-z]?\b", re.I)


def parse_attendance_html(html: str) -> list[dict]:
    """Best-effort parser for the GLearn attendance report HTML table.

    The JSON endpoint (getsubject_Std) can bounce to the My-GITAM login page even with a
    valid session/regno, so we fall back to the attendance table that the report page
    already rendered. Column order is not assumed: the subject code identifies the row and
    present/total are recovered from integer values, verified against a percentage when present.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    result, seen = [], set()
    for row in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        text = " ".join(cells)
        match = _SUBJECT_CODE_RE.search(text)
        if not match:
            continue
        code = re.sub(r"[^A-Za-z0-9]", "", match.group(0)).upper()

        # Name = longest non-code, non-numeric cell.
        name = ""
        for cell in cells:
            clean = cell.strip()
            if not clean or re.fullmatch(r"[0-9%.\s,/()_-]+", clean):
                continue
            if len(clean) > len(name):
                name = clean
        if not name:
            continue

        # Numeric tokens (with a flag for '%'-suffixed percentage values).
        numbers = []            # (float, is_percentage_like)
        for cell in cells:
            for token in re.findall(r"\d+(?:\.\d+)?%?", cell):
                is_pct = token.endswith("%")
                numbers.append((float(token.rstrip("%")), is_pct))
        if not numbers:
            continue

        ints = sorted({int(v) for v, pct in numbers if (not pct) and float(v).is_integer()})
        if len(ints) < 2:
            continue

        # present/total = integers a<=b whose ratio matches a decimal in the row (the percentage).
        present = total = None
        for total_c in reversed(ints):
            for present_c in ints:
                if present_c > total_c:
                    continue
                calc = round(present_c / total_c * 100, 2) if total_c else 0
                if any(abs(v - calc) <= 0.5 for v, _ in numbers):
                    present, total = present_c, total_c
                    break
            if present is not None:
                break
        if present is None:          # fallback: two largest integers (present <= total)
            present_c = max(ints)
            total_c = max(v for v in ints if v >= (min(ints))) if ints else present_c
            present = ints[-2] if len(ints) >= 2 else present_c
            total = present_c if present_c >= present else present
        present = min(present, total)

        percentage = round(100 * present / total, 2) if total else 0.0
        item = {"subjectCode": code, "subjectName": name, "totalClasses": total,
                "presentClasses": present, "absentClasses": total - present, "percentage": percentage}
        if code in seen:
            continue
        seen.add(code)
        result.append(item)
    if not result:
        raise PortalError("GLearn attendance table was not recognized.")
    return result


def _parse_time_range(label: str) -> tuple[str | None, str | None]:
    values = re.findall(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b", label)
    if len(values) >= 2:
        return values[0].zfill(5), values[1].zfill(5)
    # Some tables use 08:00 AM - 08:50 AM.
    matches = re.findall(r"\b\d{1,2}:\d{2}\s*(?:AM|PM)\b", label, re.I)
    if len(matches) >= 2:
        from datetime import datetime
        return tuple(datetime.strptime(value.upper(), "%I:%M %p").strftime("%H:%M") for value in matches[:2])
    return None, None


def parse_timetable(html: str, subjects: list[dict]) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    table = soup.find("table", class_=lambda value: value and "table-bordered" in value) or soup.find("table")
    if not table:
        raise PortalError("GLearn timetable format was not found.")
    header_cells = table.select("thead tr th, thead tr td")
    headers = [cell.get_text(" ", strip=True).title() for cell in header_cells]
    if not headers or "Monday" not in headers:
        raise PortalError("GLearn timetable columns changed.")
    known_by_code = {item["subjectCode"].lower(): item for item in subjects}
    result, seen = [], set()
    for row in table.select("tbody tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        start, end = _parse_time_range(cells[0].get_text(" ", strip=True))
        if not start or not end:
            continue
        for position, day in enumerate(headers[1:], 1):
            if day not in {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"} or position >= len(cells):
                continue
            raw = cells[position].get_text(" ", strip=True)
            if not raw or raw.lower() in {"-", "--", "na", "n/a"}:
                continue
            normalized_raw = " ".join(raw.lower().split())
            # Sort codes by length (longest first) to match lab codes (e.g., "24csen2202p") before lecture codes (e.g., "24csen2202")
            sorted_codes = sorted(known_by_code.items(), key=lambda x: len(x[0]), reverse=True)
            subject = next((item for code, item in sorted_codes if code in normalized_raw), None)
            if not subject:
                subject = next((item for item in subjects if " ".join(item["subjectName"].lower().split()) in normalized_raw), None)
            if not subject:
                continue
            item = {"dayOfWeek": day, "startTime": start, "endTime": end,
                    "subjectCode": subject["subjectCode"], "subjectName": subject["subjectName"]}
            key = tuple(item.values())
            if key not in seen:
                seen.add(key); result.append(item)
    return result


def _refresh_glearn_session(session: requests.Session) -> requests.Session:
    """Re-run the GStudent->GLearn SSO handshake on the existing session so a
    protected GLearn AJAX resource (e.g. getsubject_Std) is served with fresh
    SSO cookies instead of being bounced to the My-GITAM login page."""
    try:
        sso_page = session.get(
            NEW_GLEARN_URL,
            headers=_headers(**{"Accept": "*/*", "X-Requested-With": "XMLHttpRequest", "Referer": GSTUDENT_HOME_URL}),
            allow_redirects=False,
            timeout=TIMEOUT,
        )
        match = re.search(r"window\.location\.href\s*=\s*['\"]([^'\"]+)['\"]", sso_page.text)
        if not match:
            raise PortalError("GLearn SSO could not be re-started.")
        sso = session.get(
            urljoin(NEW_GLEARN_URL, match.group(1)),
            headers=_headers(Referer=GSTUDENT_HOME_URL),
            allow_redirects=True,
            timeout=TIMEOUT,
        )
        if "glearn.gitam.edu" not in sso.url.lower():
            raise PortalError("GLearn SSO was not re-accepted.")
        dashboard = session.get(
            f"{GLEARN}/student/std_dashboard_main",
            headers=_headers(Referer=sso.url),
            allow_redirects=True,
            timeout=TIMEOUT,
        )
        if "std_dashboard_main" not in dashboard.url:
            raise PortalError("GLearn is not accepting the refreshed session.")
        return session
    except PortalError:
        raise
    except requests.RequestException as exc:
        raise PortalError("The college portal is temporarily unavailable while refreshing the GLearn session.") from exc



def fetch_current_data(session: requests.Session) -> PortalData:
    step = "dashboard"
    try:
        dashboard = session.get(f"{GLEARN}/student/std_dashboard_main", headers=_headers(), allow_redirects=True, timeout=TIMEOUT)
        if "std_dashboard_main" not in dashboard.url:
            raise PortalError("GLearn session expired. Please log in again.")
        step = "attendance"
        attendance = session.get(f"{GLEARN}/student/std_attendance_report", headers=_headers(Referer=dashboard.url), allow_redirects=True, timeout=TIMEOUT)
        if "std_attendance_report" not in attendance.url:
            raise PortalError("GLearn attendance page is unavailable.")
        regno = ""
        photo = re.search(r"doeresults\.gitam\.edu/photo/img\.aspx\?id\s*=\s*([^\"\s>]+)", dashboard.text, re.I)
        if photo:
            regno = unquote(photo.group(1))
        roll = re.search(r"\b(202\d{7})\b", dashboard.text)
        if roll:
            regno = roll.group(1)
        # The GLearn attendance page passes an opaque (often base64-style) identifier as the
        # per-request token it sends as 'regno' to getsubject_Std; the plain roll number is
        # rejected for these AJAX resources. Prefer the actual token the page will use.
        import html as _html_mod
        token = re.search(r'id="srch_term"[^>]*value="([^"]*)"', attendance.text, re.I)
        if token:
            raw = _html_mod.unescape(token.group(1)).strip()
            if raw and "#" in raw:
                raw = raw.split("#")[0].strip()
            if raw:
                regno = raw
        if not regno:
            raise PortalError("Student identifier was not available from GLearn.")
        step = "attendance-data"
        response = None
        for _att_attempt in range(2):
            response = session.get(f"{GLEARN}/student/getsubject_Std", params={"regno": regno}, headers=_headers(**{"Accept": "*/*", "X-Requested-With": "XMLHttpRequest", "Referer": attendance.url}), timeout=TIMEOUT)
            response.raise_for_status()
            try:
                subjects = parse_subjects(response.json())
                break
            except (ValueError, json.JSONDecodeError) as _jerr:
                if _att_attempt == 0:
                    # Likely bounced to the My-GITAM login page; re-mint the GLearn SSO and retry once.
                    _refresh_glearn_session(session)
                else:
                    # The JSON endpoint is unreliable here; parse the attendance table the report
                    # page already rendered (attendance.text) instead of failing the whole sync.
                    try:
                        subjects = parse_attendance_html(attendance.text)
                    except PortalError as _html_err:
                        raise PortalError(
                            f"GLearn attendance data could not be parsed (JSON redirect to {response.url} and "
                            f"HTML fallback failed). Last error: {_html_err}"
                        ) from _jerr
        try:
            timetable = session.get(f"{GLEARN}/student/std_timetable", headers=_headers(Accept=HTML_ACCEPT, Referer=attendance.url), allow_redirects=True, timeout=TIMEOUT)
            if "std_timetable" not in timetable.url: raise PortalError("GLearn timetable page is unavailable.")
            return PortalData(subjects=subjects, timetable=parse_timetable(timetable.text, subjects))
        except (PortalError, requests.RequestException):
            # Attendance has already been safely fetched; retain a valid old timetable.
            return PortalData(subjects=subjects, timetable=None, timetable_error="Timetable synchronization failed")
    except requests.RequestException as exc:
        http = getattr(exc, "response", None)
        if http is not None:
            snippet = ""
            try: snippet = (http.text or "")[:200]
            except Exception: pass
            raise PortalError(f"The college portal is temporarily unavailable while fetching {step} (HTTP {http.status_code}: {snippet}).") from exc
        raise PortalError(f"The college portal is temporarily unavailable while fetching {step} ({exc}).") from exc
