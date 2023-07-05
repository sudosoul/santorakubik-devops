FROM --platform=linux/amd64 debian:stable-slim

########################
# install OS deps -- TODO: use apt-key / gpg key
########################
RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    curl \
    git \
    nano \
    openssl \
    python3 \ 
    python3-pip \
    sed \
    sudo \
    unzip \
    vim \
    wget \
    zip

##########################
# install User deps..
###########################
# pulumi
RUN curl -fsSL https://get.pulumi.com | sh
# awscli
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && sudo ./aws/install \
    && rm -rf aws*
# kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm -rf kubectl
# kubeseal (sealed-secrets)
RUN wget https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.22.0/kubeseal-0.22.0-linux-amd64.tar.gz \
    && tar -xvzf kubeseal-0.22.0-linux-amd64.tar.gz kubeseal \
    && sudo install -m 755 kubeseal /usr/local/bin/kubeseal \
    && rm -rf kubeseal*
# helm
RUN wget https://get.helm.sh/helm-v3.12.1-linux-amd64.tar.gz \
    && tar -zxvf helm-v3.12.1-linux-amd64.tar.gz \
    && mv linux-amd64/helm /usr/local/bin/helm \
    && rm -rf helm*
# flux
RUN curl -s https://fluxcd.io/install.sh | sudo bash
