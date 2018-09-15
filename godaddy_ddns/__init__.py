import datetime
import errno
import os
import re
import sys

import click
import pif
import yaml

from godaddypy import Client, Account
from godaddypy.client import BadResponse


@click.command()
@click.option(
    '--config',
    default="/etc/godaddy-ddns/config.yaml",
    help="Path to configuration file (.yaml).",
    type=click.File('r')
)
@click.option('--force', is_flag=True, help="Update the IP regardless of the cached IP.")
@click.option('--quiet', is_flag=True, help="Don't print to stdout.")
def update_ip(config, force, quiet):
    # Load the configuration file
    try:
        conf = yaml.load(config)
    except yaml.MarkedYAMLError as e:
        # If the error is marked, give the details
        print("Error: Malformed configuration file.")
        print(e)
        sys.exit(errno.EINVAL)
    except yaml.YAMLError:
        # Otherwise just state that it's malformed
        print("Error: Malformed configuration file")
        sys.exit(errno.EINVAL)

    # Check the supplied log path
    if conf.get("log_path", False):
        # Make sure that the log path exists and is writable
        try:
            touch(conf["log_path"])
        except PermissionError:
            print("Error: Insufficient permissions to write log to '{}'.".format(conf['log_path']))
            sys.exit(errno.EACCES)

        # Define the logging function
        def write_log(msg):
            now = datetime.datetime.now().isoformat(' ', timespec='seconds')
            with open(conf["log_path"], 'a') as f:
                f.write("[{now}]: {msg}\n".format(now=now, msg=msg))
            if not quiet:
                click.echo(msg)
    else:
        # No log file specified, so disable logging
        def write_log(msg):
            if not quiet:
                click.echo(msg)  # Just print the message, don't log it

    # Check the supplied cache path
    if conf.get("cache_path", False):
        # Make sure that the log path exists and is writable
        try:
            touch(conf["cache_path"])  # Create the file if necessary
        except PermissionError:
            write_log("Error: Insufficient permissions to write to cache ({}).".format(conf['cache_path']))
            sys.exit(errno.EACCES)

        # Define the caching functions
        def write_cache(ip_addr):
            now = datetime.datetime.now().isoformat(' ', timespec='seconds')
            with open(conf["cache_path"], 'w') as f:
                f.write("[{}]: {}".format(now, ip_addr))

        def read_cache():
            with open(conf["cache_path"], "r") as f:
                cached = f.readline()
            return (cached[1:20], cached[23:])  # date_time, ip_addr
    else:
        # No cache file specified, so disable caching and warn the user!
        write_log("Warning: No cache file specified, so the IP address will always be submitted as if new - this could be considered abusive!")

        # Define the caching functions
        def write_cache(ip_addr):
            pass  # Don't write to cache

        def read_cache():
            return (None, None)

    # Get IPv4 address
    myip = pif.get_public_ip("v4.ident.me")

    if not myip:
        write_log("Error: Failed to determine IPv4 address")
        sys.exit(errno.CONNREFUSED)

    # Check whether the current IP is equal to the cached IP address
    date_time, cached_ip = read_cache()
    if force:
        write_log("Info: Performing forced update")
    elif myip == cached_ip:
        # Already up-to-date, so log it and exit
        write_log("Success: IP address is already up-to-date ({})".format(myip))
        sys.exit(0)
    else:
        write_log("Info: New IP address detected ({})".format(myip))

    # Get API details
    account = Account(api_key=conf.get("api_key"), api_secret=conf.get("api_secret"))
    client = Client(account, api_base_url=conf.get("api_base_url", "https://api.godaddy.com"))

    # Check that we have a connection and get the set of available domains
    try:
        available_domains = set(client.get_domains())
    except BadResponse as e:
        write_log("Error: Bad response from GoDaddy ({})".format(e._message))
        sys.exit(errno.CONNREFUSED)

    # Make the API requests to update the IP address
    failed_domains = {}  # Stores a set of failed domains - failures will be tolerated but logged
    for target in conf.get("targets", []):
        try:
            target_domain = target["domain"]
        except KeyError:
            write_log("Error: Missing 'domain' in confuration file")
            sys.exit(errno.EINVAL)

        if type(target_domain) == str:
            target_domain = {target_domain}
        else:
            target_domain = set(target_domain)

        unknown_domains = target_domain - available_domains
        failed_domains.update(unknown_domains)

        domains = list(target_domain & available_domains)  # Remove unknown domains
        subdomains = target.get("alias", "@")  # Default to no subdomain (GoDaddy uses "@" for this)

        try:
            update_succeeded = client.update_ip(myip, domains=domains, subdomains=subdomains)
        except BadResponse as e:
            write_log("Error: Bad response from GoDaddy ({})".format(e._message))
            sys.exit(errno.CONNREFUSED)

        if update_succeeded:
            write_log("Success: Updated IP for {subs}.{doms}".format(subs=subdomains, doms=domains))
        else:
            write_log("Error: Unknown failure for (domain(s): {doms}, alias(es): {subs})".format(doms=target_domain, subs=subdomains))
            sys.exit(errno.CONNREFUSED)

    if failed_domains:
        write_log("Warning: The following domains were not found {}".format(failed_domains))

    # Write the new IP address to the cache and exit
    write_cache(myip)
    sys.exit(0)


# Define 'touch' function
def touch(path):
    # Ensure the path exists
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Create the file if necessary
    with open(path, 'a'):
        os.utime(path, None)
