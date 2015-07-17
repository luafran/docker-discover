#!/usr/bin/python

import etcd
from jinja2 import Environment, PackageLoader
import os
from subprocess import call
import signal
import sys
import time

env = Environment(loader=PackageLoader('haproxy', 'templates'))
POLL_TIMEOUT=5

signal.signal(signal.SIGCHLD, signal.SIG_IGN)

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

    host, port = get_etcd_addr()
    client = etcd.Client(host=host, port=int(port))
    backends = client.read('/backends', recursive=True)
    services = {}

    for i in backends.children:

        print('children: {i}'.format(i=i))

        if i.key[1:].count("/") == 2:
            _, service, container = i.key[1:].split("/")
        elif i.key[1:].count("/") == 3:
            _, _, service, container = i.key[1:].split("/")
        else:
            print('skipping: {i}'.format(i=i))
            print('/ = {count}'.format(count=i.key[1:].count("/")))
            continue


        print('service: {srv}'.format(srv=service))
        print('container: {cont}'.format(cont=container))

        endpoints = services.setdefault(service, dict(port="", backends=[]))

        if container == "port":
            endpoints["port"] = i.value
            continue
        endpoints["backends"].append(dict(name=container, addr=i.value))
        print('endpoints: {ep}'.format(ep=endpoints))

    print("services: {srv}".format(srv=services))

    return services

def generate_config(services):
    template = env.get_template('haproxy.cfg.tmpl')
    with open("/etc/haproxy.cfg", "w") as f:
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
            ret = call(["./reload-haproxy.sh"])
            if ret != 0:
                print "reloading haproxy returned: ", ret
                time.sleep(POLL_TIMEOUT)
                continue
            current_services = services

        except Exception, e:
            print "Error:", e

        time.sleep(POLL_TIMEOUT)
