import datetime
import os
import warnings

import click
import pif
import yaml

from godaddypy import Client, Account
from godaddypy.client import BadResponse


class ConfigError(Exception):
    pass


def update_ip(config_file, force):
    """Update the IP address for the configured domains/subdomains

    Parameters:
     - config_file: Open file or file-like object configuration file
     - force: boolean flag for forcing updates (True => force update)

    Returns:
     - updated: bool indicating whether the IP address was updated
     - myip: str containing the current IP address
     - domains: list of updated domains (eg. ["[sub1,sub2].[example.com]"])
    """
    # Load the configuration file
    try:
        config = yaml.load(config_file)
    except (yaml.MarkedYAMLError, yaml.YAMLError) as e:
        raise ConfigError("Error: {}".format(e))

    # Check the supplied log path
    log_path = config.get("log_path")
    if log_path:
        # Make sure that the log path exists and is writable
        try:
            touch(log_path)
        except PermissionError:
            msg = "Error: Insufficient permissions to write log to '{}'.".format(log_path)
            raise PermissionError(msg)  # Currently no log, so just raise an exception

        # Define the logging function
        def write_log(msg):
            now = datetime.datetime.now().isoformat(' ', timespec='seconds')
            with open(log_path, 'a') as f:
                f.write("[{now}]: {msg}\n".format(now=now, msg=msg))
    else:
        # No log file specified, so disable logging
        def write_log(msg):
            pass

    # Check the supplied cache path
    cache_path = config.get("cache_path")
    if cache_path:
        # Make sure that the log path exists and is writable
        try:
            touch(cache_path)  # Create the file if necessary
        except PermissionError:
            msg = "Error: Insufficient permissions to write to cache ({}).".format(cache_path)
            write_log(msg)
            raise PermissionError(msg)

        # Define the caching functions
        def write_cache(ip_addr):
            now = datetime.datetime.now().isoformat(' ', timespec='seconds')
            with open(cache_path, 'w') as f:
                f.write("[{}]: {}".format(now, ip_addr))

        def read_cache():
            with open(cache_path, "r") as f:
                cached = f.readline()
            return (cached[1:20], cached[23:])  # date_time, ip_addr
    else:
        # No cache file specified, so disable caching and warn the user!
        msg = ("Warning: No cache file specified, so the IP address will always be submitted "
               "as if new - this could be considered abusive!")
        write_log(msg)
        warnings.warn(msg)

        # Define the caching functions
        def write_cache(ip_addr):
            pass  # Don't write to cache

        def read_cache():
            return (None, None)

    # Get IPv4 address
    myip = pif.get_public_ip("v4.ident.me")  # Enforce IPv4 (for now)

    if not myip:
        msg = "Error: Failed to determine IPv4 address"
        write_log(msg)
        raise ConnectionError(msg)

    # Check whether the current IP is equal to the cached IP address
    date_time, cached_ip = read_cache()
    if force:
        write_log("Info: Performing forced update")
    elif myip == cached_ip:
        # Already up-to-date, so log it and exit
        write_log("Success: IP address is already up-to-date ({})".format(myip))
        return (False, myip, None)
    else:
        write_log("Info: New IP address detected ({})".format(myip))

    # Get API details
    api_key = config.get("api_key")
    api_secret = config.get("api_secret")

    # Check that they have values
    missing_cred = []
    if not api_key:
        missing_cred.append("'api_key'")
    if not api_secret:
        missing_cred.append("'api_secret'")

    if missing_cred:
        msg = "Error: Missing credentials - {} must be specified".format(" and ".join(missing_cred))
        write_log(msg)
        raise ConfigError(msg)

    # Initialise the connection classes
    account = Account(api_key=config.get("api_key"), api_secret=config.get("api_secret"))
    client = Client(account, api_base_url=config.get("api_base_url", "https://api.godaddy.com"))

    # Check that we have a connection and get the set of available domains
    try:
        available_domains = set(client.get_domains())
    except BadResponse as e:
        msg = "Error: Bad response from GoDaddy ({})".format(e._message)
        write_log(msg)
        raise BadResponse(msg)

    # Make the API requests to update the IP address
    failed_domains = set()  # Stores a set of failed domains - failures will be tolerated but logged
    succeeded_domains = []
    forced = "forcefully " if force else ""

    for target in config.get("targets", []):
        try:
            target_domain = target["domain"]
        except KeyError:
            msg = "Error: Missing 'domain' for target in configuration file"
            write_log(msg)
            raise ConfigError(msg)

        if isinstance(target_domain, str):
            target_domain = {target_domain}  # set of one element
        else:
            target_domain = set(target_domain)  # set of supplied targets

        unknown_domains = target_domain - available_domains
        failed_domains.update(unknown_domains)

        domains = list(target_domain & available_domains)  # Remove unknown domains
        if not domains:
            continue  # No known domains, so don't bother contacting GoDaddy

        subdomains = target.get("alias", "@")  # Default to no subdomain (GoDaddy uses "@" for this)

        try:
            update_succeeded = client.update_ip(myip, domains=domains, subdomains=subdomains)
        except BadResponse as e:
            msg = "Error: Bad response from GoDaddy ({})".format(e._message)
            write_log(msg)
            raise BadResponse(msg)

        if update_succeeded:
            succeeded_domains.append("{subs}.{doms}".format(subs=subdomains, doms=domains))
            write_log("Success: IP address {}updated to {} for {}.".format(forced,
                                                                           myip,
                                                                           succeeded_domains[-1]))
        else:
            msg = "Error: Unknown failure for (domain(s): {doms}, alias(es): {subs})".format(
                        doms=target_domain, subs=subdomains)
            write_log(msg)
            raise BadResponse(msg)

    if failed_domains:
        msg = "Warning: The following domains were not found {}".format(failed_domains)
        write_log(msg)
        warnings.warn(msg)

    # Write the new IP address to the cache and return
    write_cache(myip)
    return (True, myip, succeeded_domains)


def print_colourised(msg):
    """Print messages automatically colourised based on initial keywords

    Currently supports: "Success", "Info", "Warning", "Error", None
    """
    if msg.startswith("Success"):
        style = {
            "fg": "green",
            "bold": True,
        }
    elif msg.startswith("Info"):
        style = {
            "fg": "blue",
        }
    elif msg.startswith("Warning"):
        style = {
            "fg": "yellow",
        }
    elif msg.startswith("Error"):
        style = {
            "fg": "red",
            "bold": True,
        }
    else:
        style = {}  # Don't apply a special style

    click.echo(click.style(msg, **style))


def touch(path):
    """Touch a path, creating it if necessary
    """
    # Ensure the path exists
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Create the file if necessary
    with open(path, 'a'):
        os.utime(path, None)
