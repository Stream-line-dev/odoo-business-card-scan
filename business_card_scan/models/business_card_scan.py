# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import plaintext2html

from .card_parser import parse_card_text


class BusinessCardScan(models.Model):
    _name = "business.card.scan"
    _description = "Business Card Scan"
    _order = "create_date desc, id desc"

    name = fields.Char("Reference", compute="_compute_name", store=True)
    image = fields.Image("Card Photo", max_width=1600, max_height=1600)
    image_128 = fields.Image("Thumbnail", related="image", max_width=128, max_height=128, store=True)
    raw_text = fields.Text("Scanned Text (OCR)")

    contact_name = fields.Char("Contact Name")
    partner_name = fields.Char("Company")
    function = fields.Char("Job Position")
    email = fields.Char("Email")
    phone = fields.Char("Phone")
    phone_2 = fields.Char("Other Phone")
    website = fields.Char("Website")
    street = fields.Char("Address")
    notes = fields.Text("Other Information")

    user_id = fields.Many2one(
        "res.users", string="Salesperson", default=lambda self: self.env.user
    )
    team_id = fields.Many2one("crm.team", string="Sales Team")
    tag_ids = fields.Many2many("crm.tag", string="Tags")
    partner_id = fields.Many2one("res.partner", string="Existing Contact")

    duplicate_lead_id = fields.Many2one(
        "crm.lead", string="Existing Lead (same email)", compute="_compute_duplicate_lead_id"
    )
    lead_id = fields.Many2one("crm.lead", string="Created Lead", readonly=True, copy=False)
    state = fields.Selection(
        [("draft", "To Review"), ("done", "Lead Created")],
        default="draft",
        required=True,
        string="Status",
    )

    @api.depends("contact_name", "partner_name")
    def _compute_name(self):
        for scan in self:
            scan.name = scan.contact_name or scan.partner_name or _("Business Card")

    @api.depends("email")
    def _compute_duplicate_lead_id(self):
        Lead = self.env["crm.lead"]
        for scan in self:
            lead = Lead
            if scan.email:
                lead = Lead.search(
                    [("email_from", "=ilike", scan.email.strip()), ("id", "!=", scan.lead_id.id or 0)],
                    limit=1,
                )
            scan.duplicate_lead_id = lead

    # ------------------------------------------------------------------
    # Analyse
    # ------------------------------------------------------------------
    def _values_from_text(self, text):
        data = parse_card_text(text or "")
        vals = {
            key: data[key] or False
            for key in ("contact_name", "partner_name", "function", "email",
                        "phone", "phone_2", "website", "street")
        }
        vals["notes"] = "\n".join(data["other_lines"]) or False
        partner = self.env["res.partner"]
        if data["email"]:
            partner = partner.search([("email", "=ilike", data["email"])], limit=1)
        vals["partner_id"] = partner.id or False
        return vals

    @api.model
    def create_from_ocr(self, image_b64, raw_text):
        """Appelé par l'écran de scan (JS) après la lecture OCR dans le navigateur."""
        vals = {"image": image_b64 or False, "raw_text": raw_text or ""}
        vals.update(self._values_from_text(raw_text))
        return self.create(vals).id

    def action_reparse(self):
        for scan in self.filtered(lambda s: s.state == "draft"):
            vals = scan._values_from_text(scan.raw_text)
            scan.write(vals)
        return True

    # ------------------------------------------------------------------
    # Création de la lead
    # ------------------------------------------------------------------
    def _prepare_lead_values(self):
        self.ensure_one()
        title = self.partner_name or self.contact_name or _("Contact")
        description_lines = []
        if self.phone_2:
            description_lines.append(_("Other phone: %s", self.phone_2))
        if self.notes:
            description_lines.append(self.notes)
        vals = {
            "name": _("Business Card - %s", title),
            "contact_name": self.contact_name,
            "partner_name": self.partner_name,
            "function": self.function,
            "email_from": self.email,
            "phone": self.phone or self.phone_2,
            "website": self.website,
            "street": self.street,
            "user_id": self.user_id.id,
            "tag_ids": [(6, 0, self.tag_ids.ids)],
            "description": plaintext2html("\n".join(description_lines)) if description_lines else False,
        }
        if self.team_id:
            vals["team_id"] = self.team_id.id
        if self.partner_id:
            vals["partner_id"] = self.partner_id.id
        return vals

    def action_create_lead(self):
        self.ensure_one()
        if self.lead_id:
            return self.action_open_lead()
        if not (self.contact_name or self.partner_name or self.email or self.phone):
            raise UserError(_("No usable information: please fill in at least the name, company, email or phone."))

        lead = self.env["crm.lead"].create(self._prepare_lead_values())
        # Avec un contact existant, Odoo recopie ses coordonnées sur la lead.
        # On complète seulement les champs restés vides (sans modifier le contact).
        if self.partner_id:
            card_values = {
                "contact_name": self.contact_name,
                "email_from": self.email,
                "phone": self.phone or self.phone_2,
                "function": self.function,
                "website": self.website,
                "street": self.street,
            }
            missing = {k: v for k, v in card_values.items() if v and not lead[k]}
            if missing:
                lead.write(missing)

        attachment_ids = []
        if self.image:
            attachment = self.env["ir.attachment"].create({
                "name": "business_card_%s.jpg" % lead.id,
                "datas": self.image,
                "res_model": "crm.lead",
                "res_id": lead.id,
                "mimetype": "image/jpeg",
            })
            attachment_ids.append(attachment.id)
        lead.message_post(
            body=_("Lead created from a scanned business card."),
            attachment_ids=attachment_ids,
        )
        self.write({"lead_id": lead.id, "state": "done"})
        return self.action_open_lead()

    def action_open_lead(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "crm.lead",
            "res_id": self.lead_id.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }

    def action_open_duplicate(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "crm.lead",
            "res_id": self.duplicate_lead_id.id,
            "views": [(False, "form")],
            "target": "current",
        }
