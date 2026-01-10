FROM ubuntu:24.04

RUN apt update -y && apt install cowsay

CMD ["cowsay", "Dummy!"]
