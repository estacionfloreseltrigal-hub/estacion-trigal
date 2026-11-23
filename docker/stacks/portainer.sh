#!/bin/bash
# Portainer (se instala una sola vez con docker run; el resto de contenedores se crean como Stacks desde Portainer)
docker run -d -p 9443:9443 --name portainer --restart=always -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer-ce:latest
