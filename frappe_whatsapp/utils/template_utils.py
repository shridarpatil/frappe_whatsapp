def get_template_values(template_name, recipient_data=None):
    """
    Get the template values for a WhatsApp template
    
    Args:
        template_name (str): Name of the WhatsApp template
        recipient_data (dict, optional): Dictionary of recipient-specific data
        
    Returns:
        dict: Dictionary of template values
    """
    import json
    
    # Get the template
    template = frappe.get_doc("WhatsApp Template", template_name)
    
    # Extract variables from template body
    variables = []
    if template.body:
        # Extract variables in {{variable}} format
        import re
        pattern = r'\{\{([^}]+)\}\}'
        matches = re.findall(pattern, template.body)
        variables.extend(matches)
    
    # Also check header, footer, etc. if needed
    
    # Prepare values
    values = {}
    
    # If recipient data is provided, use it
    if recipient_data:
        if isinstance(recipient_data, str):
            try:
                recipient_data = json.loads(recipient_data)
            except Exception:
                recipient_data = {}
        
        # Map variables from recipient data
        for var in variables:
            if var in recipient_data:
                values[var] = recipient_data[var]
    
    return values
