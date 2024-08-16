import frappe

def remove_integrations_card():
    try:
        # Fetch the Integrations workspace document
        workspace = frappe.get_doc('Workspace', 'Integrations')
    except frappe.DoesNotExistError:
        frappe.log_error("The Integrations workspace does not exist.")
        return
    
    # Find the index of the card break with the label "WhatsApp Integrations"
    card_break_index = next((index for (index, d) in enumerate(workspace.links) if d.type == "Card Break" and d.label == "WhatsApp"), None)
    
    if card_break_index is not None:
        # Remove the card break and all links after it until the next card break or the end of the list
        workspace.links.pop(card_break_index)
        
        # Remove subsequent links associated with the "WhatsApp Integrations" card
        while card_break_index < len(workspace.links) and workspace.links[card_break_index].type == "Link":
            workspace.links.pop(card_break_index)
        
        # Save the updated workspace
        workspace.save()
        frappe.db.commit()
        frappe.log_error("WhatsApp Integrations card and links removed successfully.")
    else:
        frappe.log_error("WhatsApp Integrations card not found in the workspace.")
