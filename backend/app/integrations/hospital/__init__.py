"""Isolated hospital integration: client, contract and policy."""
from .errors import ERROR_MESSAGES, REASON_MESSAGES, HospitalError
from .schemas import LIMA, PatientIdentity
from .client import HospitalClient, hospital_client

__all__ = [
    "ERROR_MESSAGES",
    "REASON_MESSAGES",
    "HospitalError",
    "LIMA",
    "PatientIdentity",
    "HospitalClient",
    "hospital_client",
]
