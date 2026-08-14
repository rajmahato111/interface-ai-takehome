MEMBERS = {
    "100234": {
        "name": "Jane Doe",
        "status": "active",
        "savings_balance": "$4,215.60",
        "checking_balance": "$812.04",
        "ssn_display": "•••-••-4412",  # masked; raw SSN never rendered
    },
    "100235": {
        "name": "Robert Chen",
        "status": "dormant",
        "savings_balance": "$1,002.00",
        "checking_balance": "$44.10",
        "ssn_display": "•••-••-7781",
    },
}

USERS = {
    "teller": {"password": "teller", "role": "teller"},
    "denied_user": {"password": "teller", "role": "denied"},
}
