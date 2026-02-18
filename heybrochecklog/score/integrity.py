# Log Integrity Checker
# Glorified modification to make use of latest pprp and python 3.9 :)
# Source from https://github.com/puddly/eac_logsigner/blob/master/eac.py

from pprp.crypto import rijndael

# Type hinting
from typing import Literal, Tuple, Optional, Union


def eac_checksum(text: str) -> str:
    # Ignore newlines
    text = text.replace('\r', '').replace('\n', '')

    # Fuzzing reveals BOMs are also ignored
    text = text.replace('\ufeff', '').replace('\ufffe', '')

    # Setup Rijndael-256 with a 256-bit blocksize
    cipher = rijndael(
        # Probably SHA256('super secret password') but it doesn't actually matter
        key=bytes.fromhex(
            '9378716cf13e4265ae55338e940b376184da389e50647726b35f6f341ee3efd9'
        ),
        block_size=256 // 8,
    )

    # Encode the text as UTF-16-LE
    plaintext = text.encode('utf-16-le')

    # The IV is all zeroes so we don't have to handle it
    signature = b'\x00' * 32

    # Process it block-by-block
    for i in range(0, len(plaintext), 32):
        # Zero-pad the last block, if necessary
        plaintext_block = plaintext[i : i + 32].ljust(32, b'\x00')

        # CBC mode (XOR the previous ciphertext block into the plaintext)
        cbc_plaintext = bytes(
            (ord_or_int(a)) ^ (ord_or_int(b))
            for a, b in zip(signature, plaintext_block)
        )

        # New signature is the ciphertext.
        signature = cipher.encrypt(cbc_plaintext)
    
    assert isinstance(signature, str) # Should be always ok since plaintext is of non-zero length 
    raw_signature = bytes(signature, "utf-16-le").hex().upper()
    signature = ""

    for i in range(0, len(raw_signature), 4):
        signature += raw_signature[i : i + 2]

    # Textual signature is just the hex representation
    return signature


def ord_or_int(data: Union[int, str]) -> int:
    if isinstance(data, int):
        return data

    assert isinstance(data, str)
    assert len(data) == 1

    return ord(data)


def extract_info(text: str) -> Tuple[str, Optional[str]]:
    if '\r\n\r\n==== Log checksum' not in text:
        signature = None
    else:
        text, signature_parts = text.split('\r\n\r\n==== Log checksum', 1)
        signature = signature_parts.split()[0].strip()

    return text, signature


def eac_verify(text: str) -> Tuple[Optional[str], str]:
    # Strip off BOM
    if text.startswith('\ufeff'):
        text = text[1:]

    # Null bytes screw it up
    if '\x00' in text:
        text = text[: text.index('\x00')]

    unsigned_text, old_signature = extract_info(text)
    return old_signature, eac_checksum(unsigned_text)


def check_integrity(
    text: str,
) -> Literal["LOG_CHECKSUM_NOT_PRESENT", "LOG_OK", "LOG_NOT_OK"]:
    text = text.replace('\n', '\r\n')  # dunno
    old_signature, actual_signature = eac_verify(text)

    if old_signature is None:
        return "LOG_CHECKSUM_NOT_PRESENT"

    if old_signature == actual_signature:
        return "LOG_OK"

    return "LOG_NOT_OK"
