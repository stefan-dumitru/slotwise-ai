FROM nginx:alpine

COPY . /usr/share/nginx/html

RUN mv /usr/share/nginx/html/docker-entrypoint.sh /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh && rm -f /usr/share/nginx/html/Dockerfile /usr/share/nginx/html/.dockerignore

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
