#!/usr/bin/python

# import etcd
from jinja2 import Environment, PackageLoader
import os
from subprocess import call
import signal
import sys
import time

env = Environment(loader=PackageLoader('haproxy', 'templates'))
POLL_TIMEOUT=5

signal.signal(signal.SIGCHLD, signal.SIG_IGN)


class Children:
    def __init__(self, key, value):
        self.key = key
        self.value = value


def get_etcd_addr():
    if "ETCD_HOST" not in os.environ:
        print "ETCD_HOST not set"
        sys.exit(1)

    etcd_host = os.environ["ETCD_HOST"]
    if not etcd_host:
        print "ETCD_HOST not set"
        sys.exit(1)

    port = 4001
    host = etcd_host

    if ":" in etcd_host:
        host, port = etcd_host.split(":")

    return host, port


def get_services():

    # host, port = get_etcd_addr()
    # client = etcd.Client(host=host, port=int(port))
    # backends = client.read('/backends', recursive=True)
    services = {}
    
    children = [
        Children('/backend/family', ''),
        Children('/backend/family/v1', ''),
        Children('/backend/family/v1/111111111111', '172.31.27.111:8011'),
        Children('/backend/family/v1/112111111111', '172.31.27.112:8011'),
        Children('/backend/family/v1/113111111111', '172.31.27.113:8011'),
        Children('/backend/context', ''),
        Children('/backend/context/v1', ''),
        Children('/backend/context/v1/211111111111', '172.31.27.211:8021'),
        Children('/backend/context/v1/212111111111', '172.31.27.212:8021'),
        Children('/backend/context/v2', ''),
        Children('/backend/context/v2/221222222222', '172.31.27.221:8021')
    ]

    # for i in backends.children:
    for i in children:

        print('children: {i}'.format(i=i))
        print i.key
        print i.value

        if i.key[1:].count("/") == 3:
            _, service, version, container = i.key[1:].split("/")
        else:
            print('skipping: {i}'.format(i=i))
            print('/ = {count}'.format(count=i.key[1:].count("/")))
            continue

        service_name = service + '_' + version
        path = '/' + service + '/' + version

        print('service_name: {srv}'.format(srv=service_name))
        print('version: {vers}'.format(vers=version))
        print('path: {path}'.format(path=path))
        print('container: {cont}'.format(cont=container))

        endpoints = services.setdefault(service_name, dict(path=path, weight=100, backends=[]))

        if container == "weight":
            endpoints["weight"] = i.value
            continue
        endpoints["backends"].append(dict(name=container, addr=i.value))
        print('endpoints: {ep}'.format(ep=endpoints))

    print("services: {srv}".format(srv=services))

    return services


def generate_config(services):
    template = env.get_template('haproxy2.cfg.tmpl')
    with open("./haproxy.cfg", "w") as f:
        f.write(template.render(services=services))

if __name__ == "__main__":
    current_services = {}
    while True:
        try:
            services = get_services()

            if not services or services == current_services:
                time.sleep(POLL_TIMEOUT)
                continue

            print "config changed. reload haproxy"
            generate_config(services)
            # ret = call(["./reload-haproxy.sh"])
            # if ret != 0:
            #     print "reloading haproxy returned: ", ret
            #     time.sleep(POLL_TIMEOUT)
            #     continue
            current_services = services

        except Exception, e:
            print "Error:", e

        time.sleep(POLL_TIMEOUT)
