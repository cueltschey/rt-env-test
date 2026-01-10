FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update -y && apt install -y cowsay

CMD ["cowsay", "Dummy!"]
