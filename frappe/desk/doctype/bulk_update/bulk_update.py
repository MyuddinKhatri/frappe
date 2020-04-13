# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document
from frappe import _
from frappe.utils import cint
from frappe.utils import get_url

class BulkUpdate(Document):
	pass

@frappe.whitelist()
def update(doctype, field, value, condition='', limit=500):
	if not limit or cint(limit) > 500:
		limit = 500

	if condition:
		condition = ' where ' + condition

	if ';' in condition:
		frappe.throw(_('; not allowed in condition'))

	docnames = frappe.db.sql_list(
		'''select name from `tab{0}`{1} limit 0, {2}'''.format(doctype, condition, limit)
	)
	data = {}
	data[field] = value
	return submit_cancel_or_update_docs(doctype, docnames, 'update', data)

@frappe.whitelist()
def submit_cancel_or_update_docs(doctype, docnames, action='submit', data=None):
	docnames = frappe.parse_json(docnames)

	if data:
		data = frappe.parse_json(data)

	failed = []

	for i, d in enumerate(docnames, 1):
		doc = frappe.get_doc(doctype, d)
		try:
			message = ''
			if action == 'submit' and doc.docstatus==0:
				doc.submit()
				message = _('Submiting {0}').format(doctype)
			elif action == 'cancel' and doc.docstatus==1:
				doc.cancel()
				message = _('Cancelling {0}').format(doctype)
			elif action == 'update' and doc.docstatus < 2:
				doc.update(data)
				doc.save()
				message = _('Updating {0}').format(doctype)
			else:
				failed.append(d)
			frappe.db.commit()
			show_progress(docnames, message, i, d)

		except Exception:
			failed.append(d)
			frappe.db.rollback()

	return failed

def show_progress(docnames, message, i, description):
	n = len(docnames)
	if n >= 10:
		frappe.publish_progress(
			float(i) * 100 / n,
			title = message,
			description = description
		)

@frappe.whitelist()
def get_contact(name, doctype):
	out = frappe._dict()

	contact_field = frappe.get_hooks("contact_fields").get(doctype) or {}
	if contact_field:
		name = frappe.db.get_value(doctype, name, contact_field)
		doctype = contact_field

	get_default_contact(out, name, doctype)

	return out

def get_default_contact(out, name, doctype):
	contact_persons = frappe.db.sql(
		"""
			SELECT parent,
				(SELECT is_primary_contact FROM tabContact c WHERE c.name = dl.parent) AS is_primary_contact
			FROM
				`tabDynamic Link` dl
			WHERE
				dl.link_doctype=%s
				AND dl.link_name=%s
				AND dl.parenttype = "Contact"
		""", (doctype,name), as_dict=1)

	if contact_persons:
		for out.contact_person in contact_persons:
			out.contact_person.email_id = frappe.db.get_value("Contact", out.contact_person.parent, ["email_id"])
			if out.contact_person.is_primary_contact:
				return out.contact_person

		out.contact_person = contact_persons[0]

		return out.contact_person

@frappe.whitelist()
def get_attach_link(docs, doctype):
	docs = json.loads(docs)
	print_format = "print_format"
	links = []
	for doc in docs:
		link = frappe.get_template("templates/emails/print_link.html").render({
			"url": get_url(),
			"doctype": doctype,
			"name": doc.get("name"),
			"print_format": print_format,
			"key": frappe.get_doc(doctype, doc.get("name")).get_signature()
		})
		links.append(link)
	return links

