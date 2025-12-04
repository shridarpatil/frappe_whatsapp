# Frappe WhatsApp

[Documentation](https://shridarpatil.github.io/frappe_whatsapp/)

WhatsApp integration for Frappe/ERPNext. Use Meta's WhatsApp Cloud API directly without any third-party integration.

[![WhatsApp Video](https://img.youtube.com/vi/nq5Kcc5e1oc/0.jpg)](https://www.youtube.com/watch?v=nq5Kcc5e1oc)

[![YouTube](http://i.ytimg.com/vi/TncXQ0UW5UM/hqdefault.jpg)](https://www.youtube.com/watch?v=TncXQ0UW5UM)

![whatsapp](https://user-images.githubusercontent.com/11792643/203741234-29edeb1b-e2f9-4072-98c4-d73a84b48743.gif)

> **Note:** If you're not using live credentials, follow [step no 2](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started) to add the number on Meta to which you are sending messages.

## Features

- **Multi-Account Support** - Manage multiple WhatsApp Business accounts
- **Two-way Messaging** - Send and receive messages with full conversation tracking
- **Template Management** - Create and sync WhatsApp templates with Meta
- **WhatsApp Notifications** - Automated notifications triggered by DocType events
- **Bulk Messaging** - Send campaigns to recipient lists with variable substitution
- **Webhook Support** - Real-time message delivery and status updates
- **Media Support** - Send and receive images, documents, videos, and audio files
- **ERPNext Integration** - Native integration with Frappe/ERPNext DocTypes

## Installation

### Step 1: Get the app
```bash
bench get-app https://github.com/shridarpatil/frappe_whatsapp
```

### Step 2: Install on your site
```bash
bench --site [sitename] install-app frappe_whatsapp
```

## Quick Setup

### 1. Get WhatsApp Credentials
Visit [Meta Developer Portal](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started) to set up your WhatsApp Business API.

### 2. Configure WhatsApp Account
Go to **WhatsApp Account** in Frappe and enter your credentials:
- Account Name
- Access Token
- Phone Number ID
- Business Account ID
- App ID
- Webhook Verify Token

![WhatsApp Settings](https://user-images.githubusercontent.com/11792643/198827382-90283b36-f8ab-430e-a909-1b600d6f5da4.png)

### 3. Create Templates
Create WhatsApp templates that are approved by Meta:

![Create Template](https://user-images.githubusercontent.com/11792643/198827355-ebf9c113-f39a-4d37-98f7-38f719fb2d1f.png)

## Core Features

### WhatsApp Notifications

Automatically send WhatsApp messages based on DocType events.

**Supported Triggers:**
- DocType Events: Before/After Insert, Validate, Save, Submit, Cancel, Delete
- Scheduler Events: Hourly, Daily, Weekly, Monthly
- Date-based: Days Before/After a specified date field

![WhatsApp Notification](https://user-images.githubusercontent.com/11792643/198827295-f6d756a3-6289-40b3-99ea-0394efb61041.png)

**Features:**
- Map template parameters to DocType fields
- Add conditions using Python expressions
- Attach document print PDFs or custom files
- Set DocType field values after sending (e.g., mark as notified)
- Support for interactive buttons with dynamic URLs

### Bulk WhatsApp Messages

Send WhatsApp messages to multiple recipients at once.

**Features:**
- Import recipients from any DocType (Customer, Contact, etc.)
- Create recipient lists for reuse
- Variable substitution from recipient data
- Background processing with progress tracking
- Retry failed messages
- Select specific WhatsApp account for sending

**Recipient Types:**
1. **Individual Recipients** - Add recipients directly with their phone numbers
2. **Recipient List** - Use a pre-configured WhatsApp Recipient List

**Variable Types:**
1. **Common** - Same values for all recipients
2. **Unique** - Different values per recipient (from recipient data)

### Direct Messaging

Send messages without templates (within 24-hour window):

![Direct Message](https://user-images.githubusercontent.com/11792643/211518862-de2d3fbc-69c8-48e1-b000-8eebf20b75ab.png)

### Custom Data Templates

Send templates using custom data instead of DocType fields:

```python
doc.set("_data_list", [
    {"phone": "+1234567890", "name": "John", "order_id": "ORD-001"},
    {"phone": "+0987654321", "name": "Jane", "order_id": "ORD-002"}
])
```

![Custom Data](https://github.com/user-attachments/assets/7496b081-df2b-41dc-bdcb-ed7e5f464698)

## Webhook Setup

### Configure Webhook on Meta
1. Go to your Meta Developer App
2. Set Webhook URL: `<your-domain>/api/method/frappe_whatsapp.utils.webhook.webhook`
3. Add Verify Token (same as in WhatsApp Account settings)
4. Subscribe to webhook fields:
   - `messages` - to receive incoming messages
   - `message_template_status_update` - for template status updates

### Incoming Messages
Messages received via webhook are automatically created as WhatsApp Message documents:

![Incoming Message](https://user-images.githubusercontent.com/11792643/211519625-a528abe2-ba24-46a4-bcbc-170f6b4e27fb.png)

## Multi-Account Support

Manage multiple WhatsApp Business accounts for different use cases:

- Set default accounts for incoming and outgoing messages
- Select specific accounts when sending bulk messages
- Route notifications through designated accounts
- Auto-read receipts per account

## Chat Integration

Install [whatsapp_chat](https://frappecloud.com/marketplace/apps/whatsapp_chat) for a messenger-like chat interface.

## Documentation

For detailed documentation, visit [https://shridarpatil.github.io/frappe_whatsapp/](https://shridarpatil.github.io/frappe_whatsapp/)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT
