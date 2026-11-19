"""COSMO 公開帳號與 Objekt metadata 查詢及欄位轉換。"""

import json
import re
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


BASE_URL = "https://api.cosmo.fans"
TIMEOUT_SECONDS = 20


def _get_json(path: str) -> dict:
    request = Request(
        BASE_URL + path,
        headers={
            "User-Agent": "COSMO-Collector-Copilot/0.1",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        data = json.load(response)
    if not isinstance(data, dict):
        raise ValueError("COSMO 沒有回傳預期的 JSON 物件。")
    return data


def fetch_public_account(username: str) -> dict:
    """以暱稱取得公開帳號；回傳暱稱和錢包地址，不包含持有清單。"""
    if not username or username != username.strip():
        raise ValueError("請輸入不含前後空白的 COSMO ID。")
    data = _get_json(f"/bff/v3/users/by-nickname/{quote(username, safe='')}")
    nickname = data.get("nickname")
    address = data.get("address")
    if not isinstance(nickname, str) or nickname.casefold() != username.casefold():
        raise ValueError("COSMO 回報的暱稱與要求的帳號不一致。")
    if not isinstance(address, str) or not re.fullmatch(r"0x[0-9a-fA-F]{40}", address):
        raise ValueError("COSMO 回報的錢包地址格式不正確。")
    return {"nickname": nickname, "address": address}


def fetch_objekt_metadata(token_id: str) -> dict:
    """取得指定 Token ID 的 metadata；此資料不能證明目前持有人。"""
    if not re.fullmatch(r"[0-9]+", token_id):
        raise ValueError("Token ID 必須是由數字組成的字串。")
    return _get_json(f"/bff/v3/objekts/nft-metadata/{token_id}")


def normalize_objekt_metadata(token_id: str, raw: dict) -> dict:
    """將官方 metadata 整理成圖鑑使用的卡片欄位。"""
    attributes = raw.get("attributes")
    if not isinstance(attributes, list):
        raise ValueError("卡片資料缺少 attributes 清單。")

    traits = {}
    member_values = []
    required = ("Artist", "Season", "Collection", "Class")
    for attribute in attributes:
        if not isinstance(attribute, dict):
            raise ValueError("卡片 attributes 內有無效的紀錄。")
        key = attribute.get("trait_type")
        if key == "Member":
            member_values.append(attribute.get("value"))
        if key in required:
            if key in traits:
                raise ValueError(f"卡片的 {key} 欄位重複，無法確定正確資料。")
            traits[key] = attribute.get("value")
    for key in required:
        if not isinstance(traits.get(key), str) or not traits[key].strip():
            raise ValueError(f"卡片缺少有效的 {key} 欄位。")

    if not member_values or any(not isinstance(value, str) or not value.strip() for value in member_values):
        raise ValueError("卡片缺少有效的 Member 欄位。")
    member_values = list(dict.fromkeys(member_values))
    unit_labels = [value for value in member_values if re.search(r"\s[xX]\s", value)]
    if traits["Class"] == "Unit" and unit_labels:
        if len(unit_labels) != 1:
            raise ValueError("組合卡含多個不同的組合名稱，無法確定卡款。")
        member_label = unit_labels[0]
        members = [value for value in member_values if value != member_label] or [member_label]
    else:
        member_label = " + ".join(member_values)
        members = member_values

    name = raw.get("name")
    image_url = raw.get("image")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("卡片缺少有效的名稱。")
    if not isinstance(image_url, str):
        raise ValueError("卡片缺少圖片網址。")
    image = urlparse(image_url)
    if image.scheme != "https" or not image.netloc:
        raise ValueError("卡片圖片必須使用有效的 HTTPS 網址。")

    return {
        "external_token_id": token_id,
        "name": name,
        "artist": traits["Artist"],
        "member": member_label,
        "members": members,
        "season": traits["Season"],
        "collection_code": traits["Collection"],
        "class_name": traits["Class"],
        "image_url": image_url,
    }
