# Synthetic PII corpus. Artifacts and logs must not contain these strings.
SSN_SAMPLE = "078-05-1120"
PAN_SAMPLE = "4111111111111111"
EMAIL_SAMPLE = "jane.doe@summit.example"
PHONE_SAMPLE = "415-555-0199"
BEARER_SAMPLE = "Bearer supersecrettokenvalue"
ACCOUNT_SAMPLE = "123456789012"
PASSWORD_SAMPLE = "teller-should-not-appear-as-raw-secret-in-logs"
CORPUS = [
    SSN_SAMPLE,
    PAN_SAMPLE,
    EMAIL_SAMPLE,
    PHONE_SAMPLE,
    BEARER_SAMPLE,
]
