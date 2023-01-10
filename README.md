<a href="https://zerodha.tech"><img src="https://zerodha.tech/static/images/github-badge.svg" align="right" /></a>

## Frappe Whatsapp

WhatsApp integration for frappe. Use directly meta API's without any 3rd party integration.


![whatsapp](https://user-images.githubusercontent.com/11792643/203741234-29edeb1b-e2f9-4072-98c4-d73a84b48743.gif)



## Installation Steps
### Step 1) One time to get app

```bench get-app https://github.com/shridarpatil/frappe_whatsapp```

### Step 2) to install app on any instance/site

```bench --site [sitename] install-app frappe_whatsapp```



### Send whatsapp notification from frappe app based on docevents.

### Get your whats app credentials

https://developers.facebook.com/docs/whatsapp/cloud-api/get-started


#### Enter whatsapp credentials

![image](https://user-images.githubusercontent.com/11792643/198827382-90283b36-f8ab-430e-a909-1b600d6f5da4.png)

#### Create Template
![image](https://user-images.githubusercontent.com/11792643/198827355-ebf9c113-f39a-4d37-98f7-38f719fb2d1f.png)



Supports all docevents

#### Create notifications
![whatsapp_notification](https://user-images.githubusercontent.com/11792643/198827295-f6d756a3-6289-40b3-99ea-0394efb61041.png)


### Sending text message without creating template
Create an entry in the WhatsApp message. On save it will trigger and whats app API to send a message

![image](https://user-images.githubusercontent.com/11792643/211518862-de2d3fbc-69c8-48e1-b000-8eebf20b75ab.png)

WhatsApp messages are received via WhatsApp cloud API.
![image](https://user-images.githubusercontent.com/11792643/211519625-a528abe2-ba24-46a4-bcbc-170f6b4e27fb.png)

![outgoing (1)](https://user-images.githubusercontent.com/11792643/211518647-45bfaa00-b06a-49c6-a3b3-3cf801d5ec68.gif)


### Upcoming features
* Update templates on facebook dev.
* Display template status

#### License

MIT
