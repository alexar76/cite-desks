FROM nginx:1.27-alpine
COPY kernel/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY kernel/web/index.html /usr/share/nginx/html/index.html
COPY kernel/web/styles.css /usr/share/nginx/html/styles.css
COPY kernel/web/app.js /usr/share/nginx/html/app.js
COPY kernel/web/scene.js /usr/share/nginx/html/scene.js
COPY kernel/web/vendor /usr/share/nginx/html/vendor
COPY kernel/web/earth-day.jpg /usr/share/nginx/html/earth-day.jpg
COPY kernel/web/favicon.svg /usr/share/nginx/html/favicon.svg
COPY kernel/web/fonts /usr/share/nginx/html/fonts
