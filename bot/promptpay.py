"""สร้าง QR PromptPay ตามมาตรฐาน EMVCo ของธนาคารแห่งประเทศไทย — คำนวณเองทั้งหมด ไม่ต้องพึ่ง API ภายนอก/บัญชีผู้ให้บริการใดๆ"""
import io
import re


def _tlv(id_, value):
    return f"{id_}{len(value):02d}{value}"


def _crc16(payload):
    poly = 0x1021
    crc = 0xFFFF
    for byte in payload.encode("ascii"):
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return format(crc, "04X")


def _target_field(promptpay_id):
    digits = re.sub(r"\D", "", promptpay_id)
    if len(digits) >= 13:
        return "02", digits[:13].rjust(13, "0")  # เลขบัตรประชาชน / eWallet ID
    if digits.startswith("0"):
        digits = "66" + digits[1:]
    return "01", digits.rjust(13, "0")  # เบอร์โทรศัพท์


def build_payload(promptpay_id, amount=None):
    """คืน payload string มาตรฐาน PromptPay (ยังไม่แปลงเป็นภาพ QR)"""
    type_tag, target = _target_field(promptpay_id)
    merchant_info = _tlv("00", "A000000677010111") + _tlv(type_tag, target)

    fields = [
        _tlv("00", "01"),
        _tlv("01", "12" if amount else "11"),
        _tlv("29", merchant_info),
        _tlv("53", "764"),
    ]
    if amount is not None:
        fields.append(_tlv("54", f"{amount:.2f}"))
    fields.append(_tlv("58", "TH"))

    payload_without_crc = "".join(fields) + "6304"
    return payload_without_crc + _crc16(payload_without_crc)


def build_qr_png(promptpay_id, amount=None):
    """คืน BytesIO ของภาพ QR (PNG) พร้อมส่งเป็นไฟล์แนบใน Discord"""
    import qrcode

    img = qrcode.make(build_payload(promptpay_id, amount))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
