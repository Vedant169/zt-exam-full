import hashlib, json, secrets, base64
from cryptography.fernet import Fernet

def sha3(s: str) -> str:
    return hashlib.sha3_256(s.encode()).hexdigest()

def mock_ipfs_cid(content: str) -> str:
    h = hashlib.sha256(content.encode()).hexdigest()
    return "bafybei" + h[:32]

def custody_tx(prev_tx: str, action: str, data: str) -> str:
    payload = (prev_tx or "") + action + data
    return "0x" + sha3(payload)[:16]

def generate_paper_key():
    return Fernet.generate_key().decode()

def encrypt_paper(key_str: str, paper_obj: dict) -> str:
    f = Fernet(key_str.encode())
    token = f.encrypt(json.dumps(paper_obj).encode())
    return token.decode()

def decrypt_paper(key_str: str, token_str: str) -> dict:
    f = Fernet(key_str.encode())
    data = f.decrypt(token_str.encode())
    return json.loads(data)
