from jit_utils.requests import get_session
from jit_utils.service_discovery import get_service_url

from src.lib.awsv4_sign_requests import sign

ENCRYPT_ENDPOINT = "{base_path}/encrypt"
DECRYPT_ENDPOINT = "{base_path}/decrypt"

_client = None


class SecretService:
    def __init__(self):
        self.base_path = get_service_url('secret-service')['service_url']

    def encrypt(self, plain: str) -> str:
        url = ENCRYPT_ENDPOINT.format(base_path=self.base_path)
        response_json = self._post(url=url, json_={"plain": plain})

        return response_json["encrypted"]

    def decrypt(self, encrypted: str) -> str:
        """The encrypted value has to be a string that can be decoded with base64"""
        # TODO: validate on client side that the encrypted value is a string that can be decoded with base64

        url = DECRYPT_ENDPOINT.format(base_path=self.base_path)
        response_json = self._post(url=url, json_={"encrypted": encrypted})

        return response_json["decrypted"]

    @staticmethod
    def _post(url: str, json_: dict) -> dict:
        """Signs the request and validates a successful response"""
        response = get_session().post(url, json=json_, auth=sign(url))
        response.raise_for_status()
        return response.json()


def get_secret_service_client() -> SecretService:
    global _client
    if _client is None:
        _client = SecretService()
    return _client
