#!/usr/bin/env python3
"""Patch production nginx site for long-lived /assess/stream SSE."""
from pathlib import Path

path = Path("/etc/nginx/sites-enabled/greenmeansgo.ai")
text = path.read_text()
Path("/tmp/greenmeansgo.ai.nginx.bak").write_text(text)

if "proxy_buffering off" in text and "assess/stream" in text:
    print("Already patched")
    raise SystemExit(0)

old_proxy = (
    "    proxy_redirect off;\n"
    "    proxy_read_timeout 300;\n"
    "    proxy_connect_timeout 300;\n"
    "    proxy_send_timeout 300;\n"
    "\n"
    "    # API endpoints\n"
    "    location /api/ {"
)

new_proxy = (
    "    proxy_redirect off;\n"
    "    proxy_http_version 1.1;\n"
    '    proxy_set_header Connection "";\n'
    "    proxy_read_timeout 1800;\n"
    "    proxy_connect_timeout 60;\n"
    "    proxy_send_timeout 1800;\n"
    "\n"
    "    # Long-lived SSE assessment streams (must stay ahead of /api/)\n"
    r"    location ~ ^/api/(assess/stream|processing/assess/stream)$ {"
    "\n"
    "        limit_req zone=api_limit burst=5 nodelay;\n"
    "        limit_conn conn_limit 10;\n"
    "        proxy_buffering off;\n"
    "        proxy_cache off;\n"
    "        proxy_read_timeout 1800;\n"
    "        proxy_send_timeout 1800;\n"
    r"        rewrite ^/api/(.*)$ /$1 break;"
    "\n"
    "        proxy_pass http://fastapi_backend;\n"
    "    }\n"
    "\n"
    "    # API endpoints\n"
    "    location /api/ {"
)

if old_proxy not in text:
    raise SystemExit("Expected proxy block not found; aborting")

text = text.replace(old_proxy, new_proxy, 1)

old_assess = (
    "    location ~ ^/assess/(.*)$ {\n"
    "        limit_req zone=api_limit burst=5 nodelay;\n"
    "        proxy_pass http://fastapi_backend;\n"
    "    }"
)
new_assess = (
    "    location ~ ^/assess/(.*)$ {\n"
    "        limit_req zone=api_limit burst=5 nodelay;\n"
    "        proxy_buffering off;\n"
    "        proxy_cache off;\n"
    "        proxy_read_timeout 1800;\n"
    "        proxy_send_timeout 1800;\n"
    "        proxy_pass http://fastapi_backend;\n"
    "    }"
)
if old_assess in text:
    text = text.replace(old_assess, new_assess, 1)

path.write_text(text)
print("Patched nginx config")
