import urllib.request
import json
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]

FIRMS = [
    "JMI Equity", "PSG", "Accel-KKR", "Great Hill Partners", "Summit Partners",
    "Audax Private Equity", "STG Partners", "Mainsail Partners", "Insight Partners",
    "Spectrum Equity", "McCarthy Capital", "Bregal Sagemount", "Serent Capital",
    "Inverness Graham", "Parker Gale", "Performant Capital", "Rubicon Technology Partners",
    "TPG Growth", "Blackstone Growth", "Sixth Street Growth", "Silversmith Capital Partners",
    "Sageview Capital", "Battery Ventures", "Long Ridge Equity Partners", "Five Elms Capital",
    "Kayne Partners", "Brighton Park Capital", "General Catalyst", "K1 Investment Management",
    "LLR Partners", "Susquehanna Growth Equity", "Lone View Capital", "True Wind Capital"
]

VERTICALS = [
    "Robotics", "Internet of Things", "Advanced Sensors", "Industrial Technology",
    "Sustainability", "Energy Management"
]

today         = datetime.now().strftime("%B %d, %Y")
firm_list     = ", ".join(FIRMS)
vertical_list = ", ".join(VERTICALS)

prompt = (
    "You are a financial news analyst specializing in private equity and growth equity "
    "acquisitions of technology companies. Today's date is " + today + ".\n\n"
    "Search ONLY for acquisition announcements made in the last 30 days by these investment "
    "firms acquiring middle-market software, technology, or hardware companies. "
    "Do not include deals older than 30 days.\n\n"
    "Firms to track: " + firm_list + "\n\n"
    "Target verticals (prioritize these): " + vertical_list + "\n\n"
    "Return ONLY a valid JSON array — no preamble, no markdown, no explanation. "
    "Each object must have exactly these fields:\n"
    "- company: string (acquired company name)\n"
    "- firm: string (acquiring firm)\n"
    "- date: string (e.g. April 2025)\n"
    "- description: string (one sentence: what the company does)\n"
    "- verticals: array of strings, pick only from: Robotics, Internet of Things, "
    "Advanced Sensors, Industrial Technology, Sustainability, Energy Management, "
    "Enterprise SaaS, Cybersecurity, FinTech, Healthcare IT\n"
    "- source: string (news URL or empty string)\n"
    "- isNew: boolean (always true since we only want last 30 days)\n\n"
    "Return a maximum of 2 deals per firm. Include all firms that have made acquisitions "
    "in the past 30 days. Only include deals you can verify from a news source."
)

payload = json.dumps({
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 4000,
    "tools": [{"type": "web_search_20250305", "name": "web_search"}],
    "messages": [{"role": "user", "content": prompt}]
}).encode("utf-8")

req = urllib.request.Request(
    "https://api.anthropic.com/v1/messages",
    data=payload,
    headers={
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
    },
    method="POST"
)

print("Calling Anthropic API...")
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode("utf-8"))

text  = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
start = text.find("[")
end   = text.rfind("]")

deals = []
if start != -1:
    json_str = text[start:end + 1] if end != -1 else text[start:]
    try:
        deals = json.loads(json_str)
    except json.JSONDecodeError:
        last = json_str.rfind("}")
        if last != -1:
            deals = json.loads(json_str[:last + 1] + "]")

print("Found " + str(len(deals)) + " deals")

if not deals:
    print("No deals found — skipping email.")
    exit(0)

# Sort: target vertical deals first
target   = set(VERTICALS)
priority = [d for d in deals if any(v in target for v in d.get("verticals", []))]
other    = [d for d in deals if d not in priority]
deals    = priority + other

# ── HTML helpers ──────────────────────────────────────────────────────────────

BADGE_COLORS = {
    "Robotics":              ("#E1F5EE", "#0F6E56"),
    "Internet of Things":    ("#E1F5EE", "#0F6E56"),
    "Advanced Sensors":      ("#E1F5EE", "#0F6E56"),
    "Industrial Technology": ("#E1F5EE", "#0F6E56"),
    "Sustainability":        ("#E1F5EE", "#0F6E56"),
    "Energy Management":     ("#E1F5EE", "#0F6E56"),
}
DEFAULT_BADGE = ("#EEEDFE", "#3C3489")


def badge(v):
    bg, fg = BADGE_COLORS.get(v, DEFAULT_BADGE)
    return (
        '<span style="background:' + bg + ';color:' + fg + ';font-size:11px;'
        'padding:3px 9px;border-radius:99px;font-weight:500;margin-right:4px;">'
        + v + '</span>'
    )


