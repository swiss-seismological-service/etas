# Use an official Ubuntu as a parent image
FROM ubuntu:22.04

# Install pycompss dependencies and then the pycompss package
# Problem: could not get the right python version that worked with pycompss and etas.

# Install dependencies
RUN apt-get update && apt-get install -y \
    openjdk-8-jdk \
    graphviz \
    xdg-utils \
    libtool \
    automake \
    build-essential \
    pkgconf \
    python3 \
    python3-dev \
    libboost-serialization-dev \
    libboost-iostreams-dev \
    libxml2 \
    libxml2-dev \
    csh \
    gfortran \
    libgmp3-dev \
    flex \
    bison \
    texinfo \
    python3-pip \
    libpapi-dev \
    wget \
    git \
    maven
    
RUN apt-get install -y unzip
RUN wget https://services.gradle.org/distributions/gradle-5.4.1-bin.zip -O /opt/gradle-5.4.1-bin.zip && \
    unzip /opt/gradle-5.4.1-bin.zip -d /opt

# Set environment variables
ENV JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64/
ENV EXTRAE_MPI_HEADERS=/usr/include/x86_64-linux-gnu/mpi
ENV GRADLE_HOME=/opt/gradle-5.4.1
ENV PATH=$GRADLE_HOME/bin:$PATH

# Install optional Python packages
RUN pip3 install dill guppy3 numpy
RUN pip3 install pycompss


# Default command
CMD ["/bin/bash"]