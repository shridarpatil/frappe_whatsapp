import frappe

def remove_integrations_card():
    try:
        workspace = frappe.get_doc('Workspace', 'Integrations')
    except frappe.DoesNotExistError:
        frappe.log_error("The Integrations workspace does not exist.")
        return

    card_break_index = next((index for (index, d) in enumerate(workspace.links) if d.type == "Card Break" and d.label == "WhatsApp"), None)
    
    if card_break_index is not None:
        workspace.links.pop(card_break_index)
        while card_break_index < len(workspace.links) and workspace.links[card_break_index].type == "Link":
            workspace.links.pop(card_break_index)
        workspace.save()
        frappe.db.commit()
        frappe.log_error("WhatsApp Integrations card and links removed successfully.")
    else:
        frappe.log_error("WhatsApp Integrations card not found in the workspace.")
