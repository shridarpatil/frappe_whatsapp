import { createApp } from 'vue'
import App from './App.vue'
import { initSocket } from './socket'
import './index.css'

import {
  FrappeUI,
  Button,
  Input,
  TextInput,
  FormControl,
  ErrorMessage,
  Dialog,
  Alert,
  Badge,
  setConfig,
  frappeRequest,
  FeatherIcon,
} from 'frappe-ui'

let globalComponents = {
  Button,
  TextInput,
  Input,
  FormControl,
  ErrorMessage,
  Dialog,
  Alert,
  Badge,
  FeatherIcon,
}

let app = createApp(App)

setConfig('resourceFetcher', frappeRequest)
app.use(FrappeUI)
// app_page.use(FrappeUI)

for (let key in globalComponents) {
  app.component(key, globalComponents[key])
  // app_page.component(key, globalComponents[key])
}

// non supportive translation fn.
// window.__ = (text) => text;

// Mount the app
// app.mount('#app');

let socket
if (import.meta.env.DEV) {
  frappeRequest({ url: '/api/method/frappe_whatsapp.www.frappe_whatsapp.get_context_for_dev'}).then(
    (values) => {
      for (let key in values) {
        window[key] = values[key]
      }
      socket = initSocket()
      app.config.globalProperties.$socket = socket
      app.mount('#app')
    },
  )
  
} else {
  socket = initSocket()
  app.config.globalProperties.$socket = socket
  app.mount('#app')
}
