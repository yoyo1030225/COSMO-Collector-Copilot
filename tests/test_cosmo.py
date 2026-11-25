import copy
import unittest
from unittest.mock import patch

from cosmo import fetch_objekt_metadata, fetch_public_account, normalize_objekt_metadata


def sample_metadata():
    return {
        "name": "Cream02 Kotone 114Z #1001",
        "image": "https://resources.cosmo.fans/images/example.webp",
        "attributes": [
            {"trait_type": "Artist", "value": "tripleS"},
            {"trait_type": "Member", "value": "Kotone"},
            {"trait_type": "Season", "value": "Cream02"},
            {"trait_type": "Collection", "value": "114Z"},
            {"trait_type": "Class", "value": "First"},
        ],
    }


class CosmoMetadataTests(unittest.TestCase):
    def test_preserves_unit_label_and_each_individual_member(self):
        raw = sample_metadata()
        raw["attributes"] = [
            {"trait_type": "Artist", "value": "tripleS"},
            {"trait_type": "Class", "value": "Unit"},
            {"trait_type": "Member", "value": "ChaeYeon"},
            {"trait_type": "Member", "value": "JooBin"},
            {"trait_type": "Member", "value": "S4 X S18"},
            {"trait_type": "Season", "value": "Cream02"},
            {"trait_type": "Collection", "value": "601A"},
        ]
        card = normalize_objekt_metadata("1002", raw)
        self.assertEqual(card["member"], "S4 X S18")
        self.assertEqual(card["members"], ["ChaeYeon", "JooBin"])
        self.assertEqual(card["collection_code"], "601A")

    def test_preserves_season_code_and_token_without_inventing_serial_or_owner(self):
        card = normalize_objekt_metadata("1001", sample_metadata())

        self.assertEqual(card["external_token_id"], "1001")
        self.assertEqual(card["season"], "Cream02")
        self.assertEqual(card["collection_code"], "114Z")
        self.assertEqual(card["member"], "Kotone")
        self.assertNotIn("serial_number", card)
        self.assertNotIn("owner", card)
        self.assertNotIn("transferable", card)

    def test_does_not_modify_the_official_response(self):
        raw = sample_metadata()
        original = copy.deepcopy(raw)

        result = normalize_objekt_metadata("1001", raw)

        self.assertEqual(raw, original)
        self.assertIsNot(result, raw)

    def test_rejects_missing_or_duplicate_required_traits(self):
        for attributes in (
            sample_metadata()["attributes"][:-1],
            sample_metadata()["attributes"] + [{"trait_type": "Season", "value": "Other"}],
            None,
        ):
            with self.subTest(attributes=attributes):
                raw = sample_metadata()
                raw["attributes"] = attributes
                with self.assertRaises(ValueError):
                    normalize_objekt_metadata("1001", raw)

    def test_rejects_invalid_name_image_and_trait_values(self):
        for field, value in (("name", ""), ("image", "javascript:alert(1)"), ("image", None)):
            with self.subTest(field=field, value=value):
                raw = sample_metadata()
                raw[field] = value
                with self.assertRaises(ValueError):
                    normalize_objekt_metadata("1001", raw)
        raw = sample_metadata()
        raw["attributes"][0]["value"] = False
        with self.assertRaises(ValueError):
            normalize_objekt_metadata("1001", raw)

    def test_rejects_invalid_token_before_sending_a_request(self):
        with patch("cosmo._get_json") as get_json:
            with self.assertRaises(ValueError):
                fetch_objekt_metadata("../users")
            get_json.assert_not_called()


class CosmoAccountTests(unittest.TestCase):
    def test_returns_only_the_matched_public_nickname_and_address(self):
        raw = {
            "nickname": "example",
            "address": "0x1111111111111111111111111111111111111111",
            "guid": "unused-identifier",
            "profileImageUrl": "https://example.com/profile.webp",
        }
        with patch("cosmo._get_json", return_value=raw) as get_json:
            result = fetch_public_account("example")

        self.assertEqual(set(result), {"nickname", "address"})
        get_json.assert_called_once_with("/bff/v3/users/by-nickname/example")

    def test_rejects_mismatched_nickname_or_invalid_wallet(self):
        for raw in (
            {"nickname": "another-user", "address": "0x" + "1" * 40},
            {"nickname": "example", "address": "invalid"},
        ):
            with self.subTest(raw=raw):
                with patch("cosmo._get_json", return_value=raw):
                    with self.assertRaises(ValueError):
                        fetch_public_account("example")
