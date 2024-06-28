## Frappe Whatsapp

WhatsApp integration for frappe. Use directly meta API's without any 3rd party integration.


![whatsapp](https://user-images.githubusercontent.com/11792643/203741234-29edeb1b-e2f9-4072-98c4-d73a84b48743.gif)


## Note: If your not using live credential follow the [step no 2](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started) to add the number on meta to which your are sending message


## Installation Steps
### Step 1) One time to get app

```bench get-app https://github.com/shridarpatil/frappe_whatsapp```

### Step 2) to install app on any instance/site

```bench --site [sitename] install-app frappe_whatsapp```



### Send whatsapp notification from frappe app based on docevents.

### Get your whats app credentials
A temporary token (Expires every 23 hours) will be available in the WhatsApp API configuration until you configure a system user with a permanent token, note that the sytem user should have the necessary API permissions in order to manage templates and messages
https://developers.facebook.com/docs/whatsapp/cloud-api/get-started

The relevant Credentials Are:
1. Token (Either the temporary token from the get-started link above, or the permanent System User Token if you have generated one)
2. URL (Which should be https://graph.facebook.com)
3. Version (Note the verion you have provisioned for the System User or what is current on the API)
4. Phone ID (Available from get-started above)
5. Business ID (Available from get-started above)
6. APP ID (Available from get-started above)
7. (Optional) Webhook Verify Token (Generate your own secure token and neter it here, however remember to this token when you create your webhook on the Meta Developer Dahsboard as you will need to provide it there)


#### Enter whatsapp credentials
![image](https://user-images.githubusercontent.com/11792643/198827382-90283b36-f8ab-430e-a909-1b600d6f5da4.png)

#### Create Template
Note the Template Name you enter here should not contain spaces or capitalisation as this will be used by the Meta API and your Notifications, i.e. use "new_notification_name" instead of "New Notification Name".
![image](https://user-images.githubusercontent.com/11792643/198827355-ebf9c113-f39a-4d37-98f7-38f719fb2d1f.png)

#### Create notifications
Note the use of the "Field Name" which references the Mobile number to be sued from the DocType you are using in the notification. You may need to create a mobile_no field (correctly formatted, i.e. country code and mobile number without the "+") in the relevant DocType.
![whatsapp_notification](https://user-images.githubusercontent.com/11792643/198827295-f6d756a3-6289-40b3-99ea-0394efb61041.png)
frappe_whatsapp supports all docevents as per Frappe, i.e. Before Insert, Before Validate, Before Save, After Save, Before Submit, After Submit, Before Cancel, After Cancel, Before Delete, After Delete, Before Save (Submitted Document) and, After Save (Submitted Document).

### Sending text message without creating template
Create an entry in the WhatsApp message. On save it will trigger and whats app API to send a message, note that this will not work if the recipient number has not sent a message to the sender in the last 24 hours as per Meta API Rules.
![image](https://user-images.githubusercontent.com/11792643/211518862-de2d3fbc-69c8-48e1-b000-8eebf20b75ab.png)

WhatsApp messages are received via WhatsApp cloud API.
![image](https://user-images.githubusercontent.com/11792643/211519625-a528abe2-ba24-46a4-bcbc-170f6b4e27fb.png)

![outgoing (1)](https://user-images.githubusercontent.com/11792643/211518647-45bfaa00-b06a-49c6-a3b3-3cf801d5ec68.gif)


### Incomming message
- Setup webhook on meta
  * Add verify token on meta and update the same on whatsapp settings
  * Add webhook url on meta `<your domain>/api/method/frappe_whatsapp.utils.webhook.webhook`
- Add apropriate webhook fields
  * `messages` to receive message
  * add other required web fields

Incoming Message for WhatsApp Flows will look like this 
<img width="1429" alt="Screenshot 2024-03-07 at 10 56 27" src="https://github.com/chechani/frappe_whatsapp/assets/6291292/de1f9f47-bd75-4d4a-940b-38ae17d9a073">


#### License

MIT
