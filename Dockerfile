FROM ghcr.io/shridarpatil/frappe

LABEL org.opencontainers.image.source=https://github.com/shridarpatil/frappe_whatsapp
MAINTAINER Shridhar <shridharpatil2792@gmail.com>
RUN bench get-app https://github.com/shridarpatil/frappe_whatsapp.git --skip-assets
