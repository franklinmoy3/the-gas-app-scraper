# This Dockerfile is only intended to be used by an IDE's Dev Containers extension

# Use latest python3 on Debian bookworm
FROM python:3.12-bookworm

# Reflect the local user in the container
ARG REMOTE_USER
ARG REMOTE_UID
ARG REMOTE_GID
RUN groupadd --gid $REMOTE_GID $REMOTE_USER \
    && useradd --uid $REMOTE_UID --gid $REMOTE_GID -m $REMOTE_USER \
    # Also install sudo and vi, adding the user to sudoers
    && apt-get update \
    && apt-get install -y sudo vim firefox-esr wget bzip2 libxtst6 libgtk-3-0 libx11-xcb-dev libdbus-glib-1-2 libxt6 libpci-dev \
    && echo $REMOTE_USER ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$REMOTE_USER \
    && chmod 0440 /etc/sudoers.d/$REMOTE_USER

RUN curl -L https://github.com/mozilla/geckodriver/releases/download/v0.35.0/geckodriver-v0.35.0-linux64.tar.gz | tar zx
RUN mv geckodriver /usr/local/bin/

# Set the default user and home directory
ENV HOME /home/${REMOTE_USER}
ENV PATH="${PATH}:/home/${REMOTE_USER}/.local/bin" 
USER ${REMOTE_USER}

# Set locale to C.UTF-8 since en_US.UTF-8 isn't listed by "locale -a"
# This gets oh-my-zsh to render themes correctly
ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8
