"""
WeChat Work (WeCom) Cryptography Utilities

Provides functions for:
- URL verification (signature computation)
- Message encryption/decryption (AES)
- XML message parsing

Extracted from msg_receive.py for reusability.
"""

import hashlib
import base64
import xml.etree.ElementTree as ET
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from typing import Dict, Any


def compute_signature(token: str, timestamp: str, nonce: str, encrypt: str) -> str:
    """
    Compute signature for WeCom callback verification

    Args:
        token: Verification token
        timestamp: Timestamp from WeCom
        nonce: Nonce from WeCom
        encrypt: Encrypted message

    Returns:
        SHA1 signature (hex string)

    Example:
        sig = compute_signature("token123", "1234567890", "random123", "encrypted_data")
    """
    # Sort parameters lexicographically
    params = [token, timestamp, nonce, encrypt]
    params.sort()

    # Concatenate parameters
    raw_string = ''.join(params)

    # Compute SHA1 hash
    sha1 = hashlib.sha1()
    sha1.update(raw_string.encode('utf-8'))
    return sha1.hexdigest()


def decrypt_message(encrypt_str: str, encoding_aes_key: str, corp_id: str) -> str:
    """
    Decrypt message from WeCom

    Args:
        encrypt_str: Base64-encoded encrypted message
        encoding_aes_key: AES key (43 chars, will be padded to 44 with '=')
        corp_id: Enterprise ID (for verification)

    Returns:
        Decrypted message (UTF-8 string)

    Raises:
        ValueError: If corp_id doesn't match or decryption fails

    Example:
        msg = decrypt_message(
            encrypt_str="base64_encrypted_data",
            encoding_aes_key="eF0rmkgB8rtBUGvXVOF5NnV0v5MoVquJQY45wUdXTax",
            corp_id="ww33e8813b380a21b9"
        )
    """
    # Decode base64 (add padding if necessary)
    aes_key = base64.b64decode(encoding_aes_key + '=')
    encrypt_bytes = base64.b64decode(encrypt_str)

    # Extract IV (first 16 bytes of AES key)
    iv = aes_key[:16]

    # Decrypt using AES-CBC
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted = decryptor.update(encrypt_bytes) + decryptor.finalize()

    # Remove PKCS#7 padding
    pad = decrypted[-1]
    if isinstance(pad, int):
        decrypted = decrypted[:-pad]
    else:
        decrypted = decrypted[:-ord(pad)]

    # Extract message length (4 bytes after 16-byte random prefix)
    msg_len = int.from_bytes(decrypted[16:20], byteorder='big')

    # Extract message content
    msg = decrypted[20:20 + msg_len].decode('utf-8')

    # Extract and verify CorpID
    received_corp_id = decrypted[20 + msg_len:20 + msg_len + len(corp_id)].decode('utf-8')
    if received_corp_id != corp_id:
        raise ValueError(
            f"CorpID mismatch: expected {corp_id}, got {received_corp_id}"
        )

    return msg


def verify_url(msg_signature: str, timestamp: str, nonce: str, echo_str: str,
               token: str, encoding_aes_key: str, corp_id: str) -> str:
    """
    Verify callback URL during WeCom URL validation

    Args:
        msg_signature: Signature from WeCom
        timestamp: Timestamp from WeCom
        nonce: Nonce from WeCom
        echo_str: Encrypted echo string from WeCom
        token: Verification token (from config)
        encoding_aes_key: AES key (from config)
        corp_id: Enterprise ID (from config)

    Returns:
        Decrypted echo string to return to WeCom

    Raises:
        ValueError: If signature verification fails

    Example:
        echo = verify_url(
            msg_signature="abc123",
            timestamp="1234567890",
            nonce="random",
            echo_str="encrypted_echo",
            token="uahVGvONDc7cUx",
            encoding_aes_key="eF0rmkgB8rtBUGvXVOF5NnV0v5MoVquJQY45wUdXTax",
            corp_id="ww33e8813b380a21b9"
        )
    """
    # Compute signature
    signature = compute_signature(token, timestamp, nonce, echo_str)

    # Verify signature
    if signature != msg_signature:
        raise ValueError(
            f"Signature verification failed: expected {msg_signature}, got {signature}"
        )

    # Decrypt echo string
    return decrypt_message(echo_str, encoding_aes_key, corp_id)


def parse_message(xml_content: str) -> Dict[str, Any]:
    """
    Parse XML message from WeCom

    Args:
        xml_content: XML string from WeCom

    Returns:
        Dictionary of message data (tag name → text content)

    Example:
        message = parse_message("<xml><MsgType>text</MsgType><Content>Hello</Content></xml>")
        # Returns: {'MsgType': 'text', 'Content': 'Hello'}
    """
    root = ET.fromstring(xml_content)
    message = {}

    for child in root:
        message[child.tag] = child.text

    return message


__all__ = [
    'compute_signature',
    'decrypt_message',
    'verify_url',
    'parse_message'
]
