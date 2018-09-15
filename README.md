# GoDaddy-DDNS
DDNS-like update service for GoDaddy DNS records


## Purpose

This script and service enable DDNS-like checking of the public IP address and subsequent updating of GoDaddy DNS records, and is intended for use with servers that undergo infrequent public IP address changes. The aim is to get the benefits of dynamic DNS without the need for a third-party DDNS service.

**Note:** The lowest value of TTL (time-to-live) that GoDaddy permits is 600 seconds (10 minutes). As a result, the old IP address may still be cached on various for up to 10 minutes after a change is made, meaning that the site will remain temporarily unavailable at that domain. If you require lower downtime than this, please consider using a proper DDNS service such as [Dynu.com](https://dynu.com).


## Requirements

The script is compatible with Python >=3.4, but may be compatible with earlier versions.

### External packages:
 - `pyyaml`
 - `click`
 - `pif`
 - `godaddypy`


## Installation

The script can be installed for a single user if only the commandline tool is needed, but should be installed system-wide for use with the systemd service and timer.

### For system-wide installation:

```sh
$ git clone --depth=1 https://github.com/N-Parsons/godaddy-ddns.git
$ cd godaddy-ddns
$ sudo pip install .
```

### For user-only installation:

```sh
$ git clone --depth=1 https://github.com/N-Parsons/godaddy-ddns.git
$ cd godaddy-ddns
$ pip install --user .
```


## Usage

### Commandline tool

The script can be run manually by calling `godaddy-ddns` with the following options:

- `--config`: Path to the configuration file (default: `/etc/godaddy-ddns/config.yaml`).
- `--force`: Update the IP address regardless of the value in the cache.
- `--quiet`: Don't print messages to `stdout`.

### Systemd

Two systemd files are included with this package so that the script can be sceduled to run automatically. To use these, simply copy `godaddy-ddns.service` and `godaddy-ddns.timer` to `/etc/systemd/system/`, then enable and start the timer.

```sh
# cp godaddy-ddns.{service,timer} /etc/systemd/system/
# systemctl enable --now godaddy-ddns.timer
```

**Note:** The systemd service assumes that the configuration file is located at `/etc/godaddy-ddns/config.yaml`.


## Configuration options

An example configuration is avaiable in `config-example.yaml`.

### API credentials

API keys can be generated at <https://developer.godaddy.com/keys/>.

The API base URL may also be specified in the config file if you want to use the testing environment (OTE). I have not used this functionality, but it should work (note: you will need a separate key and secret for the OTE).

### Targets (domains you want to update)

The `targets` are a list of domains and aliases to be updated. Each element of this list consists of a mandatory `domain` and optional `alias`; both `domain` and `alias` may be single values or lists. If no alias is specified, `"@"` is assumed - this is how GoDaddy designates the lack of a subdomain, so the IP address for `example.com` will be updated.

A complete set of example targets are given in `config-example.yaml`.

Specifying non-existent aliases is silently tolerated by the API and thus also by this script. Non-existent domains cause a warning to be logged.

### Logging and caching

Paths may be set for the log and cache; setting these to `""` or commenting out the entries disables them. If the configured paths don't exist, the script will create them.

While caching *can* be disabled, it is **strongly** advised that you enable it. When the cache is disabled, the script will make API requests to set the IP address regardless of whether the IP address is already up-to-date - doing this repeatedly is unnecessary and could be considered abusive.


## License

This project is made available under the MIT license.
