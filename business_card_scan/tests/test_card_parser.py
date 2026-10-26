# -*- coding: utf-8 -*-
"""Tests de l'analyseur, exécutables sans Odoo :
    cd <dossier contenant business_card_scan>
    python3 business_card_scan/tests/test_card_parser.py
"""
import importlib.util
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "card_parser", os.path.join(_HERE, "..", "models", "card_parser.py")
)
card_parser = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(card_parser)
parse_card_text = card_parser.parse_card_text


class TestCardParser(unittest.TestCase):

    def test_moroccan_card(self):
        text = """
        STREAM INDUSTRY SARL
        Youssef El Amrani
        Directeur Commercial
        Tél : +212 5 22 33 44 55
        GSM : 06 61 23 45 67
        y.elamrani @ streamindustry . ma
        www.streamindustry.ma
        12, Rue Ibn Battouta, Casablanca
        """
        r = parse_card_text(text)
        self.assertEqual(r["email"], "y.elamrani@streamindustry.ma")
        self.assertEqual(r["contact_name"], "Youssef El Amrani")
        self.assertEqual(r["function"], "Directeur Commercial")
        self.assertEqual(r["partner_name"], "STREAM INDUSTRY SARL")
        self.assertEqual(r["phone"], "06 61 23 45 67")
        self.assertEqual(r["phone_2"], "+212 5 22 33 44 55")
        self.assertEqual(r["website"], "https://www.streamindustry.ma")
        self.assertIn("Rue Ibn Battouta", r["street"])

    def test_english_card_company_from_domain(self):
        text = """
        Sarah Johnson
        Senior Software Engineer
        sarah.johnson@acmerobotics.com
        +1 (514) 555-0199
        Fax: +1 (514) 555-0100
        """
        r = parse_card_text(text)
        self.assertEqual(r["contact_name"], "Sarah Johnson")
        self.assertEqual(r["function"], "Senior Software Engineer")
        self.assertEqual(r["phone"], "+1 (514) 555-0199")
        self.assertFalse(r["phone_2"])  # le fax est ignoré
        self.assertEqual(r["partner_name"], "Acmerobotics")

    def test_uppercase_name_and_gmail(self):
        text = """
        KARIM BENNANI
        Consultant ERP Odoo
        karim.bennani@gmail.com
        0661-112233
        """
        r = parse_card_text(text)
        self.assertEqual(r["contact_name"], "Karim Bennani")
        self.assertEqual(r["function"], "Consultant ERP Odoo")
        self.assertFalse(r["partner_name"])  # gmail n'est pas une société
        self.assertEqual(r["email"], "karim.bennani@gmail.com")

    def test_canadian_english_card(self):
        text = """
        NORTHWIND LOGISTICS INC.
        Michael O'Brien
        Vice President, Business Development
        T: +1 416 555 0142
        M: +1 647 555 0198
        F: +1 416 555 0100
        E: mobrien@northwind.ca
        W: www.northwind.ca
        250 King Street West, Suite 400
        Toronto, ON M5H 1J9
        """
        r = parse_card_text(text)
        self.assertEqual(r["partner_name"], "NORTHWIND LOGISTICS INC.")
        self.assertEqual(r["contact_name"], "Michael O'Brien")
        self.assertEqual(r["function"], "Vice President, Business Development")
        self.assertEqual(r["phone"], "+1 647 555 0198")  # M: = mobile en premier
        self.assertEqual(r["phone_2"], "+1 416 555 0142")  # le fax F: est ignoré
        self.assertEqual(r["email"], "mobrien@northwind.ca")
        self.assertEqual(r["website"], "https://www.northwind.ca")
        self.assertIn("King Street West", r["street"])
        self.assertIn("Toronto", r["street"])

    def test_logo_initials_and_double_label(self):
        text = """
        AE ATLAS ÉQUIPEMENTS SARL
        Sophie Gagnon
        Directrice Marketing / Marketing Director
        Tél. / Tel.: 613 555-0144
        Courriel / Email: sophie.gagnon@erable-solutions.ca
        """
        r = parse_card_text(text)
        self.assertEqual(r["partner_name"], "ATLAS ÉQUIPEMENTS SARL")
        self.assertEqual(r["phone"], "613 555-0144")
        self.assertEqual(r["email"], "sophie.gagnon@erable-solutions.ca")
        self.assertEqual(r["other_lines"], [])

    def test_empty(self):
        r = parse_card_text("")
        self.assertFalse(r["email"])
        self.assertEqual(r["other_lines"], [])


if __name__ == "__main__":
    unittest.main()
