"""Constants for the Škola OnLine integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "skolaonline"
MANUFACTURER = "Škola OnLine"
ATTRIBUTION = "Data poskytuje Škola OnLine"

API_BASE_URL = "https://aplikace.skolaonline.cz/solapi/api"
API_CLIENT_ID = "test_client"
API_SCOPE = "openid offline_access profile sol_api"

CONF_STUDENT_ID = "student_id"
CONF_STUDENT_NAME = "student_name"

UPDATE_INTERVAL = timedelta(minutes=30)

# Rozsah rozvrhu: od začátku aktuálního týdne po konec příštího týdne.
DAYS_BEFORE = 7
DAYS_AFTER = 14
