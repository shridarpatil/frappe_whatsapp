Frappe Whatsapp

WhatsApp integration for frappe. Use directly meta API's without any 3rd party integration.

[![Whatsapp Video](https://img.youtube.com/vi/nq5Kcc5e1oc/0.jpg)](https://www.youtube.com/watch?v=nq5Kcc5e1oc)


[![YouTube](http://i.ytimg.com/vi/TncXQ0UW5UM/hqdefault.jpg)](https://www.youtube.com/watch?v=TncXQ0UW5UM)



![whatsapp](https://user-images.githubusercontent.com/11792643/203741234-29edeb1b-e2f9-4072-98c4-d73a84b48743.gif)

Note: If your not using live credential follow the [step no 2](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started) to add the number on meta to which your are sending message

### Chat app You can also install
[whatsapp\_chat](https://frappecloud.com/marketplace/apps/whatsapp_chat) along with this app to send and receive message like a messenger Installation Steps

### Step 1) One time to get app 
`bench get-app https://github.com/shridarpatil/frappe_whatsapp` 
### Step 2) to install app on any instance/site
`bench --site [sitename] install-app frappe_whatsapp` 

### Send whatsapp notification from frappe app based on docevents. 
### Get your whats app credentials 
https://developers.facebook.com/docs/whatsapp/cloud-api/get-started 
#### Enter whatsapp credentials ![image](https://user-images.githubusercontent.com/11792643/198827382-90283b36-f8ab-430e-a909-1b600d6f5da4.png) 

#### Create Template ![image](https://user-images.githubusercontent.com/11792643/198827355-ebf9c113-f39a-4d37-98f7-38f719fb2d1f.png) Supports all docevents 

#### Create notifications ![whatsapp_notification](https://user-images.githubusercontent.com/11792643/198827295-f6d756a3-6289-40b3-99ea-0394efb61041.png) 

### Sending text message without creating template Create an entry in the WhatsApp message. On save it will trigger and whats app API to send a message ![image](https://user-images.githubusercontent.com/11792643/211518862-de2d3fbc-69c8-48e1-b000-8eebf20b75ab.png) WhatsApp messages are received via WhatsApp cloud API.![image](https://user-images.githubusercontent.com/11792643/211519625-a528abe2-ba24-46a4-bcbc-170f6b4e27fb.png) ![outgoing (1)](https://user-images.githubusercontent.com/11792643/211518647-45bfaa00-b06a-49c6-a3b3-3cf801d5ec68.gif) 

### Sending a template using custom _dict() insted of a doctype.
This can be very useful for features where it is not possible to get the values directly from the doctype.
Just create a script and populate variable called "_data_list":
`doc.set("_data_list", data_list)`

Example:
![image](https://github.com/user-attachments/assets/7496b081-df2b-41dc-bdcb-ed7e5f464698)

### Incomming message 
* Setup webhook on meta 
* Add verify token on meta and update the same on whatsapp settings 
* Add webhook url on meta
`<domain >/api/method/frappe_whatsapp.utils.webhook.webhook` 
* Add apropriate webhook fields 
* `messages` to receive message 
* add other required web fields 

### Upcoming features 
* Update templates on facebook dev. 
* Display template status 
 
#### License MIT
