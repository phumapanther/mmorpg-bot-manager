from bot import promptpay


def _parse_tlv(payload):
    i = 0
    fields = {}
    while i < len(payload):
        tag = payload[i:i + 2]
        length = int(payload[i + 2:i + 4])
        value = payload[i + 4:i + 4 + length]
        fields[tag] = value
        i += 4 + length
    assert i == len(payload)
    return fields


def test_crc_is_self_consistent():
    payload = promptpay.build_payload("0812345678", 100.0)
    body, crc = payload[:-4], payload[-4:]
    assert promptpay._crc16(body) == crc


def test_phone_number_target_field():
    fields = _parse_tlv(promptpay.build_payload("0812345678", 100.0))
    assert fields["29"].endswith("0066812345678")
    assert fields["54"] == "100.00"
    assert fields["58"] == "TH"


def test_national_id_target_field_and_no_amount():
    fields = _parse_tlv(promptpay.build_payload("1234567890123", None))
    assert fields["29"].endswith("1234567890123")
    assert "54" not in fields
    assert fields["01"] == "11"  # static (no amount) point-of-initiation


def test_qr_png_bytes_generated():
    buf = promptpay.build_qr_png("0812345678", 50.0)
    assert buf.read(8)[:4] == b"\x89PNG"
