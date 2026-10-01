from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


MONITORING_HOSTS = {"kwicky.kanalytics.in"}
KANALYTICS_API = (
    "https://kwicky.kanalytics.in/middleware/commonmid/artdets/{article_key}/0/0"
)
REDIRECT_CODES = {301, 302, 303, 307, 308}
USER_AGENT = "BFSI-news-retrieval-MVP/1.0"


@dataclass
class ArticleInput:
    input_id: str
    sequence: str
    date: str
    headline: str
    source_domain: str
    supplied_url: str
    journalist: str
    language: str
    reach: str


def unwrap_safelink(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname and parsed.hostname.endswith(
        "safelinks.protection.outlook.com"
    ):
        target = parse_qs(parsed.query).get("url", [""])[0]
        return unquote(target)
    return url


def normalise_domain(value: str) -> str:
    value = value.strip().lower()
    if "://" not in value:
        value = f"https://{value}"
    host = urlparse(value).hostname or ""
    return host.removeprefix("www.").rstrip(".")


def domain_matches(host: str, expected_domain: str) -> bool:
    host = normalise_domain(host)
    expected = normalise_domain(expected_domain)
    return bool(expected) and (host == expected or host.endswith(f".{expected}"))


def _assert_public_host(host: str) -> None:
    if not host:
        raise ValueError("URL has no hostname")
    for result in socket.getaddrinfo(host, None):
        address = ipaddress.ip_address(result[4][0])
        if not address.is_global:
            raise ValueError(f"Non-public destination rejected: {host}")


def validate_request_url(url: str, permitted_hosts: Iterable[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS URLs are permitted")
    host = parsed.hostname or ""
    if not any(domain_matches(host, allowed) for allowed in permitted_hosts):
        raise ValueError(f"Host is not permitted: {host}")
    _assert_public_host(host)


def extract_html_rows(html: str) -> list[ArticleInput]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[ArticleInput] = []

    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 7:
            continue

        sequence = _clean_text(cells[0])
        headline_link = cells[2].find("a", href=True)
        source_link = cells[3].find("a", href=True)
        if not sequence.isdigit() or not headline_link:
            continue

        supplied_url = unwrap_safelink(headline_link["href"])
        source_value = (
            unwrap_safelink(source_link["href"])
            if source_link
            else _clean_text(cells[3])
        )
        source_domain = normalise_domain(source_value)
        if not source_domain:
            continue

        records.append(
            ArticleInput(
                input_id=f"article-{len(records) + 1:04d}",
                sequence=sequence,
                date=_clean_text(cells[1]),
                headline=_clean_text(cells[2]),
                source_domain=source_domain,
                supplied_url=supplied_url,
                journalist=_clean_text(cells[4]),
                language=_clean_text(cells[5]),
                reach=_clean_text(cells[6]),
            )
        )

    if not records:
        raise ValueError("No article rows were found in the HTML")
    return records


def extract_input_rows(source_path: Path) -> list[ArticleInput]:
    if source_path.suffix.lower() == ".eml":
        message = BytesParser(policy=policy.default).parsebytes(
            source_path.read_bytes()
        )
        html = next(
            (
                part.get_content()
                for part in message.walk()
                if part.get_content_type() == "text/html"
            ),
            None,
        )
        if not html:
            raise ValueError("The email does not contain an HTML body")
        return extract_html_rows(html)

    return extract_html_rows(source_path.read_text(encoding="utf-8"))


def _clean_text(node: BeautifulSoup) -> str:
    return " ".join(node.get_text(" ", strip=True).split())


def extract_article_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(
        ["script", "style", "noscript", "nav", "footer", "header", "aside", "form"]
    ):
        node.decompose()

    title = ""
    if soup.title:
        title = _clean_text(soup.title)
    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    article = soup.find("article") or soup.find("main") or soup.body or soup
    text = _clean_text(article)

    if canonical and canonical.get("href"):
        title = title.strip()
    return title, text


def resolve_monitoring_url(
    url: str, session: requests.Session, timeout: float
) -> tuple[str, str]:
    parsed = urlparse(url)
    if not domain_matches(parsed.hostname or "", "kwicky.kanalytics.in"):
        return url, ""

    article_key = parsed.query
    if not re.fullmatch(r"[A-Za-z0-9_-]+", article_key):
        return "", "invalid_monitoring_article_key"

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://kwicky.kanalytics.in",
        "Referer": url,
    }
    if cookie := os.environ.get("KANALYTICS_COOKIE"):
        headers["Cookie"] = cookie
    if authorization := os.environ.get("KANALYTICS_AUTHORIZATION"):
        headers["Authorization"] = authorization

    response = session.post(
        KANALYTICS_API.format(article_key=article_key),
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and payload.get("err"):
        if "unauthorized" in str(payload["err"]).lower():
            return "", "monitoring_auth_required"
        return "", "monitoring_api_error"

    try:
        source_link = payload[0]["data"]["source_link"]
    except (IndexError, KeyError, TypeError):
        return "", "monitoring_source_link_missing"

    if not isinstance(source_link, str) or not source_link.strip():
        return "", "monitoring_source_link_missing"
    return unwrap_safelink(source_link.strip()), ""


def retrieve_article(
    article: ArticleInput,
    timeout: float = 20,
    max_bytes: int = 2_000_000,
    session: requests.Session | None = None,
) -> dict:
    result = asdict(article)
    result.update(
        {
            "status": "unresolved",
            "reason": "",
            "final_url": "",
            "retrieved_title": "",
            "article_text_file": "",
        }
    )

    current_url = article.supplied_url
    initial_host = urlparse(current_url).hostname or ""
    permitted_initial_hosts = {article.source_domain, *MONITORING_HOSTS}
    if not any(
        domain_matches(initial_host, allowed) for allowed in permitted_initial_hosts
    ):
        result["reason"] = "supplied_link_host_not_permitted"
        return result

    client = session or requests.Session()
    try:
        if any(
            domain_matches(initial_host, host) for host in MONITORING_HOSTS
        ):
            current_url, monitoring_error = resolve_monitoring_url(
                current_url, client, timeout
            )
            if monitoring_error:
                result["reason"] = monitoring_error
                return result

        for _ in range(6):
            validate_request_url(current_url, permitted_initial_hosts)
            response = client.get(
                current_url,
                allow_redirects=False,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
                stream=True,
                timeout=timeout,
            )
            if response.status_code in REDIRECT_CODES:
                location = response.headers.get("Location")
                if not location:
                    result["reason"] = "redirect_without_location"
                    return result
                current_url = urljoin(current_url, location)
                continue
            break
        else:
            result["reason"] = "too_many_redirects"
            return result

        result["final_url"] = current_url
        final_host = urlparse(current_url).hostname or ""
        if not domain_matches(final_host, article.source_domain):
            result["reason"] = (
                "monitoring_link_did_not_resolve"
                if any(domain_matches(final_host, host) for host in MONITORING_HOSTS)
                else "final_domain_mismatch"
            )
            return result

        if response.status_code != 200:
            result["reason"] = f"http_{response.status_code}"
            return result

        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type:
            result["reason"] = "response_is_not_html"
            return result

        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(65_536):
            total += len(chunk)
            if total > max_bytes:
                result["reason"] = "page_exceeds_size_limit"
                return result
            chunks.append(chunk)

        response.encoding = response.encoding or "utf-8"
        html = b"".join(chunks).decode(response.encoding, errors="replace")
        title, text = extract_article_text(html)
        if len(text) < 300:
            result["reason"] = "insufficient_article_text"
            return result

        result.update(
            {
                "status": "retrieved",
                "reason": "",
                "retrieved_title": title,
                "_article_text": text,
            }
        )
        return result
    except (requests.RequestException, OSError, ValueError) as error:
        result["reason"] = f"{type(error).__name__}: {error}"
        return result


def retrieve_records(
    records: list[ArticleInput], workers: int = 6
) -> list[dict]:
    results: list[dict | None] = [None] * len(records)
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 12))) as pool:
        futures = {
            pool.submit(retrieve_article, record): index
            for index, record in enumerate(records)
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    if any(result is None for result in results):
        raise RuntimeError("One or more retrieval tasks did not return a result")
    return [result for result in results if result is not None]


def write_results(
    output_dir: Path, records: list[ArticleInput], results: list[dict]
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    article_dir = output_dir / "article-text"
    article_dir.mkdir(exist_ok=True)

    manifest: list[dict] = []
    for result in results:
        text = result.pop("_article_text", "")
        if text:
            text_path = article_dir / f"{result['input_id']}.txt"
            text_path.write_text(text, encoding="utf-8")
            result["article_text_file"] = str(text_path)
        manifest.append(result)

    counts: dict[str, int] = {}
    for result in manifest:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
        if result["reason"]:
            key = f"reason:{result['reason'].split(':', 1)[0]}"
            counts[key] = counts.get(key, 0) + 1

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "validation-report.json").write_text(
        json.dumps(
            {
                "input_rows": len(records),
                "meets_220_row_requirement": len(records) >= 220,
                "unique_input_ids": len({r.input_id for r in records})
                == len(records),
                "result_rows": len(manifest),
                "counts": counts,
                "email_sent": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse an EML and safely retrieve direct publisher article links."
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Complete Outlook HTML saved as .html, or an Outlook .eml file.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resolve", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    records = extract_input_rows(args.source)
    selected = records[: args.limit] if args.limit else records

    if not args.resolve:
        results = [
            {
                **asdict(record),
                "status": "not_attempted",
                "reason": "",
                "final_url": "",
                "retrieved_title": "",
                "article_text_file": "",
            }
            for record in selected
        ]
    else:
        results = retrieve_records(selected, args.workers)

    write_results(args.output_dir, selected, results)
    print(
        json.dumps(
            {
                "rows": len(selected),
                "output": str(args.output_dir),
                "resolved": sum(r["status"] == "retrieved" for r in results),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
