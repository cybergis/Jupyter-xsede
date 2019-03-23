FROM jupyter/datascience-notebook

USER root 

ADD . /opt/cybergis
WORKDIR /opt/cybergis
RUN python setup.py install
#RUN apt-get install -yq python2.7-dev
#RUN /bin/bash -c "source /opt/conda/envs/python2/bin/activate /opt/conda/envs/python2 && python setup.py install" 
