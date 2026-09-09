FROM nginx:alpine

COPY . /usr/share/nginx/html

RUN mv /usr/share/nginx/html/docker-entrypoint.sh /docker-entrypoint.sh \
    && mkdir -p /etc/nginx/templates \
    && mv /usr/share/nginx/html/nginx.conf.template /etc/nginx/templates/default.conf.template \
    && chmod +x /docker-entrypoint.sh \
    && rm -f /usr/share/nginx/html/Dockerfile /usr/share/nginx/html/.dockerignore

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
