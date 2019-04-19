FROM jupyter/datascience-notebook

USER root 

### TauDEM installation adapted from https://github.com/hydroshare/hydroshare-jupyterhub/blob/develop/docker/docker-base/Dockerfile
RUN apt update \
    && apt-get install -y software-properties-common \ 
    && add-apt-repository -y ppa:ubuntugis/ubuntugis-unstable \
    && add-apt-repository -y ppa:ubuntu-toolchain-r/test

RUN apt-get update && apt-get install --fix-missing -y --no-install-recommends \ 
  gcc-7 \
  g++-7 \
  autoconf \
  automake \
  libtool \
  libgeos-dev \
  libproj-dev \   
  libfuse2 \
  libfuse-dev \
  build-essential \ 
  git \ 
  subversion \
  p7zip-full \
  python \
  python-dev \
  python-pip \
  python-scipy \
  libxml2-dev \
  libxslt-dev \
  libgdal-dev \  
  gdal-bin \
  python-gdal \
  grass \
  grass-dev \
  libbsd-dev \
  vlc  \
  libx11-dev \
  man-db \
  wget \
  bash-completion \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/

RUN git clone git://git.mpich.org/mpich.git /tmp/mpich \
    && cd /tmp/mpich \
    && git submodule update --init \
    && ./autogen.sh \
    && ./configure --prefix=/usr \
    && make -j8 \
    && make -j8 install \
    && rm -rf /tmp/mpich

RUN git clone --branch Develop https://github.com/dtarb/TauDEM.git /home/jovyan/libs/TauDEM \
    && cd /home/jovyan/libs/TauDEM \
    && git checkout bceeef2f6a399aa23749a7c7cae7fed521ea910f \
    && cd /home/jovyan/libs/TauDEM/src \
    && sed -i 's#\.\.#/usr/local/bin#g' makefile \
    && make \
    && rm -rf /home/jovyan/libs/TauDEM

### END TauDEM installation

### Python2 kernel

USER jovyan

RUN conda create --name python2 python=2.7

RUN conda install -y -n python2 \
    pandas \
    gdal \
    basemap \
    ipykernel \
    geopandas \
 && conda clean --all -y

RUN /opt/conda/envs/python2/bin/python -m ipykernel install \
    --user \
    --name "python2" \
    --display-name "Python 2" 

RUN conda install -y -n python2 xarray && conda clean --all -y

USER root

### End Python2 kernel

ADD . /opt/cybergis
WORKDIR /opt/cybergis
RUN python setup.py install
RUN /opt/conda/envs/python2/bin/python setup.py install
#RUN apt-get install -yq python2.7-dev
#RUN /bin/bash -c "source /opt/conda/envs/python2/bin/activate /opt/conda/envs/python2 && python setup.py install" 
