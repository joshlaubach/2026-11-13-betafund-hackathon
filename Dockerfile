# API image: FastAPI server for Echo (port 8000). No dev or test packages, no .env, no secrets.
# The API key is passed at runtime by docker compose, never at build time.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system --gid 10001 echoapp \
    && useradd --system --uid 10001 --gid echoapp --home-dir /app --shell /usr/sbin/nologin echoapp

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

# Only what the server imports: core/, server/, scripts/audit_bank.py (bank audit used by core),
# scripts/demo_worksheet.py (worksheet mode wiring imported by server/worksheet_api.py),
# scripts/gate_power_rule.py (gate run below), the bank file, and the saved replays.
COPY core/ ./core/
COPY server/ ./server/
COPY scripts/audit_bank.py scripts/demo_worksheet.py scripts/gate_power_rule.py ./scripts/
COPY docs/verified_problems.json ./docs/
COPY --chown=echoapp:echoapp replay/ ./replay/

# One-time gate: writes build/gate_power_rule.json bound to the bank's SHA-256.
# The build fails unless the gate prints GATE: ENABLED (exit 0).
RUN python scripts/gate_power_rule.py > /tmp/gate.txt 2>&1; status=$?; cat /tmp/gate.txt; \
    test "$status" -eq 0 && grep -qx "GATE: ENABLED" /tmp/gate.txt \
    && rm -f /tmp/gate.txt

USER echoapp

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
