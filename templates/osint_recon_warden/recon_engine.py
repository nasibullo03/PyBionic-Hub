import os
import sys
import re
import socket
import ssl
import json
import http.client
import urllib.parse
from datetime import datetime, timezone

def clean_target(target: str) -> str:
    target = target.strip()
    if target.startswith("http://") or target.startswith("https://"):
        parsed = urllib.parse.urlparse(target)
        target = parsed.netloc or parsed.path
    if ":" in target:
        target = target.split(":")[0]
    return target.strip("/")

def resolve_dns(domain: str) -> dict:
    domain = clean_target(domain)
    res = {"domain": domain, "ipv4": [], "ipv6": [], "cname": None, "error": None}
    try:
        addr_info = socket.getaddrinfo(domain, None)
        for item in addr_info:
            family, _, _, _, sockaddr = item
            ip = sockaddr[0]
            if family == socket.AF_INET and ip not in res["ipv4"]:
                res["ipv4"].append(ip)
            elif family == socket.AF_INET6 and ip not in res["ipv6"]:
                res["ipv6"].append(ip)
    except Exception as e:
        res["error"] = str(e)
    return res

def inspect_ssl(domain: str, port: int = 443, timeout: float = 4.0) -> dict:
    domain = clean_target(domain)
    res = {
        "domain": domain,
        "valid": False,
        "issuer": "N/A",
        "subject": "N/A",
        "expires": "N/A",
        "days_left": 0,
        "cipher": "N/A",
        "sans": [],
        "error": None
    }
    
    # Try with default context (returns full dict if valid CA)
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                cipher = ssock.cipher()
                res["cipher"] = f"{cipher[0]} ({cipher[1]})" if cipher else "Unknown"
                res["valid"] = True
                _parse_cert_dict(cert, res)
                return res
    except Exception as e:
        # Fallback to CERT_NONE to handle self-signed or unverified certs
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            with socket.create_connection((domain, port), timeout=timeout) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cipher = ssock.cipher()
                    res["cipher"] = f"{cipher[0]} ({cipher[1]})" if cipher else "Unknown"
                    res["valid"] = True
                    res["issuer"] = "Self-signed / Unverified CA"
                    res["subject"] = domain
                    return res
        except Exception as e2:
            res["error"] = str(e2)
    return res

def _parse_cert_dict(cert: dict, res: dict):
    if not cert:
        return
    for item in cert.get("subject", ()):
        for k, v in item:
            if k == "commonName":
                res["subject"] = v
    for item in cert.get("issuer", ()):
        for k, v in item:
            if k in ("organizationName", "commonName"):
                res["issuer"] = v
    not_after = cert.get("notAfter")
    if not_after:
        try:
            exp_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            now_dt = datetime.now(timezone.utc)
            res["expires"] = exp_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            res["days_left"] = max(0, (exp_dt - now_dt).days)
        except Exception:
            res["expires"] = str(not_after)
    sans = [x[1] for x in cert.get("subjectAltName", ()) if x[0] == "DNS"]
    res["sans"] = sans[:8]

def inspect_security_headers(domain: str, timeout: float = 4.0) -> dict:
    domain = clean_target(domain)
    res = {
        "domain": domain,
        "status": None,
        "headers": {},
        "hsts": False,
        "csp": False,
        "x_frame_options": False,
        "x_content_type": False,
        "referrer_policy": False,
        "score": 0,
        "error": None
    }
    try:
        conn = http.client.HTTPSConnection(domain, timeout=timeout)
        conn.request("HEAD", "/", headers={"User-Agent": "OSINT-Recon-Warden/1.0"})
        resp = conn.getresponse()
        res["status"] = resp.status
        headers = {k.lower(): v for k, v in resp.getheaders()}
        res["headers"] = headers
        
        score = 0
        if "strict-transport-security" in headers:
            res["hsts"] = True
            score += 25
        if "content-security-policy" in headers:
            res["csp"] = True
            score += 30
        if "x-frame-options" in headers:
            res["x_frame_options"] = True
            score += 15
        if "x-content-type-options" in headers:
            res["x_content_type"] = True
            score += 15
        if "referrer-policy" in headers:
            res["referrer_policy"] = True
            score += 15
        res["score"] = score
        conn.close()
    except Exception as e:
        res["error"] = str(e)
    return res

def full_recon(domain: str) -> dict:
    domain = clean_target(domain)
    dns = resolve_dns(domain)
    ssl_info = inspect_ssl(domain)
    sec_hdrs = inspect_security_headers(domain)
    
    score = sec_hdrs.get("score", 0)
    if ssl_info.get("valid"):
        score = min(100, score + 10)
    
    if score >= 80:
        badge = f"🛡🛡🛡 Отлично ({score}/100 - Grade A)"
    elif score >= 50:
        badge = f"🛡🛡 Хорошо ({score}/100 - Grade B)"
    elif score >= 20:
        badge = f"⚠️ Средне ({score}/100 - Grade C)"
    else:
        badge = f"❌ Слабо ({score}/100 - Grade F)"

    return {
        "target": domain,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dns": dns,
        "ssl": ssl_info,
        "headers": sec_hdrs,
        "security_score": score,
        "score_badge": badge
    }

if __name__ == "__main__":
    t = "github.com"
    r = full_recon(t)
    print("Recon result for:", t)
    print("IPv4:", r["dns"]["ipv4"])
    print("SSL Issuer:", r["ssl"]["issuer"], "Expires:", r["ssl"]["expires"])
    print("Security Score:", r["security_score"], r["score_badge"])
