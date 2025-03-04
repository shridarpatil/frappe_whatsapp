import { io } from 'socket.io-client'

export function initSocket() {
  console.log("Site Name:", import.meta.env.VITE_SITE_NAME)
  
  let host = window.location.hostname
  let siteName = import.meta.env.VITE_SITE_NAME || window.location.host
  let port = window.location.port ? `:${window.location.port}` : ''
  let protocol = port ? 'http' : 'https'
  let url = `${protocol}://${host}${port}/${siteName}`

  let socket = io(url, {
    withCredentials: true,
    reconnectionAttempts: 5,
  })

  return socket
}