def deal_card(d):
    badges      = "".join(badge(v) for v in d.get("verticals", []))
    source_link = (
        ' &nbsp;<a href="' + d["source"] + '" style="font-size:12px;color:#0C447C;">Source</a>'
        if d.get("source") else ""
    )
    return (
        '<div style="background:#ffffff;border:1px solid #e5e5e3;border-radius:12px;'
        'padding:16px 20px;margin-bottom:12px;">'
        '<div style="font-size:15px;font-weight:600;color:#1a1a18;">' + d.get("company", "") + '</div>'
        '<div style="font-size:13px;color:#6b6b67;margin-top:2px;">Acquired by <strong>'
        + d.get("firm", "") + '</strong></div>'
        '<div style="font-size:13px;color:#6b6b67;margin-top:8px;line-height:1.5;">'
        + d.get("description", "") + '</div>'
        '<div style="margin-top:10px;">' + badges
        + '<span style="background:#f5f5f4;color:#6b6b67;font-size:11px;'
        'padding:3px 9px;border-radius:99px;">' + d.get("date", "") + '</span>'
        + source_link + '</div></div>'
    )


def section_header(label, color):
    return (
        '<div style="font-size:11px;font-weight:500;color:' + color + ';'
        'text-transform:uppercase;letter-spacing:0.06em;margin:20px 0 10px;">'
        + label + '</div>'
    )


priority_cards = "".join(deal_card(d) for d in priority)
other_cards    = "".join(deal_card(d) for d in other)

priority_section = (section_header("Target Verticals", "#0F6E56") + priority_cards) if priority else ""
other_section    = (section_header("Other Software Deals", "#6b6b67") + other_cards)  if other    else ""

html_body = (
    '<div style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;'
    'max-width:680px;margin:0 auto;background:#f5f5f4;padding:24px 16px;">'

    '<div style="background:#ffffff;border-radius:16px;padding:28px 28px 16px;margin-bottom:16px;">'
    '<div style="font-size:20px;font-weight:600;color:#1a1a18;">PE Acquisition Digest</div>'
    '<div style="font-size:13px;color:#6b6b67;margin-top:4px;">' + today + ' &nbsp;&middot;&nbsp; Last 30 days</div>'

    '<div style="display:flex;gap:16px;margin-top:16px;flex-wrap:wrap;">'
    '<div style="background:#f5f5f4;border-radius:8px;padding:10px 16px;min-width:100px;">'
    '<div style="font-size:11px;color:#6b6b67;text-transform:uppercase;">Total deals</div>'
    '<div style="font-size:24px;font-weight:500;color:#1a1a18;">' + str(len(deals)) + '</div></div>'

    '<div style="background:#E1F5EE;border-radius:8px;padding:10px 16px;min-width:100px;">'
    '<div style="font-size:11px;color:#0F6E56;text-transform:uppercase;">Target verticals</div>'
    '<div style="font-size:24px;font-weight:500;color:#0F6E56;">' + str(len(priority)) + '</div></div>'

    '<div style="background:#EEEDFE;border-radius:8px;padding:10px 16px;min-width:100px;">'
    '<div style="font-size:11px;color:#3C3489;text-transform:uppercase;">Other software</div>'
    '<div style="font-size:24px;font-weight:500;color:#3C3489;">' + str(len(other)) + '</div></div>'
    '</div></div>'

    + priority_section
    + other_section

    + '<div style="font-size:12px;color:#a0a09a;text-align:center;margin-top:24px;'
    'padding-top:16px;border-top:1px solid #e5e5e3;">'
    'PE Acquisition Tracker &nbsp;&middot;&nbsp; Powered by Claude</div>'
    '</div>'
)

# Plain text fallback
text_lines = ["PE Acquisition Digest -- " + today, "=" * 40, ""]
for d in deals:
    text_lines.append(d.get("company", "") + " -- " + d.get("firm", ""))
    text_lines.append(d.get("description", ""))
    text_lines.append(d.get("date", "") + "  " + d.get("source", ""))
    text_lines.append("")
text_body = "\n".join(text_lines)

# ── Send email ────────────────────────────────────────────────────────────────
msg = MIMEMultipart("alternative")
msg["Subject"] = "PE Digest: " + str(len(deals)) + " deals found -- " + today
msg["From"]    = GMAIL_USER
msg["To"]      = GMAIL_USER
msg.attach(MIMEText(text_body, "plain"))
msg.attach(MIMEText(html_body, "html"))

print("Sending email to " + GMAIL_USER + "...")
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())

print("Email sent successfully.")
